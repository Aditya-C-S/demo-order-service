"""
simulate_processing.py — Realistic 35-Second Order Processing Workload.

Simulates long-running batch order validation and processing in CI/CD pipeline:
- Progressively emits structured log lines every 0.8–1.5s
- Features an intentional 6-second silence pause to test timer-based buffer flushing
- Accepts --fail (or FAILURE_STAGE=processing) to simulate mid-execution failure
- Flushes stdout continuously to ensure child-to-parent piping
"""

import argparse
import os
import sys
import time

TOTAL_BATCHES = 10


def main():
    parser = argparse.ArgumentParser(description="Simulate long-running batch order processing.")
    parser.add_argument("--fail", action="store_true", help="Simulate a processing failure mid-run")
    parser.add_argument("--batches", type=int, default=10, help="Number of batches to process")
    args = parser.parse_args()

    fail_env = os.environ.get("FAILURE_STAGE") in ("processing", "order_service") or os.environ.get("INJECT_PROCESSING_FAILURE") == "1"
    should_fail = args.fail or fail_env

    print("================================================================================")
    print("STARTING ORDER BATCH VALIDATION & SETTLEMENT PIPELINE")
    print("================================================================================")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"Total Batches Configured: {args.batches}")
    print("Worker Pool: 4 workers active (Python asyncio concurrent processor)")
    print("--------------------------------------------------------------------------------")
    sys.stdout.flush()
    time.sleep(1.0)

    for i in range(1, args.batches + 1):
        start_time = time.time()
        print(f"\n[Batch {i:02d}/{args.batches:02d}] Fetching pending transaction records from queue...")
        sys.stdout.flush()
        time.sleep(1.2)

        print(f"[Batch {i:02d}/{args.batches:02d}] Validating schema compliance (ISO 8583 message specs)...")
        print(f"[Batch {i:02d}/{args.batches:02d}] Verified 150 transaction headers: OK")
        print(f"[Batch {i:02d}/{args.batches:02d}] Verifying cryptographic checksums and digital signatures...")
        sys.stdout.flush()
        time.sleep(1.2)

        # Trigger controlled failure on batch 5 if requested
        if should_fail and i == 5:
            print("\n" + "=" * 70)
            print(f"[CRITICAL ERROR] Batch {i:02d} Integrity Check Failed!")
            print("Detected cryptographically invalid order payload checksum in item ORD-94821")
            print("=" * 70)
            print("Traceback (most recent call last):")
            print('  File "src/processor.py", line 142, in process_batch')
            print('    verify_payload_checksum(order_id="ORD-94821", checksum=expected_chk)')
            print('  File "src/validator.py", line 87, in verify_payload_checksum')
            print('    raise ValueError("Order processing validation failure: checksum mismatch")')
            print("ValueError: Order processing validation failure: checksum mismatch")
            print("##[error] Batch processing aborted with exit code 1")
            sys.stdout.flush()
            time.sleep(1.0)
            sys.exit(1)

        print(f"[Batch {i:02d}/{args.batches:02d}] Settlement ledger synchronized. Batch duration: {time.time() - start_time:.2f}s")
        sys.stdout.flush()

        # Intentional 6-second silence pause after Batch 4 to verify background timer flush
        if i == 4:
            print("\n>>> Entering 6-second settlement lock synchronization window (Testing Timer Flush) <<<")
            print(">>> Forwarder buffer should automatically flush due to elapsed time (>3.0s) <<<")
            sys.stdout.flush()
            time.sleep(6.0)
            print(">>> Lock synchronization complete. Resuming batch processing <<<\n")
            sys.stdout.flush()

        time.sleep(0.8)

    print("\n================================================================================")
    print("ALL BATCHES PROCESSED AND COMMITTED SUCCESSFULLY")
    print(f"Summary: {args.batches}/{args.batches} batches passed integrity check (0 errors)")
    print("================================================================================")
    sys.stdout.flush()
    time.sleep(1.0)
    sys.exit(0)


if __name__ == "__main__":
    main()
