# Product Design/Requirements Document (PDR)

## 1. Project Overview
**Project Name:** DiagnoiQ Text Extractor + DB Pipeline  
**Purpose:** Automatically fetch lab report PDFs from AWS S3, extract structured test data, and persist results/audit logs in PostgreSQL.

## 2. Goals
- Ingest new PDF lab reports from S3.
- Extract normalized test rows (test name, result, unit, reference range, method).
- Persist data into relational tables with basic dedup/idempotency handling.
- Track processing state (`processed`, `failed`, `retried`, `permanent_failed`).

## 3. Current File Structure and Responsibility

| Path | Type | Responsibility |
|---|---|---|
| `main.py` | Entrypoint | Runs one batch execution (`run_batch`). |
| `scheduler.py` | Scheduler | Runs `run_batch` continuously every 30s. |
| `s3_batch.py` | Orchestrator | S3 listing/download, retry flow, extraction, DB insert, processed-file tracking. |
| `requirements.txt` | Dependency list | Runtime Python dependencies. |
| `.env` | Config | AWS bucket/prefix/region/local download path. |
| `processed_files.json` | State store | Tracks already processed S3 keys. |
| `README.md` | Documentation | High-level repository summary. |
| `Howtorun.txt` | Runbook | Setup + execution instructions. |
| `db/db_config.py` | DB config | PostgreSQL connection factory (`get_connection`). |
| `db/insert_data.py` | DB writer | Inserts LMS/lab/patient/testgroup/testparameter/testresult data. |
| `db/report_audit.py` | Audit/retry | Maintains `failed_reports` and `success_reports` status lifecycle. |
| `extractor/core.py` | Extraction core | Page/table parsing pipeline and final DataFrame assembly. |
| `extractor/column.py` | Parsing helper | Header detection and column interval construction/refinement. |
| `extractor/row_processor.py` | Parsing helper | Heading scoring, result parsing, noise-row filtering. |
| `extractor/utils.py` | Parsing helper | Marker cleanup, range parsing, dedup helpers, header filtering. |
| `extractor/__init__.py` | Package API | Exposes `extract_lab_data`. |
| `parser/pdf_extractor.py` | Legacy parser | Older monolithic extraction implementation. |
| `reports/` | Data dir | Downloaded PDFs from S3. |
| `csv/`, `output.csv` | Data/output | CSV artifacts and outputs. |
| `old/` | Legacy scripts | Deprecated/older scripts. |

## 4. Runtime Components

### 4.1 Input Sources
- AWS S3 PDF objects under `BUCKET_NAME` + `S3_PREFIX`.
- Retry candidates from DB table `public.failed_reports`.

### 4.2 Processing Engine
- `extractor.extract_lab_data(file_path)` processes each PDF page.
- Dynamic table parsing with column detection and fallback interval strategy.
- Produces structured pandas DataFrame with min/max parsed from reference range.

### 4.3 Persistence Layer
- PostgreSQL via `psycopg2`.
- Audit tables for success/failure tracking.
- JSON key-store (`processed_files.json`) for idempotent S3 sync behavior.

## 5. End-to-End Workflow

1. `main.py` (or `scheduler.py`) invokes `s3_batch.run_batch()`.
2. `run_batch()` first fetches retryable failed reports (`get_failed_reports`).
3. For each retry key:
   - Download PDF from S3.
   - Run extraction.
   - If extraction fails: increment retry count (`update_retry`), eventually mark `permanent_failed` after 3 attempts.
   - If extraction succeeds: insert lab data, mark success, remove failed record, save key to `processed_files.json`.
4. List all PDFs from S3 prefix.
5. Exclude keys that are:
   - Already present in `processed_files.json`.
   - Marked `permanent_failed` in DB.
6. Process only `BATCH_SIZE` new files per run (current code: `BATCH_SIZE = 10`).
7. For each new file:
   - Download PDF to `reports/`.
   - Derive patient name from filename pattern.
   - Extract DataFrame from PDF.
   - If empty: add to `failed_reports`.
   - If valid: insert into DB tables (`lms`, `lab`, `patient`, `testgroup`, `testparameter`, `testresult`), mark success, and update `processed_files.json`.
8. Batch ends; scheduler waits 30s and repeats if running continuous mode.

## 6. Database Interaction Summary

### 6.1 Insert/Data Tables
- `public.lms` (upsert-like lookup/insert by category name)
- `public.lab` (lookup/insert by lab name + lms)
- `public.patient` (new row per processed report)
- `public.testgroup` (lookup/insert)
- `public.testparameter` (lookup/insert)
- `public.testresult` (idempotent upsert via `ON CONFLICT (patientid, testparameterid)`)

### 6.2 Audit Tables
- `public.failed_reports`
- `public.success_reports`

## 7. Configuration and Operational Controls

### 7.1 Environment Variables (`.env`)
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `BUCKET_NAME`
- `S3_PREFIX`
- `LOCAL_DOWNLOAD_PATH`

### 7.2 Hardcoded/Code-Level Controls
- Scheduler interval: `30` seconds (`scheduler.py`).
- Batch size: `10` files per run (`s3_batch.py`).
- Retry-to-permanent-failure threshold: `3` attempts (`db/report_audit.py`).

## 8. Failure Handling and Recovery
- Extraction failures are logged to `failed_reports` with status `retrying`.
- Retry attempts are prioritized before new files each run.
- Reports exceeding retry threshold are marked `permanent_failed` and skipped in future runs.
- Successful retry clears failed audit row and registers success.

## 9. Known Risks/Design Gaps (Current State)
- `db/db_config.py` uses hardcoded DB credentials (should be env-driven).
- `processed_files.json` is local and not shared across instances (not distributed-safe).
- S3 listing currently reads one response page (`list_objects_v2` without pagination loop).
- Patient identity is derived from filename pattern and may break for inconsistent names.
- Transaction handling prints errors but has limited structured logging/alerting.

## 10. Execution Modes
- Single run: `python main.py`
- Continuous polling: `python scheduler.py`

## 11. Suggested Next Enhancements
1. Move DB credentials to `.env` and secrets manager.
2. Add paginated S3 listing (`ContinuationToken`) support.
3. Replace local `processed_files.json` with DB-backed or object-store-backed state.
4. Add unit/integration tests for parser and DB insert flow.
5. Add structured logging and monitoring metrics.
