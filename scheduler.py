import time
from s3_batch import run_batch

INTERVAL = 30   # 30 seconds

while True:
    print("\nRunning Batch Job...\n")
    try:
        run_batch()
    except Exception as e:
        print(f"Error: {e}")
    print(f"Waiting {INTERVAL} seconds...\n")
    time.sleep(INTERVAL)