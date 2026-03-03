import time
from old.s3_batch_fetch_old import run_batch

while True:
    print("\nRunning Batch Job...\n")
    run_batch()

    print("Waiting 10 seconds...\n")
    time.sleep(10)