'''
Generate Fake Dataset Script
Creates a fake CSV dataset with similar characteristics to the real WikiDict data.
Useful for testing the build pipeline without downloading the full Wikipedia dataset.

Usage:
    python scripts/generate_fake_dataset.py --target-size 8 --output data/dict/fake_data.csv
    python scripts/generate_fake_dataset.py --num-rows 1000000 --output data/dict/fake_data.csv
'''

import csv
import sys
import os
import argparse
import random
from faker import Faker

# Initialize Faker
fake = Faker()

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)


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
        # Common words (60% probability)
        lambda: fake.word().capitalize(),  # Single word
        lambda: fake.word().lower(),  # Lowercase word
        lambda: fake.word().capitalize() + " " + fake.word(),  # Two words
        lambda: fake.word() + fake.word().capitalize(),  # Compound word

        # Proper nouns (15% probability)
        lambda: fake.name(),  # Person name
        lambda: fake.first_name(),  # First name only
        lambda: fake.last_name(),  # Last name only
        lambda: fake.city(),  # City name
        lambda: fake.country(),  # Country name
        lambda: fake.company(),  # Company/organization name

        # Multi-word phrases (10% probability)
        lambda: fake.catch_phrase(),  # Catch phrase
        lambda: " ".join([fake.word() for _ in range(random.randint(2, 4))]),  # Multiple words
        lambda: fake.sentence(nb_words=random.randint(2, 5)).rstrip('.'),  # Short phrase

        # Technical/specialized terms (10% probability)
        lambda: fake.word() + "-" + fake.word(),  # Hyphenated word
        lambda: fake.word().capitalize() + fake.word() + "tion",  # -tion suffix
        lambda: fake.word().capitalize() + fake.word() + "ism",  # -ism suffix
        lambda: "un" + fake.word(),  # Prefix un-
        lambda: "pre" + fake.word(),  # Prefix pre-
        lambda: "anti" + fake.word(),  # Prefix anti-
        lambda: fake.word() + "ology",  # -ology suffix (sciences)

        # Abbreviations and acronyms (3% probability)
        lambda: ''.join([fake.word()[0].upper() for _ in range(random.randint(2, 4))]),  # Acronym
        lambda: fake.word()[:random.randint(3, 6)].upper(),  # Abbreviation

        # Special categories (2% probability)
        lambda: fake.color_name().capitalize(),  # Color names
        lambda: fake.job(),  # Occupations
        lambda: random.choice(['Mount', 'Lake', 'River', 'Cape']) + " " + fake.last_name(),  # Geographic features
    ]

    return random.choice(title_types)()


def generate_fake_value(size_bytes=8000):
    """
    Generate fake value text similar to Wikipedia articles.
    Ensures single-line output for CSV compatibility and byte-range indexing.

    Args:
        size_bytes (int): Target size in bytes (approximate)

    Returns:
        str: Generated text (single line, no newlines)
    """
    # Generate paragraphs until we reach approximate target size
    value_parts = []
    current_size = 0

    while current_size < size_bytes:
        # Choose random content type
        content_type = random.choice([
            'paragraph',
            'sentence',
            'text',
            'definition'
        ])

        if content_type == 'paragraph':
            text = fake.paragraph(nb_sentences=random.randint(3, 7))
        elif content_type == 'sentence':
            text = fake.sentence(nb_words=random.randint(10, 30))
        elif content_type == 'text':
            text = fake.text(max_nb_chars=random.randint(200, 500))
        else:  # definition
            text = f"{fake.word()}: {fake.sentence()}"

        # Remove newlines and normalize whitespace for single-line CSV
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())  # Collapse multiple spaces

        value_parts.append(text)
        current_size += len(text.encode('utf-8'))

    return ' '.join(value_parts)


def generate_fake_dataset(output_file, num_rows=None, target_size_gb=None, sort_output=True):
    """
    Generate a fake CSV dataset with unique titles.
    Uses streaming write for memory efficiency with large datasets.

    Args:
        output_file (str): Path to output CSV file
        num_rows (int): Number of rows to generate (if specified)
        target_size_gb (float): Target file size in GB (if specified)
        sort_output (bool): Whether to sort by title (default: True)
    """
    import time
    start_time = time.time()

    # Determine number of rows
    if num_rows is None and target_size_gb is None:
        print("Error: Must specify either --num-rows or --target-size")
        return False

    if num_rows is None:
        num_rows = estimate_rows_for_size(target_size_gb)
        print(f"Target size: {target_size_gb:.2f} GB")
        print(f"Estimated rows needed: {num_rows:,}")
    else:
        print(f"Generating {num_rows:,} rows")

    print()

    # Create output directory
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Determine if we should use streaming (memory-efficient) or in-memory approach
    use_streaming = num_rows > 100000  # Use streaming for large datasets

    if use_streaming:
        print("Using memory-efficient streaming mode for large dataset...")
        temp_file = output_file + '.tmp'

        # Generate data and write directly to temp file
        print("Generating and writing fake data with unique titles...")
        seen_titles = set()
        attempts = 0
        max_attempts = num_rows * 10
        row_count = 0

        with open(temp_file, 'w', encoding='utf-8', newline='') as f:
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

                # Write directly to file
                writer.writerow({
                    'title': title,
                    'value': value
                })

                row_count += 1

                # Progress reporting
                if row_count % 10000 == 0:
                    elapsed = time.time() - start_time
                    rows_per_sec = row_count / elapsed
                    print(f"  Generated {row_count:,} / {num_rows:,} rows ({rows_per_sec:.0f} rows/sec)")

                attempts += 1

        if row_count < num_rows:
            print(f"\nWarning: Could only generate {row_count:,} unique titles out of {num_rows:,} requested")
            num_rows = row_count

        # Sort the file if requested
        if sort_output:
            print("\nSorting file by title...")
            print("  Reading file into memory for sorting...")

            with open(temp_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            print(f"  Sorting {len(rows):,} rows...")
            rows.sort(key=lambda x: x['title'].lower())

            print(f"  Writing sorted data to {output_file}...")
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['title', 'value'])
                writer.writeheader()
                writer.writerows(rows)

            # Remove temp file
            os.remove(temp_file)
        else:
            # Just rename temp file to final name
            os.rename(temp_file, output_file)

    else:
        # In-memory approach for small datasets (faster)
        print("Using in-memory mode for small dataset...")
        print("Generating fake data with unique titles...")
        rows = []
        seen_titles = set()
        attempts = 0
        max_attempts = num_rows * 10

        while len(rows) < num_rows and attempts < max_attempts:
            title = generate_fake_title()

            # Ensure uniqueness
            if title in seen_titles:
                attempts += 1
                continue

            seen_titles.add(title)
            value = generate_fake_value(size_bytes=random.randint(5000, 12000))

            rows.append({
                'title': title,
                'value': value
            })

            # Progress reporting
            if len(rows) % 10000 == 0:
                elapsed = time.time() - start_time
                rows_per_sec = len(rows) / elapsed
                print(f"  Generated {len(rows):,} / {num_rows:,} rows ({rows_per_sec:.0f} rows/sec)")

            attempts += 1

        if len(rows) < num_rows:
            print(f"\nWarning: Could only generate {len(rows):,} unique titles out of {num_rows:,} requested")
            num_rows = len(rows)

        # Sort by title (case-insensitive) if requested
        if sort_output:
            print("\nSorting rows by title...")
            rows.sort(key=lambda x: x['title'].lower())

        # Write to CSV
        print(f"\nWriting to {output_file}...")
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['title', 'value'])
            writer.writeheader()
            writer.writerows(rows)

    # Get final file size
    file_size = os.path.getsize(output_file)
    file_size_gb = file_size / (1024 ** 3)
    file_size_mb = file_size / (1024 ** 2)

    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("✓ Fake dataset generated successfully!")
    print("=" * 60)
    print(f"  Output file: {output_file}")
    print(f"  Total rows: {num_rows:,}")
    print(f"  File size: {file_size_gb:.2f} GB ({file_size_mb:.2f} MB)")
    print(f"  Sorted: {'Yes' if sort_output else 'No'}")
    print(f"  Time taken: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print()

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Generate fake CSV dataset for testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Generate dataset with specific number of rows
  python scripts/generate_fake_dataset.py \\
      --num-rows 100000 \\
      --output data/dict/fake_data.csv

  # Generate dataset to reach target size
  python scripts/generate_fake_dataset.py \\
      --target-size 8 \\
      --output data/dict/fake_data.csv

  # Generate unsorted dataset (for testing sort scripts)
  python scripts/generate_fake_dataset.py \\
      --num-rows 50000 \\
      --output data/dict/fake_data.csv \\
      --no-sort

  # Generate small dataset for quick testing
  python scripts/generate_fake_dataset.py \\
      --num-rows 1000 \\
      --output data/dict/test_data.csv
        '''
    )

    parser.add_argument('--num-rows', type=int, help='Number of rows to generate')
    parser.add_argument('--target-size', type=float, help='Target file size in GB')
    parser.add_argument('--output', required=True, help='Output CSV file path')
    parser.add_argument('--no-sort', action='store_true', help='Do not sort the output')
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')

    args = parser.parse_args()

    # Validate arguments
    if args.num_rows is None and args.target_size is None:
        parser.error("Must specify either --num-rows or --target-size")

    if args.num_rows is not None and args.target_size is not None:
        parser.error("Cannot specify both --num-rows and --target-size")

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        Faker.seed(args.seed)
        print(f"Using random seed: {args.seed}")
        print()

    # Generate dataset
    success = generate_fake_dataset(
        output_file=args.output,
        num_rows=args.num_rows,
        target_size_gb=args.target_size,
        sort_output=not args.no_sort
    )

    if success:
        print("Note: This script generates test data only.")
        print("For production use, run build_wikidict_full.py instead, which:")
        print("  - Generates data")
        print("  - Sorts it")
        print("  - Creates index")
        print("  - Uploads to S3")
        print()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
