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
# 🔥 NEW: BULK DB FETCH
# ==============================
def get_processed_files():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s3_path
            FROM dev.reports_upload_details
            WHERE upload_status_id IN (
                SELECT status_id FROM dev.status_details
                WHERE status_name IN ('success', 'permanent failed')
            )
        """)

        rows = cursor.fetchall()

        return set(r[0] for r in rows)

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
# MAIN BATCH PROCESS (THREADING)
# ==============================
def run_batch():
    BATCH_SIZE = 100
    batch_start = time.time()

    log("========== STARTING NEW BATCH ==========")

    # 🔥 Step 1: Fetch S3 files
    all_keys = list_pdfs_from_s3()

    # 🔥 Step 2: Get processed files (ONLY 1 DB CALL)
    processed_set = get_processed_files()

    # 🔥 Step 3: Filter in memory
    to_process = [k for k in all_keys if k not in processed_set]

    log(f"[BATCH] Total: {len(all_keys)} | To Process: {len(to_process)}")

    if not to_process:
        log("[BATCH] No files to process")
        return

    # Step 4: Take batch
    batch = to_process[:BATCH_SIZE]

    from extractor.thread_manager import run_threaded_batch

    # Step 5: Run threading
    run_threaded_batch(
        batch_keys=batch,
        safe_download=safe_download,
        log=log,
        max_workers=10
    )
    batch_end = time.time()   # 🔥 END

    log(f"[TOTAL BATCH TIME] {round(batch_end - batch_start, 2)} sec")
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