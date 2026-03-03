import boto3
import os
import time
import json
from dotenv import load_dotenv
from extractor import extract_lab_data
from db.insert_data import insert_lab_data
from db.report_audit import (
    insert_failed_report,
    insert_success_report,
    get_failed_reports,
    update_retry,
    delete_failed
)

load_dotenv()

# AWS Configuration
BUCKET_NAME = os.getenv("BUCKET_NAME", "diagnoiqailab-reports")
S3_PREFIX = os.getenv("S3_PREFIX", "labid/year/month/2/")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-2")

# Local paths
LOCAL_DOWNLOAD_PATH = os.getenv("LOCAL_DOWNLOAD_PATH", "reports")
os.makedirs(LOCAL_DOWNLOAD_PATH, exist_ok=True)

SYNC_FILE = "processed_files.json"

# S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION
)
from db.report_audit import (
    insert_failed_report,
    insert_success_report,
    get_failed_reports,
    update_retry,
    delete_failed,
    get_permanent_failed
)

# ---------------- JSON SYNC ----------------

def load_processed_files():
    if not os.path.exists(SYNC_FILE):
        return set()
    with open(SYNC_FILE, "r") as f:
        data = json.load(f)
    return set(data.get("processed_files", []))


def save_processed_file(key):
    processed = load_processed_files()
    processed.add(key)
    with open(SYNC_FILE, "w") as f:
        json.dump({"processed_files": list(processed)}, f, indent=4)

# ---------------- S3 ----------------

def list_pdfs_from_s3():
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=S3_PREFIX)
    pdf_keys = []
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if key.lower().endswith(".pdf") and not key.endswith("/"):
            pdf_keys.append(key)
    return pdf_keys


def download_single_pdf(key):
    file_name = key.split("/")[-1]
    local_path = os.path.join(LOCAL_DOWNLOAD_PATH, file_name)
    s3.download_file(BUCKET_NAME, key, local_path)
    return local_path

# ---------------- MAIN ----------------

def run_batch():

    BATCH_SIZE = 2

    print("\n================ RETRYING FAILED =================\n")

    # 🔁 RETRY FAILED REPORTS FIRST
    failed = get_failed_reports()

    for patient_name, key in failed:

        print(f"Retrying Failed File: {key}")

        local_pdf = download_single_pdf(key)
        df = extract_lab_data(local_pdf)

        if df is None or df.empty:
            print("Retry Failed Again\n")
            update_retry(key)
            continue

        insert_lab_data(df)
        insert_success_report(patient_name, key)
        delete_failed(key)
        save_processed_file(key)

        print("Recovered Successfully!\n")

    print("\n================ NEW FILES =================\n")

    all_keys = list_pdfs_from_s3()
    processed_keys = load_processed_files()
    permanent_failed = get_permanent_failed()

    new_files = [
        key for key in all_keys
        if key not in processed_keys
        and key not in permanent_failed
    ]

    print(f"Total PDFs in S3: {len(all_keys)}")
    print(f"Already Processed: {len(processed_keys)}")
    print(f"New Files Found: {len(new_files)}\n")

    if not new_files:
        print("Sync Up-to-Date. No new files to process.")
        return

    patient_id_counter = 1000
    batch = new_files[:BATCH_SIZE]

    for key in batch:

        print(f"\nProcessing File: {key}")
        total_start = time.time()

        # DOWNLOAD
        local_pdf = download_single_pdf(key)

        # PATIENT NAME
        file_name = os.path.basename(local_pdf)
        parts = file_name.replace(".pdf", "").split("_")
        patient_name = parts[1] + " " + parts[2] if len(parts) >= 3 else parts[0]

        # EXTRACT
        df = extract_lab_data(local_pdf)

        if df is None or df.empty:
            print("Extraction failed. Logging...\n")
            insert_failed_report(patient_name, key, "Extraction returned empty")
            continue

        df["Patient_ID"] = patient_id_counter
        df["Patient_Name"] = patient_name

        # INSERT + AUDIT
        insert_lab_data(df)
        insert_success_report(patient_name, key)

        save_processed_file(key)

        total_end = time.time()
        print(f"Total File Time: {total_end - total_start:.2f} sec")

        patient_id_counter += 1

    print("\nBatch Completed\n")