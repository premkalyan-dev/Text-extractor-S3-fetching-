# Product Design and Requirement Document (PDR)

## 1. Document Purpose

This document explains the complete working of the `Text_extractor+db_main` project, including:

- what the project does
- how the folder is organized
- how the extractor works internally
- how to install all required dependencies
- how to configure AWS, PostgreSQL, and local paths
- how to run the project
- what database objects are required
- known risks and improvement areas

This PDR is based on the current project code in this repository.

## 2. Project Summary

### Project Name
DiagnoiQ Text Extractor + DB Pipeline

### Primary Objective
Fetch PDF lab reports from AWS S3, extract structured patient and lab-test data, and store the processed output in PostgreSQL.

### Main Business Use
Automate ingestion of pathology/lab reports so raw PDF reports become searchable structured records.

## 3. High-Level Workflow

The active runtime flow is:

1. `main.py` starts the batch process.
2. `main.py` calls `run_batch()` from `s3_batch.py`.
3. `s3_batch.py` reads AWS and local settings from `.env`.
4. It lists PDF files from the configured S3 bucket and prefix.
5. It checks the database to decide whether each file is:
   - new
   - already processed successfully
   - failed and retryable
   - permanently failed
6. Each selected PDF is downloaded to the local reports folder.
7. `extractor.extract_lab_data()` reads the PDF and returns:
   - `header_data` dictionary
   - `df` pandas DataFrame of extracted test rows
8. `db.insert_data.insert_lab_data()` inserts or updates the database records.
9. The pipeline marks the upload as success, failed, or permanent failed in the database.

## 4. Current Runtime Entry Points

### `main.py`
Single-run entry point.

Behavior:
- prints startup message
- imports `run_batch`
- executes one batch run

Run command:

```powershell
python main.py
```

### `scheduler.py`
Continuous polling entry point.

Behavior:
- calls `run_batch()`
- waits 30 seconds
- repeats forever

Run command:

```powershell
python scheduler.py
```

### `s3_batch.py`
Main orchestration module.

Behavior:
- loads AWS and local path config from `.env`
- creates S3 client using `boto3`
- lists PDF objects using S3 paginator
- checks DB status from `dev.reports_upload_details`
- downloads files locally
- calls extractor
- calls DB insert logic
- processes up to `BATCH_SIZE = 50` files per run

Note:
`s3_batch.py` also contains its own infinite loop under `if __name__ == "__main__":` with a 60-second delay. In normal usage, prefer `main.py` for one run and `scheduler.py` for continuous runs.

## 5. Folder Structure and Responsibility

### Root Files

| Path | Purpose |
|---|---|
| `main.py` | Starts one batch execution. |
| `scheduler.py` | Runs the batch continuously every 30 seconds. |
| `s3_batch.py` | Core orchestration for S3 listing, download, extraction, and database save. |
| `requirements.txt` | Python package dependencies. |
| `README.md` | Short repository overview. |
| `Howtorun.txt` | Short run notes. |
| `PDR.md` | Full design and requirements document. |
| `processed_files.json` | Legacy local tracking file. Not used by the current active path in `s3_batch.py`. |

### `extractor/`

This is the main extraction package used by the active pipeline.

| File | Purpose |
|---|---|
| `extractor/__init__.py` | Exposes `extract_lab_data`. |
| `extractor/core.py` | Main PDF extraction pipeline and DataFrame generation. |
| `extractor/header_extractor.py` | Reads patient/header data from the first page before the test table begins. |
| `extractor/bold_detector.py` | Detects bold numeric results to mark abnormal tests. |
| `extractor/column.py` | Detects test/result/unit/reference/method columns and builds boundaries. |
| `extractor/row_processor.py` | Scores headings, parses result values, and removes noise rows. |
| `extractor/utils.py` | Shared cleanup helpers such as range parsing and deduplication. |
| `extractor/processed_files.json` | Legacy/local artifact, not part of the active DB-driven orchestration. |

### `db/`

Database connection and insert logic.

| File | Purpose |
|---|---|
| `db/db_config.py` | PostgreSQL connection creation. |
| `db/insert_data.py` | Inserts patients, report records, panels, and test results. |
| `db/report_audit.py` | Extra audit helpers for failed/success/retry flows. Some logic appears older than the active `s3_batch.py` path. |

### `parser/`

| File | Purpose |
|---|---|
| `parser/pdf_extractor.py` | Older monolithic extractor implementation kept for reference/legacy use. |

### `old/`

| File | Purpose |
|---|---|
| `old/main_old.py` | Old entry point. |
| `old/sheduler.py` | Old scheduler version. |

## 6. Detailed Extractor Flow

The active extractor entry point is:

```python
from extractor import extract_lab_data
```

It is implemented in `extractor/core.py`.

### 6.1 Header Extraction

File: `extractor/header_extractor.py`

Function:
- `extract_header_until_testname(pdf_path)`

What it does:
- opens the first PDF page with `pdfplumber`
- groups words into lines
- reads lines until it finds the table header containing `test name`
- extracts left-side and right-side label-value pairs
- normalizes some fields such as:
  - `MR Number`
  - `Bill no`
  - `Age`
  - `Gender`
  - date/time fields like `Registered On`

Expected header examples:
- `Patient Name`
- `Age`
- `Gender`
- `MR Number`
- `Bill no`
- `Registered On`
- `Sample Collected On`
- `Sample Reported On`

Output:
- Python dictionary called `header_data`

### 6.2 Abnormal Value Detection

File: `extractor/bold_detector.py`

Function:
- `get_abnormal_tests(pdf_path)`

What it does:
- inspects PDF characters
- groups characters into words
- finds the likely result-value column
- detects bold numeric values
- maps those bold values to test names

Output:
- set of lowercase abnormal test names

This set is used later in `core.py` to set:
- `Abnormal = 1` for detected bold/abnormal tests
- `Abnormal = 0` otherwise

### 6.3 Table/Column Detection

File: `extractor/column.py`

Functions:
- `detect_columns`
- `build_header_based_intervals`
- `refine_intervals_with_gaps`

What they do:
- identify where `test`, `result`, `unit`, `ref`, and `method` columns start
- create x-axis boundaries for each column
- optionally improve the intervals using spacing/gap analysis from sample rows

This is important because PDF tables do not behave like normal CSV tables. The extractor must infer columns from text position.

### 6.4 Row Processing

File: `extractor/row_processor.py`

Functions:
- `heading_score`
- `hybrid_result_parser`
- `is_noise_row`

What they do:
- identify likely headings/category names
- extract numeric or textual result values
- ignore separators, signatures, footer text, and end-of-report lines

### 6.5 Common Cleanup Helpers

File: `extractor/utils.py`

Functions:
- `strip_page_markers`
- `parse_range_improved`
- `deduplicate_by_completeness`
- `contains_header_words`

Purpose:
- remove page markers like `Page 1 of 2`
- extract min/max values from reference ranges such as `4.0 - 10.5`
- remove duplicate extracted rows while keeping the most complete one
- filter rows that are actually table headers, not test rows

### 6.6 Main Test Row Extraction

File: `extractor/core.py`

Function:
- `extract_lab_data(file_path)`

Processing sequence:

1. Extract header fields using `extract_header_until_testname`.
2. Detect abnormal test names using `get_abnormal_tests`.
3. Open each page of the PDF using `pdfplumber`.
4. Find words and sort by vertical and horizontal position.
5. Detect the row that contains the table header.
6. Build column intervals.
7. Process each row and classify it as:
   - category heading
   - test group heading
   - continuation row
   - valid test row
   - noise row
8. Build row dictionaries with fields:
   - `Category`
   - `Test Group`
   - `Test Name`
   - `Result`
   - `Unit`
   - `Reference Range`
   - `Method`
   - `Abnormal`
9. Merge all pages into a final DataFrame.
10. Parse `Min Range` and `Max Range` from `Reference Range`.

Return value:

```python
header_data, final_df = extract_lab_data(file_path)
```

Returned DataFrame columns:

- `Category`
- `Test Group`
- `Test Name`
- `Result`
- `Unit`
- `Reference Range`
- `Method`
- `Min Range`
- `Max Range`
- `Abnormal`

## 7. Database Design Requirements

The active code expects PostgreSQL and uses schema `dev`.

### 7.1 Current Connection Settings

File: `db/db_config.py`

Current hardcoded values:

```python
host="localhost"
database="TablesScript"
user="postgres"
password="your_password"
port="5432"
```

Before running the project, update these values to match your PostgreSQL instance.

### 7.2 Required Tables Referenced by Current Code

The code currently references these database objects:

- `dev.status_details`
- `dev.reports_upload_details`
- `dev.patients_details`
- `dev.test_panel_details`
- `dev.patient_result_details`
- `dev.patient_notification_details`

### 7.3 Logical Use of Each Table

#### `dev.status_details`
Used to resolve numeric `status_id` values from names such as:
- `success`
- `failed`
- `permanent failed`

#### `dev.reports_upload_details`
Tracks each S3 report file.

Fields expected by current code:
- `report_id`
- `lab_id`
- `patient_id`
- `s3_path`
- `uploaded_at`
- `upload_status_id`
- `retry_count`

#### `dev.patients_details`
Stores patient master records.

Fields expected by current code:
- `patient_id`
- `lab_id`
- `name`
- `age`
- `gender`

#### `dev.test_panel_details`
Stores panel or category information.

Fields expected by current code:
- `panel_id`
- `panel_name`
- `lab_id`

#### `dev.patient_result_details`
Stores extracted test values.

Fields expected by current code:
- `result_id`
- `report_id`
- `test_group`
- `test_name`
- `result_value`
- `min_range`
- `max_range`
- `reference_range`
- `method`
- `abnormality_id`

#### `dev.patient_notification_details`
Used by `db/report_audit.py` for retry tracking.

Fields expected by current code:
- `report_id`
- `retry_count`

### 7.4 Important Note About Schema Ownership

The code assumes these tables already exist. This repository does not currently include SQL migration files for creating them, so the database schema must be provisioned separately before running the pipeline.

## 8. AWS and Environment Configuration Requirements

The active project loads environment variables with `python-dotenv`.

Create a `.env` file in the project root.

Recommended example:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-south-1
BUCKET_NAME=your_bucket_name
S3_PREFIX=your/folder/prefix/
LOCAL_DOWNLOAD_PATH=reports
```

### Variable Meaning

| Variable | Required | Purpose |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Yes | AWS access key for S3 download access. |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS secret key for S3 download access. |
| `AWS_REGION` | Yes | AWS region of the bucket. |
| `BUCKET_NAME` | Yes | Name of the S3 bucket. |
| `S3_PREFIX` | Yes | Folder-style prefix to search for PDF files. |
| `LOCAL_DOWNLOAD_PATH` | Yes | Local folder where PDFs will be downloaded. |

## 9. Full Dependency Installation Guide

### 9.1 Software Prerequisites

Install these before running the project:

- Python 3.10 or newer
- PostgreSQL
- Network access to AWS S3
- Windows PowerShell or terminal

### 9.2 Python Dependencies

Current `requirements.txt`:

- `pdfplumber`
- `pandas`
- `psycopg2-binary`
- `boto3`
- `python-dotenv`

### 9.3 Recommended Installation Steps on Windows

Open PowerShell in the project root and run:

```powershell
python --version
```

If Python is installed, create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install project dependencies:

```powershell
pip install -r requirements.txt
```

### 9.4 If Virtual Environment Activation Is Blocked

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 9.5 Verify Dependency Installation

Run:

```powershell
python -c "import pdfplumber, pandas, psycopg2, boto3, dotenv; print('Dependencies OK')"
```

Expected result:

```text
Dependencies OK
```

## 10. How to Configure and Run the Project

### Step 1: Open Project Folder

```powershell
cd "c:\Users\premk\OneDrive\Desktop\DiagnoiQ\Text_extractor+db_main"
```

### Step 2: Create `.env`

Add your AWS values:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=your_region
BUCKET_NAME=your_bucket
S3_PREFIX=your/prefix/
LOCAL_DOWNLOAD_PATH=reports
```

### Step 3: Update Database Connection

Edit `db/db_config.py` and set:

- host
- database
- user
- password
- port

### Step 4: Ensure Database Tables Exist

Make sure the `dev` schema tables referenced in Section 7 are already created.

### Step 5: Run One Batch

```powershell
python main.py
```

### Step 6: Run Continuous Scheduler

```powershell
python scheduler.py
```

## 11. What Happens During a Successful Run

For each processable PDF:

1. S3 object path is read from the bucket.
2. PDF is downloaded to `LOCAL_DOWNLOAD_PATH`.
3. Header fields are extracted.
4. Table data is parsed into structured rows.
5. Abnormal/bold tests are marked.
6. A report record is inserted or updated.
7. Patient details are inserted or reused.
8. Panel details are inserted or reused.
9. Test rows are inserted into `dev.patient_result_details`.
10. Report status is marked as `success`.

## 12. Failure and Retry Handling

The current code uses DB status tracking.

### Failure Cases

A file can fail if:
- S3 download fails
- the PDF is unreadable
- extractor returns no rows
- database insertion fails

### Retry Logic in Active Insert Path

Inside `db/insert_data.py`:
- if a report is new and extraction fails, a report entry is created with failed status
- retry count is incremented
- after 4 attempts, status changes to `permanent failed`

### Additional Audit Helper Logic

`db/report_audit.py` contains helper functions for:
- creating report entries
- updating failed/success states
- reading failed reports
- incrementing retry count

This file appears to represent an older or parallel retry-management path, because the active `s3_batch.py` currently relies mainly on `report_should_be_processed()` and `insert_lab_data()`.

## 13. Non-Functional Requirements

### Performance
- must process multiple PDF files in a batch
- must support paginated S3 listing
- must handle multi-page reports

### Reliability
- must avoid reprocessing successful files
- must mark repeated failures clearly
- must not stop the whole batch because one file fails

### Maintainability
- extraction logic should remain modular
- DB logic should remain separate from PDF parsing logic
- configuration should be externalized

### Data Quality
- extracted output should include category, test name, result, units, reference range, and abnormal flag whenever available
- duplicate rows should be reduced
- noise rows should be filtered

## 14. Current Gaps and Risks

These are important for deployment and future maintenance:

1. `db/db_config.py` uses hardcoded DB credentials instead of `.env`.
2. There is no SQL schema or migration script in the repository.
3. There are legacy files (`old/`, `parser/pdf_extractor.py`, `processed_files.json`) that can confuse maintainers.
4. `scheduler.py` and `s3_batch.py` both support looping, which creates duplicated scheduling behavior.
5. Logging uses `print()` statements only; there is no structured logging.
6. Error handling is basic and does not alert externally.
7. Some documentation files were behind the active code path before this PDR update.

## 15. Recommended Improvements

1. Move database configuration to `.env`.
2. Add SQL schema scripts or migration files.
3. Keep one scheduler mechanism only.
4. Add unit tests for extractor helper modules.
5. Add integration tests for PDF-to-DB flow.
6. Add structured logging.
7. Add sample `.env.example`.
8. Document expected database status values in seed SQL.

## 16. Quick Start Summary

If you need the shortest run path, do this:

1. Install Python and PostgreSQL.
2. Run `python -m venv .venv`.
3. Activate virtual environment.
4. Run `pip install -r requirements.txt`.
5. Create `.env` with AWS settings.
6. Update `db/db_config.py` with PostgreSQL credentials.
7. Ensure all required `dev` schema tables exist.
8. Run `python main.py`.

## 17. Acceptance Criteria

The project is considered correctly set up when:

- dependencies install without error
- AWS credentials can access the configured bucket/prefix
- PostgreSQL connection succeeds
- one PDF downloads successfully
- `extract_lab_data()` returns header data and test rows
- report status is stored in `dev.reports_upload_details`
- patient and result rows are inserted into the database

## 18. Conclusion

This repository is a modular PDF lab-report extraction pipeline built around:

- S3 ingestion
- PDF parsing with `pdfplumber`
- structured DataFrame generation with `pandas`
- PostgreSQL persistence with `psycopg2`

The `extractor/` folder is the main business logic layer, and the project can be run after installing Python dependencies, configuring AWS and PostgreSQL, and preparing the required database schema.
