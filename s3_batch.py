import boto3
import os
import time
import requests
from dotenv import load_dotenv
from datetime import datetime

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

URL_EXPIRY = int(os.getenv("URL_EXPIRY", 60))

os.makedirs(LOCAL_DOWNLOAD_PATH, exist_ok=True)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com"
)

# ==============================
# LOGGER
# ==============================
def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

# ==============================
# DATABASE HELPERS
# ==============================
def get_status_id(cursor, status_name):
    cursor.execute(
        "SELECT status_id FROM dev.status_details WHERE status_name = %s",
        (status_name,)
    )
    return cursor.fetchone()[0]

def report_should_be_processed(s3_path):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT upload_status_id 
            FROM dev.reports_upload_details 
            WHERE s3_path = %s
        """, (s3_path,))
        row = cursor.fetchone()

        if not row:
            return True

        status_id = row[0]
        success = get_status_id(cursor, "success")
        permanent = get_status_id(cursor, "permanent failed")

        if status_id in (success, permanent):
            return False

        return True

    finally:
        cursor.close()
        conn.close()

# ==============================
# S3 HELPERS
# ==============================
def list_pdfs_from_s3():
    pdf_keys = []
    paginator = s3.get_paginator("list_objects_v2")

    log("Fetching PDFs from S3...")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf") and not key.endswith("/"):
                pdf_keys.append(key)

    return pdf_keys


def generate_presigned_url(key):
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=URL_EXPIRY
        )
    except Exception as e:
        log(f"[ERROR][URL] {key}: {e}")
        return None


def download_via_url(url, key):
    file_name = key.split("/")[-1]
    local_path = os.path.join(LOCAL_DOWNLOAD_PATH, file_name)

    try:
        # 🔥 Show clean URL (without signature)
        log(f"[PRESIGNED URL] {url}")

        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            return local_path
        else:
            log(f"[DOWNLOAD FAILED] {key} → {response.status_code}")
            return None

    except Exception as e:
        log(f"[ERROR][DOWNLOAD] {key}: {e}")
        return None


# ==============================
# SAFE DOWNLOAD (JIT + RETRY)
# ==============================
def safe_download(key):
    url = generate_presigned_url(key)
    if not url:
        return None

    local_pdf = download_via_url(url, key)
    if local_pdf:
        return local_pdf

    log(f"[RETRY] Regenerating URL → {key}")
    url = generate_presigned_url(key)
    return download_via_url(url, key)


# ==============================
# MAIN BATCH PROCESS
# ==============================
def run_batch():
    BATCH_SIZE = 100

    log("========== STARTING NEW BATCH ==========")

    all_keys = list_pdfs_from_s3()
    to_process = [k for k in all_keys if report_should_be_processed(k)]

    log(f"[BATCH] Total: {len(all_keys)} | To Process: {len(to_process)}")

    if not to_process:
        log("[BATCH] No files to process")
        return

    batch = to_process[:BATCH_SIZE]

    for key in batch:
        try:
            start_time = time.time()   # 🔥 START TIMER

            log(f"\nProcessing: {key}")

            # Download
            local_pdf = safe_download(key)
            if not local_pdf:
                continue

            # Extract
            header_data, df = extract_lab_data(local_pdf)

            if header_data:
                preview = dict(list(header_data.items())[:5])
                log(f"[EXTRACTED] {preview}")
            else:
                log("[EXTRACTED] No header data")

            # Insert
            report_id = insert_lab_data(header_data, df, key)

            if report_id:
                log("[DB INSERT] SUCCESS")
            else:
                log("[DB INSERT] FAILED")

            # 🔥 PROCESSING TIME
            end_time = time.time()
            log(f"[TIME] {round(end_time - start_time, 2)} sec")

        except Exception as e:
            log(f"[ERROR] {key}: {e}")
            continue

    log("========== BATCH COMPLETED ==========")


# ==============================
# ENTRY POINT
# ==============================
if __name__ == "__main__":
    while True:
        try:
            run_batch()
        except Exception as e:
            log(f"[FATAL ERROR]: {e}")

        log(f"Waiting {URL_EXPIRY} seconds...\n")
        time.sleep(URL_EXPIRY)