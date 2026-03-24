import boto3
import os
import time
from dotenv import load_dotenv

from extractor import extract_lab_data
from db.insert_data import insert_lab_data
from db.db_config import get_connection

# ==============================
# LOAD ENV VARIABLES
# ==============================
load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME")
S3_PREFIX = os.getenv("S3_PREFIX")
AWS_REGION = os.getenv("AWS_REGION")
LOCAL_DOWNLOAD_PATH = os.getenv("LOCAL_DOWNLOAD_PATH", "reports")
os.makedirs(LOCAL_DOWNLOAD_PATH, exist_ok=True)

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION
)

# ==============================
# DATABASE HELPERS
# ==============================
def get_status_id(cursor, status_name):
    cursor.execute("SELECT status_id FROM dev.status_details WHERE status_name = %s", (status_name,))
    return cursor.fetchone()[0]

def report_should_be_processed(s3_path):
    """Return True if file is not success and not permanently failed."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT upload_status_id FROM dev.reports_upload_details WHERE s3_path = %s
        """, (s3_path,))
        row = cursor.fetchone()
        if not row:
            return True
        status_id = row[0]
        success = get_status_id(cursor, "success")
        permanent = get_status_id(cursor, "permanent failed")
        return status_id not in (success, permanent)
    finally:
        cursor.close()
        conn.close()

def list_pdfs_from_s3():
    pdf_keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf") and not key.endswith("/"):
                pdf_keys.append(key)
    return pdf_keys

def download_single_pdf(key):
    file_name = key.split("/")[-1]
    local_path = os.path.join(LOCAL_DOWNLOAD_PATH, file_name)
    s3.download_file(BUCKET_NAME, key, local_path)
    return local_path

# ==============================
# MAIN BATCH PROCESS
# ==============================
def run_batch():
    BATCH_SIZE = 100
    print("\n========== STARTING BATCH ==========\n")

    all_keys = list_pdfs_from_s3()
    print(f"Total PDFs in S3: {len(all_keys)}")

    to_process = [k for k in all_keys if report_should_be_processed(k)]
    print(f"Files to process (new + retry): {len(to_process)}")

    if not to_process:
        print("No files to process.")
        return

    batch = to_process[:BATCH_SIZE]
    for key in batch:
        print(f"\n--- Processing: {key} ---")
        try:
            local_pdf = download_single_pdf(key)
            header_data, df = extract_lab_data(local_pdf)

            # The ONE function that handles everything
            report_id = insert_lab_data(header_data, df, key)

            if report_id:
                print(f"Successfully processed: {key}")
            else:
                print(f"File not processed (failure/permanent): {key}")

        except Exception as e:
            print(f"Unexpected error for {key}: {e}")
            # Optional: force a failure record
            # insert_lab_data({}, None, key)
            continue

    print("\n========== BATCH COMPLETED ==========\n")

# ==============================
# ENTRY POINT
# ==============================
if __name__ == "__main__":
    while True:
        try:
            run_batch()
        except Exception as e:
            print(f"Fatal error in batch loop: {e}")
        print("\nWaiting 60 seconds before next run...\n")
        time.sleep(60)