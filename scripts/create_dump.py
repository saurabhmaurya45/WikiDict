import subprocess
import csv
import re
import os
import json
import time
import mwxml
import mwparserfromhell
from multiprocessing import Pool, cpu_count
import shutil

# ---------------- CONFIG ----------------

DUMP_FILE = "enwiki-latest-pages-articles.xml.bz2"
OUTPUT_CSV = "wikipedia_kv_1.csv"
CHECKPOINT_FILE = "checkpoint.json"

MIN_TEXT_LENGTH = 100            # drop very small stubs
MAX_RAW_TEXT_LENGTH = 1_000_000  # safety guard (1MB wikitext)
BATCH_SIZE = 1000                # larger batches for better throughput
NUM_WORKERS = max(1, cpu_count() - 2)  # auto-detect, leave 2 cores free
CHECKPOINT_INTERVAL = 10000      # less frequent checkpoints for speed

# ----------------------------------------


def get_decompressor():
    """Find the fastest available bz2 decompressor."""
    for cmd in ["lbzip2", "pbzip2", "bzcat"]:
        if shutil.which(cmd):
            return cmd
    return None


def open_dump_file(filepath):
    """
    Open dump file using fastest available method.
    Priority: lbzip2 > pbzip2 > bzcat > Python bz2
    """
    if not filepath.endswith(".bz2"):
        # Already decompressed XML
        return open(filepath, "rb")

    decompressor = get_decompressor()

    if decompressor == "lbzip2":
        log(f"⚡ Using lbzip2 (fastest parallel decompression)")
        proc = subprocess.Popen(
            ["lbzip2", "-dc", filepath],
            stdout=subprocess.PIPE,
            bufsize=64 * 1024 * 1024  # 64MB buffer
        )
        return proc.stdout
    elif decompressor == "pbzip2":
        log(f"⚡ Using pbzip2 (parallel decompression)")
        proc = subprocess.Popen(
            ["pbzip2", "-dc", filepath],
            stdout=subprocess.PIPE,
            bufsize=64 * 1024 * 1024
        )
        return proc.stdout
    elif decompressor == "bzcat":
        log(f"⚙️  Using bzcat (single-threaded)")
        proc = subprocess.Popen(
            ["bzcat", filepath],
            stdout=subprocess.PIPE,
            bufsize=64 * 1024 * 1024
        )
        return proc.stdout
    else:
        log(f"⚠️  No external decompressor found, using slow Python bz2")
        log(f"   Install lbzip2 or pbzip2 for 10-50x faster decompression:")
        log(f"   brew install lbzip2  (Mac) | apt install lbzip2 (Linux)")
        import bz2
        return bz2.open(filepath, "rb")


def log(message):
    """Print timestamped log message."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def load_checkpoint():
    """Load checkpoint if exists, returns (last_title, count) or (None, 0)."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            data = json.load(f)
            log(f"📂 Loaded checkpoint: {data['count']:,} articles, last title: '{data['last_title']}'")
            return data["last_title"], data["count"]
    return None, 0


def save_checkpoint(last_title, count):
    """Save current progress to checkpoint file."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"last_title": last_title, "count": count}, f)
    log(f"💾 Checkpoint saved: {count:,} articles")


def extract_latest_text(page):
    """
    pages-articles dump contains only the latest revision,
    but we keep this generic and safe.
    """
    for rev in page:
        if rev.text:
            return rev.text
    return None


def safe_remove(wikicode, node):
    """
    Remove a node from wikicode, but never crash if mwparser
    cannot locate it (common for templates like {{!}}).
    """
    try:
        wikicode.remove(node)
    except ValueError:
        pass  # ignore nodes that cannot be removed safely


# Pre-compile regex patterns for speed
RE_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
RE_TEMPLATES = re.compile(r"\{\{[^{}]*\}\}")
RE_REFS = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/]*/\s*>", re.DOTALL | re.IGNORECASE)
RE_TAGS = re.compile(r"<[^>]+>")
RE_LINKS = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
RE_EXT_LINKS = re.compile(r"\[https?://[^\s\]]+\s*([^\]]*)\]")
RE_BOLD_ITALIC = re.compile(r"'{2,5}")
RE_HEADINGS = re.compile(r"^=+\s*(.*?)\s*=+$", re.MULTILINE)
RE_BRACKETS = re.compile(r"\[\[|\]\]|\{\{|\}\}")
RE_WHITESPACE = re.compile(r"\s+")


def clean_wikitext_fast(text):
    """
    Fast regex-based wikitext cleaning.
    ~3-5x faster than mwparserfromhell for most articles.
    """
    # Remove HTML comments
    text = RE_COMMENTS.sub("", text)

    # Remove references
    text = RE_REFS.sub("", text)

    # Remove templates (iterate for nested)
    for _ in range(5):
        new_text = RE_TEMPLATES.sub("", text)
        if new_text == text:
            break
        text = new_text

    # Remove remaining HTML tags
    text = RE_TAGS.sub("", text)

    # Convert wiki links [[link|text]] -> text
    text = RE_LINKS.sub(r"\1", text)

    # Convert external links [url text] -> text
    text = RE_EXT_LINKS.sub(r"\1", text)

    # Remove bold/italic markup
    text = RE_BOLD_ITALIC.sub("", text)

    # Convert headings
    text = RE_HEADINGS.sub(r"\1", text)

    # Remove any leftover brackets
    text = RE_BRACKETS.sub("", text)

    # Normalize whitespace
    text = RE_WHITESPACE.sub(" ", text).strip()

    return text


def clean_wikitext(text):
    """
    Convert MediaWiki markup into readable plain text.
    Uses fast regex for most cases, falls back to mwparserfromhell for complex ones.
    """
    # Try fast method first
    try:
        cleaned = clean_wikitext_fast(text)
        # If result looks reasonable, use it
        if len(cleaned) > 50 and "{{" not in cleaned and "[[" not in cleaned:
            return cleaned
    except Exception:
        pass

    # Fall back to mwparserfromhell for complex cases
    wikicode = mwparserfromhell.parse(text)

    # Remove templates {{...}}
    for template in wikicode.filter_templates(recursive=True):
        safe_remove(wikicode, template)

    # Remove HTML-style tags like <ref>, <gallery>, etc.
    for tag in wikicode.filter_tags(recursive=True):
        safe_remove(wikicode, tag)

    # Convert remaining markup to text
    cleaned = wikicode.strip_code()

    # Remove leftover [[ ]] from links
    cleaned = re.sub(r"\[\[|\]\]", "", cleaned)

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def process_page(item):
    """
    Process a single page (title, raw_text) tuple.
    Returns (title, cleaned_text) or None if page should be skipped.
    """
    title, raw_text = item

    try:
        cleaned_text = clean_wikitext(raw_text)

        # Drop very small / low-value pages
        if len(cleaned_text) < MIN_TEXT_LENGTH:
            return None

        return (title, cleaned_text)
    except Exception:
        return None


def main():
    # Load checkpoint
    resume_after_title, count = load_checkpoint()
    skipping = resume_after_title is not None

    batch = []
    pages_scanned = 0
    skipped_redirects = 0
    skipped_small = 0
    skipped_large = 0
    last_title = None
    start_time = time.time()

    log(f"🚀 Starting with {NUM_WORKERS} worker processes (detected {cpu_count()} CPUs)")
    log(f"📁 Input: {DUMP_FILE}")
    log(f"📁 Output: {OUTPUT_CSV}")
    log(f"📊 Batch size: {BATCH_SIZE}, Checkpoint interval: {CHECKPOINT_INTERVAL}")

    # Open in append mode if resuming, write mode if fresh start
    file_mode = "a" if resume_after_title else "w"

    with open_dump_file(DUMP_FILE) as dump_file, \
         open(OUTPUT_CSV, file_mode, encoding="utf-8", newline="") as csv_file, \
         Pool(NUM_WORKERS) as pool:

        writer = csv.writer(csv_file)

        # Write header only for fresh start
        if not resume_after_title:
            writer.writerow(["title", "value"])

        dump = mwxml.Dump.from_file(dump_file)

        for page in dump:
            pages_scanned += 1

            # Only main namespace (articles)
            if page.namespace != 0:
                continue

            title = page.title

            # Skip until we reach the checkpoint
            if skipping:
                if title == resume_after_title:
                    skipping = False
                    log(f"⏩ Skipped to checkpoint, resuming after '{title}'")
                continue

            raw_text = extract_latest_text(page)

            if not raw_text:
                continue

            # Skip redirects
            if raw_text.lstrip().upper().startswith("#REDIRECT"):
                skipped_redirects += 1
                continue

            # Safety guard against pathological pages
            if len(raw_text) > MAX_RAW_TEXT_LENGTH:
                skipped_large += 1
                log(f"⚠️  Skipped large page: '{title}' ({len(raw_text):,} bytes)")
                continue

            batch.append((title, raw_text))
            last_title = title

            # Process batch in parallel when full
            if len(batch) >= BATCH_SIZE:
                results = pool.map(process_page, batch)
                batch_written = 0
                for result in results:
                    if result is not None:
                        writer.writerow(result)
                        count += 1
                        batch_written += 1
                    else:
                        skipped_small += 1
                batch = []

                # Log progress
                if count % 10_000 < BATCH_SIZE:
                    elapsed = time.time() - start_time
                    rate = count / elapsed if elapsed > 0 else 0
                    log(f"📊 Progress: {count:,} articles written | "
                        f"{pages_scanned:,} pages scanned | "
                        f"{rate:.1f} articles/sec")

                # Save checkpoint
                if count % CHECKPOINT_INTERVAL < BATCH_SIZE:
                    csv_file.flush()  # ensure data is written before checkpoint
                    save_checkpoint(last_title, count)

        # Process remaining pages in final batch
        if batch:
            results = pool.map(process_page, batch)
            for result in results:
                if result is not None:
                    writer.writerow(result)
                    count += 1
                else:
                    skipped_small += 1

        # Final checkpoint
        if last_title:
            csv_file.flush()
            save_checkpoint(last_title, count)

    # Final summary
    elapsed = time.time() - start_time
    log("=" * 50)
    log(f"✅ Done!")
    log(f"📊 Total articles written: {count:,}")
    log(f"📊 Total pages scanned: {pages_scanned:,}")
    log(f"📊 Skipped redirects: {skipped_redirects:,}")
    log(f"📊 Skipped small articles: {skipped_small:,}")
    log(f"📊 Skipped large articles: {skipped_large:,}")
    log(f"⏱️  Total time: {elapsed/3600:.2f} hours ({elapsed:.0f} seconds)")
    log(f"⚡ Average rate: {count/elapsed:.1f} articles/sec")


if __name__ == "__main__":
    main()
