from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from extractor import extract_lab_data
from db.insert_data import insert_lab_data


def process_single_file(item, safe_download, log):

    key = item["s3_key"]

    try:
        start_time = time.time()

        log(f"\nProcessing: {key}")

        # Download
        local_pdf = safe_download(key)
        if not local_pdf:
            return {"status": "failed", "key": key, "error": "Download failed"}

        # Extract
        header_data, df = extract_lab_data(local_pdf)

        # Insert
        report_id = insert_lab_data(header_data, df, key)

        end_time = time.time()

        return {
            "status": "success",
            "key": key,
            "time": round(end_time - start_time, 2),
            "rows": len(df)
        }

    except Exception as e:
        return {
            "status": "failed",
            "key": key,
            "error": str(e)
        }


def run_threaded_batch(batch_keys, safe_download, log, max_workers=5):

    file_map = [{"s3_key": key} for key in batch_keys]

    success = 0
    failed = 0

    log(f"\n🚀 Threading Started | Files: {len(file_map)}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = [
            executor.submit(process_single_file, item, safe_download, log)
            for item in file_map
        ]

        for future in as_completed(futures):
            result = future.result()

            if result["status"] == "success":
                success += 1
                log(f"✅ {result['key']} | {result['time']} sec | Rows: {result['rows']}")
            else:
                failed += 1
                log(f"❌ {result['key']} | {result['error']}")

    log("\n📊 Thread Summary")
    log(f"Success: {success}")
    log(f"Failed: {failed}")