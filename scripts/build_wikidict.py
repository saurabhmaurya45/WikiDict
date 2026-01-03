'''
 SM-WikiDict Build Script
 This script automates the process of building the SM-WikiDict project.
steps to build
 1. Pull manifest.json file from S3 bucket
 2. parse manifest.json
 3. Check if file exist which is mentioned in manifest.json as file_path
 4. If file exist, download the file from S3
       4.1 Download changelog file from S3
       4.2 Create new updated wikidict file via changelog file
            4.2.1 If key exist in both files, update the value from changelog file
            4.2.2 If key does not exist in existing file but exists in changelog file, add the key-value pair from changelog file
        4.3 Upload the updated wikidict file to S3
        4.4 Update the manifest.json file with new file_path, last_updated_at, version and upload to S3
 5. If not trigger full rebuild by calling build_full_wikidict.py script
'''

import os
import sys
import json
import boto3
import csv
from datetime import datetime
import subprocess
import logging
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# S3 configuration
S3_BUCKET = os.getenv('AWS_BUCKET_NAME')
MANIFEST_FILE_NAME = 'manifest.json'
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION')

# create s3 client
s3_client = boto3.client('s3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_DEFAULT_REGION)

# load manifest.json file from S3
def load_manifest_from_s3():
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=MANIFEST_FILE_NAME)
        manifest = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"Loaded manifest: {manifest}")
        return manifest
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.warning(f"{MANIFEST_FILE_NAME} not found in S3. Starting with empty manifest.")
            return {}
        else:
            logger.error(f"Error loading manifest from S3: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error loading manifest: {e}")
        raise

# update manifest.json file in S3
def update_manifest_in_s3(manifest):
    try:
        manifest_data = json.dumps(manifest, indent=2).encode('utf-8')
        s3_client.put_object(Bucket=S3_BUCKET, Key=MANIFEST_FILE_NAME, Body=manifest_data)
        logger.info(f"Updated manifest.json in s3://{S3_BUCKET}/{MANIFEST_FILE_NAME}")
    except Exception as e:
        logger.error(f"Error updating manifest in S3: {e}")
        raise

# upload updated wikidict file to S3 with index file and verify
def upload_file_to_s3(file_path, manifest):
    try:
        # Hardcoded names for security - only accept data.csv and index.json
        index_local_path = file_path.replace("data.csv", "index.json")

        # Verify files exist
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found: {file_path}")
        if not os.path.exists(index_local_path):
            raise FileNotFoundError(f"Index file not found: {index_local_path}")

        # Hardcoded S3 paths for security
        s3_file_path = "dict/" + datetime.now().strftime("%Y%m%d") + "/data.csv"
        index_file_path = "dict/" + datetime.now().strftime("%Y%m%d") + "/index.json"

        # Upload data file
        logger.info("Uploading data.csv to S3...")
        s3_client.upload_file(file_path, S3_BUCKET, s3_file_path)

        # Upload index file
        logger.info("Uploading index.json to S3...")
        s3_client.upload_file(index_local_path, S3_BUCKET, index_file_path)

        # Verify uploads
        logger.info("Verifying uploads...")
        try:
            s3_client.head_object(Bucket=S3_BUCKET, Key=s3_file_path)
            s3_client.head_object(Bucket=S3_BUCKET, Key=index_file_path)
            logger.info("✓ Upload verification successful")
        except ClientError:
            logger.error("✗ Upload verification failed!")
            raise

        # Update manifest
        manifest['file_path'] = s3_file_path
        manifest['last_updated_at'] = datetime.now().isoformat()
        manifest['version'] = datetime.now().strftime("%Y%m%d")
        manifest['index_file_path'] = index_file_path

        logger.info(f"✓ Uploaded to s3://{S3_BUCKET}/{s3_file_path}")
        logger.info(f"✓ Uploaded to s3://{S3_BUCKET}/{index_file_path}")

    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error uploading files to S3: {e}")
        raise

# download existing wikidict file from S3 with index file
def download_file_from_s3(s3_file_path):
    try:
        file_name = os.path.basename(s3_file_path)
        file_path = os.path.join("data/" + s3_file_path)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        logger.info(f"Downloading {file_name} from S3...")
        s3_client.download_file(S3_BUCKET, s3_file_path, file_path)

        # Download index file (hardcoded names for security)
        index_s3_file_path = s3_file_path.replace("data.csv", "index.json")
        index_file_path = file_path.replace("data.csv", "index.json")

        s3_client.download_file(S3_BUCKET, index_s3_file_path, index_file_path)

        logger.info(f"✓ Downloaded {file_name} to {file_path}")
        logger.info(f"✓ Downloaded index file to {index_file_path}")
        return file_path

    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"File not found in S3: {s3_file_path}")
        else:
            logger.error(f"Error downloading from S3: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {e}")
        raise

# download changelog file from S3
def download_changelog_from_s3(changelog_file_path):
    try:
        file_path = os.path.join("data/" + changelog_file_path)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        logger.info("Downloading changelog from S3...")
        s3_client.download_file(S3_BUCKET, changelog_file_path, file_path)
        logger.info(f"✓ Downloaded changelog {changelog_file_path} to {file_path}")
        return file_path

    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"Changelog file not found in S3: {changelog_file_path}")
        else:
            logger.error(f"Error downloading changelog from S3: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading changelog: {e}")
        raise

# Update wikidict file using changelog file and build index
def update_wikidict(existing_file_path, changelog_file_path, output_file_path):
    # Increase CSV field size limit
    csv.field_size_limit(sys.maxsize)

    updated_index_file_path = output_file_path.replace("data.csv", "index.json")

    logger.info("Starting sorted merge of two sorted CSV files and building index...")

    # Index to be built during merge
    index = {}

    # Open both files and the output file
    with open(existing_file_path, 'r', encoding='utf-8') as existing_file, \
         open(changelog_file_path, 'r', encoding='utf-8') as changelog_file, \
         open(output_file_path, 'w', encoding='utf-8', newline='') as output_file:

        existing_reader = csv.DictReader(existing_file)
        changelog_reader = csv.DictReader(changelog_file)
        writer = csv.DictWriter(output_file, fieldnames=['title', 'value'])
        writer.writeheader()

        # Get first row from each file
        existing_row = next(existing_reader, None)
        changelog_row = next(changelog_reader, None)

        existing_count = 0
        changelog_count = 0
        updated_count = 0
        added_count = 0
        total_count = 0

        # Merge the two sorted files (like merge sort)
        while existing_row is not None or changelog_row is not None:
            # Track byte position before writing
            row_start = output_file.tell()

            # If one file is exhausted, write from the other
            if existing_row is None:
                # Only changelog left
                writer.writerow({'title': changelog_row['title'], 'value': changelog_row['value']})
                row_end = output_file.tell()

                # Add to index
                index[changelog_row['title']] = {
                    "offset": row_start,
                    "length": row_end - row_start
                }

                added_count += 1
                total_count += 1
                changelog_row = next(changelog_reader, None)
                changelog_count += 1

            elif changelog_row is None:
                # Only existing left
                writer.writerow({'title': existing_row['title'], 'value': existing_row['value']})
                row_end = output_file.tell()

                # Add to index
                index[existing_row['title']] = {
                    "offset": row_start,
                    "length": row_end - row_start
                }

                total_count += 1
                existing_row = next(existing_reader, None)
                existing_count += 1

            else:
                # Both files have data, compare titles (case-insensitive)
                existing_title_lower = existing_row['title'].lower()
                changelog_title_lower = changelog_row['title'].lower()

                if existing_title_lower < changelog_title_lower:
                    # Existing title comes first alphabetically
                    writer.writerow({'title': existing_row['title'], 'value': existing_row['value']})
                    row_end = output_file.tell()

                    # Add to index
                    index[existing_row['title']] = {
                        "offset": row_start,
                        "length": row_end - row_start
                    }

                    total_count += 1
                    existing_row = next(existing_reader, None)
                    existing_count += 1

                elif existing_title_lower > changelog_title_lower:
                    # Changelog title comes first alphabetically (new entry)
                    writer.writerow({'title': changelog_row['title'], 'value': changelog_row['value']})
                    row_end = output_file.tell()

                    # Add to index
                    index[changelog_row['title']] = {
                        "offset": row_start,
                        "length": row_end - row_start
                    }

                    added_count += 1
                    total_count += 1
                    changelog_row = next(changelog_reader, None)
                    changelog_count += 1

                else:
                    # Same title - use value from changelog (update)
                    writer.writerow({'title': changelog_row['title'], 'value': changelog_row['value']})
                    row_end = output_file.tell()

                    # Add to index
                    index[changelog_row['title']] = {
                        "offset": row_start,
                        "length": row_end - row_start
                    }

                    updated_count += 1
                    total_count += 1
                    existing_row = next(existing_reader, None)
                    changelog_row = next(changelog_reader, None)
                    existing_count += 1
                    changelog_count += 1

            # Progress reporting
            if total_count % 100000 == 0:
                logger.info(f"  Merged {total_count:,} entries...")

    # Write index file
    logger.info(f"Writing index to {updated_index_file_path}...")
    with open(updated_index_file_path, 'w', encoding='utf-8') as idx_f:
        json.dump(index, idx_f, ensure_ascii=False, indent=2)

    index_size = os.path.getsize(updated_index_file_path)
    index_size_mb = index_size / (1024 ** 2)

    # Validate index
    if len(index) != total_count:
        logger.warning("Index size mismatch!")
        logger.warning(f"  Index entries: {len(index):,}")
        logger.warning(f"  Total rows: {total_count:,}")
        logger.warning(f"  Difference: {total_count - len(index):,}")
    else:
        logger.info(f"✓ Index validation passed: {len(index):,} entries")

    logger.info("Merge and indexing complete!")
    logger.info(f"  Processed {existing_count:,} entries from existing file")
    logger.info(f"  Processed {changelog_count:,} entries from changelog file")
    logger.info(f"  Updated {updated_count:,} existing entries")
    logger.info(f"  Added {added_count:,} new entries")
    logger.info(f"  Total entries in output: {total_count:,}")
    logger.info(f"  Updated wikidict saved to {output_file_path}")
    logger.info(f"  Index saved to {updated_index_file_path} ({index_size_mb:.2f} MB)")
    logger.info("  Output file is SORTED ✓")
    logger.info("  Index created ✓")

# cleanup downloaded files and processed files from local storage
def cleanup_local_files():
    data_dir = "data/dict/"
    if os.path.exists(data_dir):
        for root, dirs, files in os.walk(data_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        logger.info(f"Cleaned up local data directory: {data_dir}")

# Build updated wikidict file
def build_updated_wikidict(manifest):
    # Validate manifest structure
    required_fields = ['file_path', 'changelog_file_path']
    for field in required_fields:
        if field not in manifest or not manifest[field]:
            raise ValueError(f"Missing or empty required field in manifest: {field}")

    existing_file_path = manifest['file_path']
    changelog_file_path = manifest['changelog_file_path']

    logger.info("Starting incremental build...")
    logger.info(f"  Existing file: {existing_file_path}")
    logger.info(f"  Changelog file: {changelog_file_path}")

    try:
        # Download existing wikidict file
        existing_file_local_path = download_file_from_s3(existing_file_path)

        # Download changelog file
        changelog_local_path = download_changelog_from_s3(changelog_file_path)

        # Create updated wikidict file
        updated_wikidict_path = os.path.join("data/dict/" + datetime.now().strftime("%Y%m%d") + "/data.csv")
        os.makedirs(os.path.dirname(updated_wikidict_path), exist_ok=True)
        update_wikidict(existing_file_local_path, changelog_local_path, updated_wikidict_path)

        # Upload updated wikidict file to S3
        upload_file_to_s3(updated_wikidict_path, manifest)

        # Update manifest in S3 (only if upload succeeded)
        update_manifest_in_s3(manifest)

        logger.info("✓ Build completed successfully!")

    except Exception as e:
        logger.error(f"✗ Build failed: {e}")
        logger.error("Original files in S3 remain unchanged (no rollback needed)")
        raise
    finally:
        # Always cleanup local files to prevent storage cost accumulation
        # Safe because manifest.json is only updated on success, so API continues using old files on failure
        cleanup_local_files()



def main():
    manifest = load_manifest_from_s3()

    # Check if manifest has valid file_path (exists, non-empty, and not just whitespace)
    has_valid_file_path = (
        manifest and
        'file_path' in manifest and
        manifest['file_path'] and
        manifest['file_path'].strip()
    )

    if has_valid_file_path:
        logger.info("Incremental update detected. Building updated wikidict...")
        build_updated_wikidict(manifest)
    else:
        logger.info("No existing file found in manifest. Triggering full rebuild...")
        subprocess.run(['python', 'scripts/build_wikidict_full.py'], check=True)

if __name__ == "__main__":
    main()