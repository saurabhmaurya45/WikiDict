'''
SM-WikiDict Full Build Script (Initial Setup)
This script is used for initial setup when no manifest.json exists in S3.
It generates fake data, sorts it, creates an index, and uploads everything to S3.

Steps:
 1. Generate fake dataset using Faker module
 2. Sort the CSV file by title (case-insensitive) using external merge sort
 3. Create index file (JSON format) for fast byte-range lookups
 4. Upload data.csv and index.json to S3
 5. Create and upload manifest.json to S3

Usage:
    python scripts/build_wikidict_full.py [--target-size GB]
    python scripts/build_wikidict_full.py --target-size 5
    python scripts/build_wikidict_full.py --target-size 10
'''

import os
import sys
import json
import boto3
import csv
import tempfile
import heapq
import random
from datetime import datetime
from pathlib import Path
import logging
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from faker import Faker

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

# Initialize Faker
fake = Faker()

# S3 configuration
S3_BUCKET = os.getenv('AWS_BUCKET_NAME')
MANIFEST_FILE_NAME = 'manifest.json'
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION')

# Create s3 client
s3_client = boto3.client('s3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_DEFAULT_REGION)


def estimate_rows_for_size(target_size_gb, avg_value_size=8000):
    """
    Estimate number of rows needed to reach target size.

    Args:
        target_size_gb (float): Target file size in GB
        avg_value_size (int): Average size of value field in bytes

    Returns:
        int: Estimated number of rows needed
    """
    target_bytes = target_size_gb * (1024 ** 3)
    # Estimate: title (~20 bytes) + value (~8000 bytes) + CSV overhead (~10 bytes)
    avg_row_size = 20 + avg_value_size + 10
    estimated_rows = int(target_bytes / avg_row_size)
    return estimated_rows


def generate_fake_title():
    """Generate a realistic fake title for a dictionary entry."""
    title_types = [
        # Common words (30% probability)
        lambda: fake.word().capitalize(),
        lambda: fake.word().lower(),
        lambda: fake.word().capitalize() + " " + fake.word(),
        lambda: fake.word() + fake.word().capitalize(),
        lambda: fake.word().upper(),
        lambda: fake.word().capitalize() + "s",  # Plurals
        lambda: fake.word() + "ing",  # Gerunds
        lambda: fake.word() + "ed",  # Past tense
        lambda: fake.word() + "ly",  # Adverbs
        lambda: fake.word() + "er",  # Comparatives

        # Proper nouns (20% probability)
        lambda: fake.name(),
        lambda: fake.first_name(),
        lambda: fake.last_name(),
        lambda: fake.city(),
        lambda: fake.country(),
        lambda: fake.company(),
        lambda: fake.state(),
        lambda: fake.street_name(),
        lambda: fake.name() + " " + fake.last_name(),  # Full names
        lambda: "The " + fake.company(),  # Company with article
        lambda: fake.city() + " " + fake.city(),  # City combinations
        lambda: fake.company() + " " + random.choice(['Corporation', 'Inc', 'LLC', 'Ltd']),

        # Multi-word phrases (15% probability)
        lambda: fake.catch_phrase(),
        lambda: " ".join([fake.word() for _ in range(random.randint(2, 4))]),
        lambda: fake.sentence(nb_words=random.randint(2, 5)).rstrip('.'),
        lambda: fake.word().capitalize() + " of " + fake.word(),
        lambda: fake.word().capitalize() + " and " + fake.word(),
        lambda: "The " + fake.word().capitalize(),
        lambda: random.choice(['Old', 'New', 'Great', 'Little']) + " " + fake.word().capitalize(),

        # Technical/specialized terms (15% probability)
        lambda: fake.word() + "-" + fake.word(),
        lambda: fake.word().capitalize() + fake.word() + "tion",
        lambda: fake.word().capitalize() + fake.word() + "ism",
        lambda: "un" + fake.word(),
        lambda: "pre" + fake.word(),
        lambda: "anti" + fake.word(),
        lambda: fake.word() + "ology",
        lambda: "post" + fake.word(),
        lambda: "re" + fake.word(),
        lambda: "over" + fake.word(),
        lambda: fake.word() + "ness",  # Abstract nouns
        lambda: fake.word() + "ment",  # Process nouns
        lambda: fake.word() + "able",  # Adjectives
        lambda: fake.word() + "ive",  # Adjectives
        lambda: "non" + fake.word(),

        # Scientific/Academic terms (8% probability)
        lambda: fake.word() + " " + fake.word() + "sis",  # -sis suffix
        lambda: fake.word().capitalize() + "ology",
        lambda: fake.word() + "graphy",  # Writing/recording
        lambda: fake.word() + "metry",  # Measurement
        lambda: fake.word() + "scopy",  # Viewing/examining
        lambda: fake.word() + " theory",
        lambda: fake.word() + " effect",
        lambda: fake.last_name() + "'s law",
        lambda: fake.last_name() + "'s theorem",
        lambda: random.choice(['Alpha', 'Beta', 'Gamma', 'Delta']) + " " + fake.word(),

        # Abbreviations and acronyms (4% probability)
        lambda: ''.join([fake.word()[0].upper() for _ in range(random.randint(2, 4))]),
        lambda: fake.word()[:random.randint(3, 6)].upper(),
        lambda: 'Dr. ' + fake.last_name(),
        lambda: 'Mr. ' + fake.last_name(),
        lambda: 'Ms. ' + fake.last_name(),

        # Geographic and natural features (5% probability)
        lambda: fake.color_name().capitalize(),
        lambda: fake.job(),
        lambda: random.choice(['Mount', 'Lake', 'River', 'Cape']) + " " + fake.last_name(),
        lambda: random.choice(['Mount', 'Lake', 'River', 'Bay', 'Gulf']) + " " + fake.word().capitalize(),
        lambda: fake.country() + " " + random.choice(['Mountains', 'Valley', 'Desert', 'Plains']),
        lambda: random.choice(['North', 'South', 'East', 'West']) + " " + fake.city(),
        lambda: random.choice(['Upper', 'Lower', 'Middle']) + " " + fake.word().capitalize(),

        # Historical/Cultural terms (3% probability)
        lambda: random.choice(['Ancient', 'Medieval', 'Modern']) + " " + fake.word(),
        lambda: random.choice(['Classical', 'Renaissance', 'Victorian']) + " " + fake.word(),
        lambda: fake.word() + " " + random.choice(['Age', 'Era', 'Period']),
        lambda: random.choice(['Battle of', 'War of', 'Treaty of']) + " " + fake.city(),
        lambda: random.choice(['King', 'Queen', 'Emperor', 'Prince']) + " " + fake.first_name(),
    ]

    return random.choice(title_types)()


def generate_fake_value(size_bytes=8000):
    """
    Generate fake value text similar to Wikipedia articles.
    Ensures single-line output for CSV compatibility.

    Args:
        size_bytes (int): Target size in bytes (approximate)

    Returns:
        str: Generated text (single line, no newlines)
    """
    value_parts = []
    current_size = 0

    while current_size < size_bytes:
        content_type = random.choice(['paragraph', 'sentence', 'text', 'definition'])

        if content_type == 'paragraph':
            text = fake.paragraph(nb_sentences=random.randint(3, 7))
        elif content_type == 'sentence':
            text = fake.sentence(nb_words=random.randint(10, 30))
        elif content_type == 'text':
            text = fake.text(max_nb_chars=random.randint(200, 500))
        else:  # definition
            text = f"{fake.word()}: {fake.sentence()}"

        # Remove newlines and normalize whitespace
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())

        value_parts.append(text)
        current_size += len(text.encode('utf-8'))

    return ' '.join(value_parts)


def generate_unsorted_dataset(output_file, num_rows):
    """
    Generate fake CSV dataset (unsorted, for external sorting).

    Args:
        output_file (str): Path to output CSV file
        num_rows (int): Number of rows to generate

    Returns:
        bool: Success status
    """
    import time
    start_time = time.time()

    logger.info(f"Generating {num_rows:,} rows of fake data...")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    seen_titles = set()
    attempts = 0
    max_attempts = num_rows * 10
    row_count = 0

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['title', 'value'])
        writer.writeheader()

        while row_count < num_rows and attempts < max_attempts:
            title = generate_fake_title()

            # Ensure uniqueness
            if title in seen_titles:
                attempts += 1
                continue

            seen_titles.add(title)
            value = generate_fake_value(size_bytes=random.randint(5000, 12000))

            writer.writerow({'title': title, 'value': value})
            row_count += 1

            # Progress reporting
            if row_count % 10000 == 0:
                elapsed = time.time() - start_time
                rows_per_sec = row_count / elapsed
                logger.info(f"  Generated {row_count:,} / {num_rows:,} rows ({rows_per_sec:.0f} rows/sec)")

            attempts += 1

    if row_count < num_rows:
        logger.warning(f"Could only generate {row_count:,} unique titles out of {num_rows:,} requested")

    elapsed = time.time() - start_time
    logger.info(f"✓ Generation completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

    return True


def sort_csv_external(input_file, output_file, chunk_size=100000):
    """
    Sort CSV file using external merge sort (memory-efficient for large files).

    Args:
        input_file (str): Path to input CSV file
        output_file (str): Path to output sorted CSV file
        chunk_size (int): Rows per chunk

    Returns:
        bool: Success status
    """
    import time
    start_time = time.time()

    logger.info("Starting external merge sort...")
    logger.info(f"  Chunk size: {chunk_size:,} rows")

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='csv_sort_')
    logger.info(f"  Temp directory: {temp_dir}")

    try:
        # Phase 1: Split into sorted chunks
        logger.info("Phase 1: Splitting into sorted chunks...")
        chunk_files, header = split_and_sort_chunks(input_file, temp_dir, chunk_size)

        phase1_time = time.time() - start_time
        logger.info(f"✓ Phase 1 completed in {phase1_time:.1f} seconds")
        logger.info(f"  Created {len(chunk_files)} sorted chunks")

        # Phase 2: Merge sorted chunks
        logger.info("Phase 2: Merging sorted chunks...")
        merge_sorted_chunks(chunk_files, output_file, header)

        total_time = time.time() - start_time
        logger.info(f"✓ Phase 2 completed in {total_time - phase1_time:.1f} seconds")
        logger.info(f"✓ Total sorting time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")

        return True

    finally:
        # Cleanup temp files
        logger.info("Cleaning up temporary files...")
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def split_and_sort_chunks(input_file, temp_dir, chunk_size):
    """Split input file into sorted chunks."""
    chunk_files = []
    chunk_number = 0
    header = None

    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        header = reader.fieldnames

        chunk_data = []
        total_rows = 0

        for row in reader:
            chunk_data.append(row)
            total_rows += 1

            if len(chunk_data) >= chunk_size:
                chunk_file = write_sorted_chunk(chunk_data, temp_dir, chunk_number, header)
                chunk_files.append(chunk_file)
                chunk_number += 1
                logger.info(f"  Created chunk {chunk_number}: {total_rows:,} rows processed")
                chunk_data = []

        # Write remaining data
        if chunk_data:
            chunk_file = write_sorted_chunk(chunk_data, temp_dir, chunk_number, header)
            chunk_files.append(chunk_file)
            chunk_number += 1
            logger.info(f"  Created chunk {chunk_number}: {total_rows:,} rows processed")

    return chunk_files, header


def write_sorted_chunk(data, temp_dir, chunk_number, header):
    """Sort data and write to temp chunk file."""
    # Sort by title (case-insensitive)
    data.sort(key=lambda row: row['title'].lower())

    chunk_file = os.path.join(temp_dir, f'chunk_{chunk_number:04d}.csv')
    with open(chunk_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=header)
        writer.writeheader()
        writer.writerows(data)

    return chunk_file


def merge_sorted_chunks(chunk_files, output_file, header):
    """Merge sorted chunks using k-way merge with min-heap."""
    chunk_readers = []
    heap = []

    try:
        # Initialize readers and heap
        for idx, chunk_file in enumerate(chunk_files):
            reader = csv.DictReader(open(chunk_file, 'r', encoding='utf-8'))
            chunk_readers.append(reader)

            try:
                row = next(reader)
                sort_key = row['title'].lower()
                heapq.heappush(heap, (sort_key, idx, row))
            except StopIteration:
                pass

        # Write merged output
        total_written = 0
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=header)
            writer.writeheader()

            while heap:
                sort_key, chunk_idx, row = heapq.heappop(heap)
                writer.writerow(row)
                total_written += 1

                if total_written % 100000 == 0:
                    logger.info(f"  Merged {total_written:,} rows")

                # Get next row from same chunk
                try:
                    next_row = next(chunk_readers[chunk_idx])
                    next_sort_key = next_row['title'].lower()
                    heapq.heappush(heap, (next_sort_key, chunk_idx, next_row))
                except StopIteration:
                    pass

        logger.info(f"  Total rows merged: {total_written:,}")

    finally:
        for reader in chunk_readers:
            if hasattr(reader, 'close'):
                reader.close()


def create_index(csv_file_path, index_file_path):
    """
    Create JSON index file for byte-range lookups.

    Args:
        csv_file_path (str): Path to sorted CSV file
        index_file_path (str): Path to output index JSON file

    Returns:
        bool: Success status
    """
    import time
    start_time = time.time()

    logger.info("Creating index file...")

    index = {}
    row_count = 0

    with open(csv_file_path, 'rb') as f:
        # Skip header
        header_line = f.readline()
        header_end = f.tell()
        logger.info(f"  Header ends at byte {header_end}")

        while True:
            row_start = f.tell()
            raw_line = f.readline()

            if not raw_line:
                break

            row_end = f.tell()
            row_length = row_end - row_start

            try:
                # Parse CSV line to extract title
                line_str = raw_line.decode('utf-8')
                import io
                line_reader = csv.DictReader(io.StringIO('title,value\n' + line_str))
                row = next(line_reader)
                key = row['title']

                # Add to index
                index[key] = {
                    "offset": row_start,
                    "length": row_length
                }

                row_count += 1

                if row_count % 100000 == 0:
                    logger.info(f"  Indexed {row_count:,} rows...")

            except Exception as e:
                logger.warning(f"Error parsing row at position {row_start}: {e}")
                continue

    # Write index to JSON
    logger.info(f"Writing index to {index_file_path}...")
    with open(index_file_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    index_size = os.path.getsize(index_file_path)
    index_size_mb = index_size / (1024 ** 2)

    elapsed = time.time() - start_time

    logger.info(f"✓ Index created successfully!")
    logger.info(f"  Total rows indexed: {row_count:,}")
    logger.info(f"  Index file size: {index_size_mb:.2f} MB")
    logger.info(f"  Time taken: {elapsed:.1f} seconds")

    return True


def upload_to_s3(data_file_path, index_file_path):
    """
    Upload data.csv and index.json to S3.

    Args:
        data_file_path (str): Local path to data.csv
        index_file_path (str): Local path to index.json

    Returns:
        tuple: (s3_data_path, s3_index_path)
    """
    logger.info("Uploading files to S3...")

    # Generate S3 paths with current date
    date_str = datetime.now().strftime("%Y%m%d")
    s3_data_path = f"dict/{date_str}/data.csv"
    s3_index_path = f"dict/{date_str}/index.json"

    # Upload data.csv
    logger.info(f"  Uploading data.csv to s3://{S3_BUCKET}/{s3_data_path}...")
    s3_client.upload_file(data_file_path, S3_BUCKET, s3_data_path)

    # Upload index.json
    logger.info(f"  Uploading index.json to s3://{S3_BUCKET}/{s3_index_path}...")
    s3_client.upload_file(index_file_path, S3_BUCKET, s3_index_path)

    # Verify uploads
    logger.info("  Verifying uploads...")
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_data_path)
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_index_path)
        logger.info("✓ Upload verification successful")
    except ClientError:
        logger.error("✗ Upload verification failed!")
        raise

    logger.info(f"✓ Uploaded to s3://{S3_BUCKET}/{s3_data_path}")
    logger.info(f"✓ Uploaded to s3://{S3_BUCKET}/{s3_index_path}")

    return s3_data_path, s3_index_path


def create_and_upload_manifest(s3_data_path, s3_index_path):
    """
    Create manifest.json and upload to S3.

    Args:
        s3_data_path (str): S3 path to data.csv
        s3_index_path (str): S3 path to index.json

    Returns:
        bool: Success status
    """
    logger.info("Creating manifest.json...")

    manifest = {
        "service_name": "sm-wikidict",
        "service_description": "A dictionary service powered by Wiktionary.",
        "service_author": "Saurabh Maurya",
        "file_path": s3_data_path,
        "index_file_path": s3_index_path,
        "changelog_file_path": "",  # Empty for initial setup
        "last_updated_at": datetime.now().isoformat(),
        "version": datetime.now().strftime("%Y%m%d")
    }

    logger.info(f"  Manifest content: {json.dumps(manifest, indent=2)}")

    # Upload to S3
    logger.info(f"  Uploading manifest.json to s3://{S3_BUCKET}/{MANIFEST_FILE_NAME}...")
    manifest_data = json.dumps(manifest, indent=2).encode('utf-8')
    s3_client.put_object(Bucket=S3_BUCKET, Key=MANIFEST_FILE_NAME, Body=manifest_data)

    # Verify upload
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=MANIFEST_FILE_NAME)
        logger.info("✓ Manifest uploaded and verified")
    except ClientError:
        logger.error("✗ Manifest upload verification failed!")
        raise

    return True


def cleanup_local_files(data_dir="data/dict/"):
    """Cleanup local data files."""
    if os.path.exists(data_dir):
        logger.info(f"Cleaning up local data directory: {data_dir}")
        for root, dirs, files in os.walk(data_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        logger.info("✓ Cleanup complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='SM-WikiDict Full Build (Initial Setup)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
This script performs initial setup by:
  1. Generating fake data with Faker
  2. Sorting the CSV file externally
  3. Creating byte-range index
  4. Uploading to S3
  5. Creating and uploading manifest.json

Examples:
  # Generate 5GB dataset (default)
  python scripts/build_wikidict_full.py

  # Generate 10GB dataset
  python scripts/build_wikidict_full.py --target-size 10

  # Generate smaller test dataset
  python scripts/build_wikidict_full.py --target-size 1
        '''
    )

    parser.add_argument(
        '--target-size',
        type=float,
        default=5.0,
        help='Target dataset size in GB (default: 5.0)'
    )

    args = parser.parse_args()

    # Validate AWS credentials
    if not all([S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION]):
        logger.error("Missing AWS credentials in .env file")
        logger.error("Required: AWS_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION")
        return 1

    logger.info("=" * 60)
    logger.info("SM-WikiDict Full Build (Initial Setup)")
    logger.info("=" * 60)
    logger.info(f"Target size: {args.target_size:.2f} GB")
    logger.info(f"S3 Bucket: {S3_BUCKET}")
    logger.info(f"Region: {AWS_DEFAULT_REGION}")
    logger.info("")

    try:
        # Calculate number of rows
        num_rows = estimate_rows_for_size(args.target_size)
        logger.info(f"Estimated rows needed: {num_rows:,}")
        logger.info("")

        # Prepare file paths
        date_str = datetime.now().strftime("%Y%m%d")
        data_dir = f"data/dict/{date_str}"
        unsorted_file = f"{data_dir}/data_unsorted.csv"
        sorted_file = f"{data_dir}/data.csv"
        index_file = f"{data_dir}/index.json"

        # Step 1: Generate unsorted dataset
        logger.info("Step 1: Generating fake dataset...")
        generate_unsorted_dataset(unsorted_file, num_rows)
        logger.info("")

        # Step 2: Sort the dataset
        logger.info("Step 2: Sorting dataset...")
        sort_csv_external(unsorted_file, sorted_file, chunk_size=100000)
        logger.info("")

        # Remove unsorted file to save space
        logger.info("Removing unsorted file...")
        os.remove(unsorted_file)
        logger.info("")

        # Step 3: Create index
        logger.info("Step 3: Creating index...")
        create_index(sorted_file, index_file)
        logger.info("")

        # Step 4: Upload to S3
        logger.info("Step 4: Uploading to S3...")
        s3_data_path, s3_index_path = upload_to_s3(sorted_file, index_file)
        logger.info("")

        # Step 5: Create and upload manifest
        logger.info("Step 5: Creating and uploading manifest...")
        create_and_upload_manifest(s3_data_path, s3_index_path)
        logger.info("")

        # Success
        logger.info("=" * 60)
        logger.info("✓ Initial setup completed successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Verify files in S3 bucket")
        logger.info("  2. Test API lookups with the uploaded data")
        logger.info("  3. For incremental updates, run build_wikidict.py with changelog files")
        logger.info("")

        return 0

    except Exception as e:
        logger.error(f"✗ Build failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

    finally:
        # Always cleanup local files
        cleanup_local_files()


if __name__ == "__main__":
    sys.exit(main())
