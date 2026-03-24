# Product Requirements Document (PRD)
## DiagnoiQ: Automated Lab Report Digitization & Data Pipeline

**Document Version:** 1.0  
**Last Updated:** March 23, 2026  
**Status:** Active Development  

---

## 1. Product Overview

**Product Name:** DiagnoiQ  

**Tagline:** Intelligent Lab Report Digitization Platform

**Description:**  
DiagnoiQ is an automated data pipeline that transforms unstructured lab reports (PDF format) into structured, queryable database records. The system fetches PDFs from cloud storage (AWS S3), intelligently extracts patient demographics and lab test results using advanced text parsing, cleans and standardizes the data, and ingests it into a PostgreSQL database—enabling labs and healthcare providers to eliminate manual data entry, reduce errors, and unlock insights from their diagnostic data.

---

## 2. Problem Statement

### Current Pain Points:
- **Manual Data Entry:** Lab reports arrive as PDFs, requiring staff to manually transcribe results into database systems—consuming 6-10 hours per 100 reports
- **High Error Rate:** Human transcription introduces ~2-3% data entry errors, leading to incorrect patient records and regulatory compliance risks
- **Slow Turnaround:** Delayed digitization of reports impacts clinical decision-making and patient care timelines
- **No Audit Trail:** Manual processes lack accountability and version history for regulatory audits (HIPAA, CAP)
- **Scalability Challenges:** As report volume grows, labs must hire more data-entry staff, increasing operational costs
- **Data Inconsistency:** Different staff transcribe data differently (unit normalization, range interpretation, typos)

### Business Impact:
- Increased operational costs (labor-intensive)
- Risk of patient harm due to data errors
- Regulatory compliance exposure
- Inability to perform analytics on historical data effectively

---

## 3. Objectives & Goals

### Primary Objectives:
1. **Automate report digitization** — Eliminate manual PDF-to-database data entry
2. **Ensure data accuracy** — Achieve >99% accuracy in extracted lab values
3. **Enable continuous processing** — Implement scheduled, unattended batch processing
4. **Maintain audit compliance** — Track all processed reports and failed attempts for regulatory audits
5. **Reduce time-to-insight** — Make lab data available in database within minutes of PDF receipt

### Success Goals (6–12 months):
- Process **10,000+ lab reports/month** with >99% accuracy
- Reduce manual data entry workload by **90%**
- Achieve **<5 minute** end-to-end processing time per report
- Maintain **99.5% uptime** for scheduled batch processing
- Support **10+ lab report formats** as new clients onboard
- Establish **zero unprocessed reports** in queue (fully automated catchup)

---

## 4. Target Users (Personas)

### Persona 1: Lab Technician / Data Entry Specialist  
**Pain Point:** Spending 6+ hours daily on repetitive PDF-to-database entry  
**Goals:** Reduce manual work, improve accuracy, focus on complex cases requiring judgment  
**Use Case:** Monitor dashboard to verify automated extractions, manually correct edge cases (5-10% of reports)  
**Needs:** Clear UI showing extraction confidence, easy override/correction interface  

### Persona 2: Lab Manager / Operations Director  
**Pain Point:** Managing staff scheduling, quality assurance, reporting delays  
**Goals:** Increase throughput, reduce staffing costs, improve SLA compliance  
**Use Case:** Monitor daily batch processing metrics, view success/failure rates, understand bottlenecks  
**Needs:** Dashboards, automated alerts on failures, weekly/monthly success metrics  

### Persona 3: Compliance Officer / Quality Assurance  
**Pain Point:** Auditing report processing for regulatory compliance (HIPAA, CAP)  
**Goals:** Maintain full audit trail, demonstrate controls, ensure data integrity  
**Use Case:** Query processed report history, verify extraction accuracy, review failed/corrected records  
**Needs:** Complete audit logs, before/after data comparison, compliance reports  

### Persona 4: Healthcare Provider / Clinician  
**Pain Point:** Need lab results available quickly for clinical decision-making  
**Goals:** Faster access to patient results, reliable data for diagnosis  
**Use Case:** Query patient lab history, access current results within minutes of report PDF arrival  
**Needs:** Fast, accurate data retrieval; reliable integration with EHR systems  

### Persona 5: System Administrator / DevOps  
**Pain Point:** Maintaining system uptime, monitoring S3 sync, handling processing failures  
**Goals:** Stable, self-healing system; minimal manual intervention  
**Use Case:** Monitor system health, manage S3 credentials, review logs, troubleshoot failures  
**Needs:** Robust logging, alerting, error retry mechanisms, easy deployment and scaling  

---

## 5. Features & Functional Requirements

### 5.1 Core Features

#### Feature 1: Automated S3 PDF Fetch & Sync  
**Priority:** HIGH  
**Description:** System automatically fetches new lab report PDFs from AWS S3 bucket at scheduled intervals.  
**Requirements:**
- Monitor S3 bucket for new PDF files matching configured patterns
- Implement idempotent processing (track processed files in `processed_files.json`)
- Retry failed downloads up to 3 times with exponential backoff
- Support multiple S3 buckets/paths via configuration
- Log all S3 operations for audit trail

**Acceptance Criteria:**
- ✓ New PDFs appear in processing queue within 5 minutes of upload to S3
- ✓ No duplicate processing of already-processed PDFs
- ✓ Failed downloads retry automatically; admin notified after 3rd failure
- ✓ Support for 500+ PDFs per batch run

---

#### Feature 2: Intelligent Text Extraction from PDFs  
**Priority:** HIGH  
**Description:** Extract structured data (patient info, lab results) from unstructured lab report PDFs.  
**Requirements:**
- Parse patient demographics (name, ID, DOB, gender, specimen type)
- Extract lab test result tables with high accuracy
- Detect and handle common PDF formatting variations
- Support tabular and semi-structured data formats
- Normalize units and reference ranges

**Acceptance Criteria:**
- ✓ Extract >95% of visible text from lab report PDFs
- ✓ Correctly identify patient identifiers in 99%+ of reports
- ✓ Parse lab result tables with column/row alignment accuracy >98%
- ✓ Process various report layouts without manual tuning

---

#### Feature 3: Advanced Text Parsing & Normalization  
**Priority:** HIGH  
**Description:** Clean, standardize, and normalize extracted text for database ingestion.  
**Sub-features:**
- **Column Detection:** Identify table columns (test name, result, unit, reference range, status)
- **Row Processing:** Parse each lab result row, extract values, handle special characters
- **Unit Normalization:** Convert variant units (mg/dL, mg/dl, MG/DL → mg/dL)
- **Reference Range Parsing:** Extract min/max bounds, handle symbol-based ranges (>, <, ≥)
- **Whitespace & Special Char Handling:** Clean extraneous spaces, line breaks, special characters
- **Bold/Emphasis Detection:** Mark clinically significant results (abnormal values)

**Acceptance Criteria:**
- ✓ Normalize 99%+ of test value units to standard format
- ✓ Correctly parse reference ranges from text (e.g., "0.5-1.5" → min:0.5, max:1.5)
- ✓ Flag abnormal results with >95% accuracy
- ✓ Handle empty cells, missing values, and special cases gracefully

---

#### Feature 4: Batch Processing with Scheduler  
**Priority:** HIGH  
**Description:** Run automated batch processing on configurable schedule (hourly, daily, etc.).  
**Requirements:**
- Trigger S3 fetch → extraction → database insert pipeline automatically
- Support cron-style scheduling (e.g., every 6 hours, daily at 2 AM)
- Graceful handling: skip processing if previous batch still running
- Comprehensive logging of each batch run (start time, duration, success/fail counts)
- Configurable batch size limits (e.g., process max 100 reports per run)

**Acceptance Criteria:**
- ✓ Batch processing runs reliably on schedule with <1% missed runs
- ✓ Complete batch of 100 reports in <10 minutes
- ✓ No overlap/concurrent execution of multiple batches
- ✓ Detailed logs available for every batch run

---

#### Feature 5: PostgreSQL Database Ingestion  
**Priority:** HIGH  
**Description:** Insert extracted and normalized lab results into PostgreSQL database with data validation.  
**Requirements:**
- Define database schema for patients, lab results, reference ranges, tests
- Insert lab results with automatic patient matching/creation
- Validate data integrity before insert (required fields, data types, value ranges)
- Handle duplicates (skip already-processed results)
- Maintain relational integrity (foreign keys, constraints)

**Acceptance Criteria:**
- ✓ Insert validated lab results with 100% success rate
- ✓ All patients and results accessible via SQL queries
- ✓ Database constraints prevent orphaned records
- ✓ Support querying patient history and trends

---

#### Feature 6: Failure Tracking & Audit Logging  
**Priority:** HIGH  
**Description:** Track processing failures, retry mechanisms, and maintain full audit trail for compliance.  
**Requirements:**
- Log all processed files with status (success, failed, retry)
- Capture failure reasons (parse error, DB error, format error)
- Store before/after data for comparison and verification
- Retry failed processing automatically (up to 3 attempts)
- Generate audit reports for regulatory compliance

**Acceptance Criteria:**
- ✓ Every processed report tracked with timestamp, status, extracting user/service
- ✓ Failed reports automatically retried; manual override available
- ✓ Audit trail queryable by date, patient, status, error type
- ✓ Compliance reports exportable for external audits

---

### 5.2 Secondary Features

#### Feature 7: Manual Correction/Override Interface  
**Priority:** MEDIUM  
**Description:** Allow data entry staff to review and correct extraction errors for edge cases.  
**Requirements:**
- Display extracted data alongside original PDF for verification
- Support manual editing of extracted values with version tracking
- Flag uncertain extractions (low confidence) for human review
- Capture correction metadata (who corrected, when, what changed)

**Acceptance Criteria:**
- ✓ Staff can review top 10% uncertain extractions daily
- ✓ Corrections saved with audit trail
- ✓ System learns from corrections to improve accuracy

---

#### Feature 8: Dashboard & Monitoring  
**Priority:** MEDIUM  
**Description:** Real-time visibility into batch processing status, success rates, and system health.  
**Requirements:**
- Display current batch status (running, pending, completed)
- Show success/failure metrics (daily, weekly, monthly)
- Alert on failures or performance issues
- Provide drill-down capability (view individual failed reports)

**Acceptance Criteria:**
- ✓ Dashboard loads in <2 seconds
- ✓ Auto-refresh every 30 seconds
- ✓ Alerts triggered within 2 minutes of failure

---

#### Feature 9: Report Export & Analytics  
**Priority:** MEDIUM  
**Description:** Generate operational and analytics reports for management and compliance.  
**Requirements:**
- Daily processing summary (reports processed, success rate, avg processing time)
- Patient lab history export (CSV, PDF)
- Batch processing audit report (detailed success/failure by batch)
- Trend analysis (accuracy over time, improved performance metrics)

**Acceptance Criteria:**
- ✓ Generate daily summary within 5 minutes of batch completion
- ✓ Export patient history in <30 seconds for 100+ records
- ✓ Audit reports available for external review

---

#### Feature 10: System Configuration Management  
**Priority:** MEDIUM  
**Description:** Allow admins to configure system behavior without code changes.  
**Requirements:**
- `.env` file for S3 credentials, DB connection, processing parameters
- Configurable batch schedules, size limits, retry policies
- Support multiple lab report formats (configuration-driven)
- Enable/disable features per deployment environment

**Acceptance Criteria:**
- ✓ All config changes take effect on next batch run
- ✓ Invalid configurations caught and logged at startup
- ✓ Secrets (API keys, passwords) never logged or exposed

---

#### Feature 11: Integration with External Systems  
**Priority:** LOW  
**Description:** Future integrations with EHR/LIS systems and clinical workflows.  
**Requirements:**
- REST API for querying patient lab results
- Webhook notifications when new results ingested
- HL7/FHIR export support (future phases)
- Direct DB access for analyst queries

**Acceptance Criteria:**
- ✓ REST API endpoints documented and tested
- ✓ API supports filtering by patient, date range, test type
- ✓ Rate limiting and authentication enforced

---

#### Feature 12: Multi-Format Report Support  
**Priority:** LOW  
**Description:** Support multiple lab report formats (hospital A's format, lab B's format, etc.).  
**Requirements:**
- Configuration-driven format definitions
- Extensible parser for new formats
- Format auto-detection (machine learning, future)
- Version control for format definitions

**Acceptance Criteria:**
- ✓ Add new format support in <2 hours (config-driven)
- ✓ Support 5+ distinct lab report formats in Phase 1
- ✓ Accuracy consistent across all supported formats

---

## 6. User Flow / Use Cases

### Use Case 1: Automatic Daily Report Processing (Happy Path)  
**Actor:** System (automated)  
**Precondition:** Scheduler triggers batch job; new PDFs in S3 bucket  
**Flow:**
1. System checks S3 bucket for new PDF files
2. Downloads new PDFs not in `processed_files.json`
3. For each PDF:
   - Extracts patient name, demographics
   - Parses lab result tables
   - Normalizes units and reference ranges
   - Validates data integrity
   - Inserts into PostgreSQL (patient + results)
4. Updates `processed_files.json` with processed file keys
5. Generates processing summary log
6. Sends completion notification

**Result:** Lab results available in database within 5 minutes; staff notified of success

---

### Use Case 2: Manual Verification & Correction  
**Actor:** Lab Technician  
**Precondition:** System flagged low-confidence results; daily batch completed  
**Flow:**
1. Technician logs in to dashboard
2. Views "Review Flagged Results" queue (top 10 uncertain extractions)
3. Selects flagged result, views extracted data + original PDF side-by-side
4. Identifies error: test value was "2.5" but extracted as "25"
5. Clicks "Edit Result", corrects value to "2.5"
6. System saves correction with metadata (user, timestamp, change log)
7. Correction synced to database
8. System logs correction for audit trail

**Result:** Accurate data in database; error logged for ML improvement

---

### Use Case 3: Failure Investigation & Retry  
**Actor:** Lab Manager / System Administrator  
**Precondition:** Batch processing failed for 5 reports; alert generated  
**Flow:**
1. Admin receives alert: "5 reports failed in batch_2024_03_23_14h"
2. Logs into dashboard, views failed batch details
3. Sees failures: 2 parse errors (malformed PDF), 3 DB constraints (duplicate patients)
4. Clicks "Retry Failed Reports"
5. System attempts reprocessing with updated handling logic
6. 3 DB-failure reports succeed; 2 parse errors remain (manual intervention needed)
7. Admin exports failed report PDFs for manual inspection
8. Reviews PDF to understand parse error; may require new format support

**Result:** 3 reports recovered automatically; root cause identified for 2 failures

---

### Use Case 4: Compliance Audit & Reporting  
**Actor:** Compliance Officer  
**Precondition:** Annual audit scheduled; need to verify lab report digitization controls  
**Flow:**
1. Officer generates audit report: "All DiagnoiQ Processed Reports (Jan-Mar 2026)"
2. System exports: 45,230 processed reports with metadata (date, status, processing time, errors)
3. Officer queries subset: "All reports processed by John Smith on March 15"
4. System displays: 342 reports processed, 99.8% success rate, 2 manual corrections
5. Officer spot-checks 10 random reports (before/after comparison)
6. Verifies extraction accuracy, no data loss, audit trail complete
7. Generates compliance certification

**Result:** Audit completed; controls validated; compliance maintained

---

### Use Case 5: Performance Analysis & Optimization  
**Actor:** System Administrator / Engineering  
**Precondition:** Processing performance degrading; need to understand bottleneck  
**Flow:**
1. Admin observes: Average processing time per report increased from 3s → 7s
2. Reviews batch logs by component:
   - S3 fetch: 0.2s/report (normal)
   - PDF extraction: 2s/report (normal)
   - Text parsing: 3.5s/report (degraded, was 1.5s)
   - DB insert: 0.3s/report (normal)
3. Identifies: Text parsing slower; likely due to more complex report format
4. Checks recent reports; confirms new hospital format contributes to slowdown
5. Optimizes parsing logic for new format; re-tests
6. Processing time returns to 3s/report

**Result:** Performance issue identified and resolved

---

## 7. UI/UX Requirements

### 7.1 User Interface Components

#### Dashboard (Main)
- **Purpose:** Overview of system health and batch processing status
- **Components:**
  - Status banner: "Last batch: 2 hours ago | Status: ✓ Success (342 reports processed)"
  - Metrics cards: Total processed, Success rate (%), Failures (count), Avg time/report
  - Chart: 7-day success trend (line chart)
  - Recent batches: Table with timestamp, report count, success/failure count, duration, action buttons

#### Flagged Results Review Queue
- **Purpose:** Technician review and correction of uncertain extractions
- **Components:**
  - List of flagged results (date, patient name, test name, confidence score)
  - Detail view: Original PDF (left), extracted data (right, editable), confidence score
  - Edit mode: Inline editing of extracted values with save/cancel buttons
  - Notes field: Technician can document reason for correction
  - Approve/Skip/Reject buttons

#### Failed Reports Details
- **Purpose:** Investigate and resolve processing failures
- **Components:**
  - Filter/search: by date, status, error type
  - Table: S3 key, error type, error message, retry count, last attempt time
  - Detail view: Full error stack trace, download original PDF, manual retry button
  - Bulk actions: Retry failed, export for manual processing, mark as DNP (do not process)

#### Audit & Compliance Report
- **Purpose:** Generate audit trails and compliance reports
- **Components:**
  - Filters: Date range, report status, processed by (user), test type
  - Report builder: Select metrics (success rate, processing time, error types, corrections)
  - Export: Download as CSV, PDF
  - Verification: Show sample records with before/after data comparison

### 7.2 Design Principles
- **Simplicity:** Focus on essential information; avoid data overload
- **Clarity:** Use clear labels, consistent terminology, intuitive navigation
- **Efficiency:** Keyboard shortcuts for power users, bulk actions, minimal clicks for common tasks
- **Safety:** Confirmation dialogs for destructive actions (retry, overwrite), undo capability
- **Accessibility:** WCAG 2.1 AA compliance, keyboard navigation, screen reader support

### 7.3 Mobile/Responsive
- **Primary:** Desktop web app (1920+ width optimal)
- **Secondary:** Tablet-responsive dashboard for quick status checks
- **Mobile:** Not required in Phase 1; future scope

---

## 8. Technical Requirements

### 8.1 Tech Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Language** | Python | 3.10+ | Data processing, ML-ready, existing codebase |
| **PDF Processing** | pdfplumber | Latest | Robust PDF text extraction, table detection |
| **Data Processing** | pandas | 2.0+ | DataFrames, data manipulation, CSV export |
| **Database** | PostgreSQL | 14+ | Relational data, ACID compliance, audit trails |
| **DB Driver** | psycopg2-binary | Latest | Python PostgreSQL adapter, production-grade |
| **Cloud Storage** | AWS S3 | — | Scalable, reliable, cost-effective |
| **AWS SDK** | boto3 | Latest | S3 operations (list, get, delete) |
| **Environment** | python-dotenv | Latest | Configuration management (secrets, credentials) |
| **Scheduling** | APScheduler (future) | 3.10+ | Lightweight job scheduling (alternative: Celery + Redis for scale) |
| **Logging** | Python logging + ELK (future) | — | Centralized logging for debugging, monitoring |
| **Web Framework** | Flask/FastAPI (future) | — | REST API, dashboard backend |
| **Frontend** | React / Vue.js (future) | — | Interactive dashboard, modern UX |

### 8.2 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                       │
│  (Dashboard, Review Queue, Audit Reports - Web App)          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                   API LAYER (REST)                           │
│   (Flask/FastAPI - GET/POST endpoints)                       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              BUSINESS LOGIC LAYER                            │
│  ┌──────────────┬──────────────┬──────────────┐              │
│  │  S3 Fetch    │  Extraction  │  Validation  │   DB         │
│  │  & Sync      │  & Parsing   │  & Insert    │  Insert      │
│  │  (s3_batch)  │  (extractor) │  (db/**)     │              │
│  └──────────────┴──────────────┴──────────────┘              │
│  ┌──────────────────────────────────────────────┐            │
│  │         SCHEDULER (Batch trigger)             │            │
│  └──────────────────────────────────────────────┘            │
└────────────┬─────────────────────┬──────────────┬────────────┘
             │                     │              │
        ┌────▼────┐  ┌─────────────▼──┐  ┌───────▼────┐
        │ AWS S3  │  │  PostgreSQL    │  │  Local     │
        │ Buckets │  │  Database      │  │  State     │
        │ (PDF)   │  │  (Results)     │  │  (.json)   │
        └─────────┘  └────────────────┘  └────────────┘

External Integrations (Phase 2+):
┌─────────────────────────────────────────────────────┐
│ EHR Systems (HL7/FHIR), LIS, Analytics Platforms    │
└─────────────────────────────────────────────────────┘
```

### 8.3 API Specifications (Future - Phase 2)

**Endpoints (examples):**
- `GET /api/v1/batches` — List recent batch runs
- `GET /api/v1/batches/{batch_id}/results` — Get results from specific batch
- `GET /api/v1/patients/{patient_id}/lab_results` — Patient lab history
- `POST /api/v1/results/{result_id}/corrections` — Submit correction
- `GET /api/v1/audit/logs?date_from=X&date_to=Y` — Audit log export

**Authentication:** API key + JWT tokens (Phase 2)

---

## 9. Data Requirements

### 9.1 Database Schema

```sql
-- Core Tables
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(50) UNIQUE NOT NULL,  -- Hospital ID
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    dob DATE,
    gender VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lab_tests (
    id SERIAL PRIMARY KEY,
    test_code VARCHAR(50) UNIQUE NOT NULL,
    test_name VARCHAR(200),
    unit VARCHAR(50),
    ref_range_min NUMERIC,
    ref_range_max NUMERIC,
    ref_range_text VARCHAR(200),  -- If non-numeric (e.g., "Negative")
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lab_results (
    id SERIAL PRIMARY KEY,
    patient_id INT NOT NULL REFERENCES patients(id),
    test_id INT NOT NULL REFERENCES lab_tests(id),
    result_value VARCHAR(100),  -- Raw value (may be text)
    result_numeric NUMERIC,      -- Parsed numeric value
    unit VARCHAR(50),
    is_abnormal BOOLEAN,
    specimen_type VARCHAR(50),
    test_date DATE,
    report_date DATE,
    source_file VARCHAR(255),    -- S3 key
    extraction_confidence NUMERIC,  -- 0-100%
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    corrected_at TIMESTAMP,
    corrected_by VARCHAR(100)
);

-- Audit Tables
CREATE TABLE processing_audit (
    id SERIAL PRIMARY KEY,
    s3_key VARCHAR(500) UNIQUE NOT NULL,
    batch_id VARCHAR(50),
    status VARCHAR(20),  -- 'success', 'failed', 'retry'
    error_message TEXT,
    retry_count INT DEFAULT 0,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_by VARCHAR(100)  -- 'system', user name, etc.
);

CREATE TABLE correction_history (
    id SERIAL PRIMARY KEY,
    result_id INT NOT NULL REFERENCES lab_results(id),
    original_value VARCHAR(100),
    corrected_value VARCHAR(100),
    reason TEXT,
    corrected_by VARCHAR(100),
    corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE batch_runs (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) UNIQUE,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    total_reports INT,
    successful INT,
    failed INT,
    status VARCHAR(20),  -- 'running', 'completed', 'failed'
    error_summary TEXT
);

-- Indexes
CREATE INDEX idx_patient_id ON lab_results(patient_id);
CREATE INDEX idx_test_date ON lab_results(test_date);
CREATE INDEX idx_source_file ON lab_results(source_file);
CREATE INDEX idx_batch_id ON processing_audit(batch_id);
```

### 9.2 Data Flow / Processing

```
S3 PDF
  ↓
[Extract text via pdfplumber]
  ↓
Raw text (unstructured)
  ↓
[Parse patient info, table structure]
  ↓
Patient demographics, raw lab results
  ↓
[Normalize units, parse values, detect abnormals]
  ↓
Structured lab results (patient, test, value, unit, range)
  ↓
[Validate: required fields, data types, ranges]
  ↓
Valid results ready for DB
  ↓
[Insert into PostgreSQL, update audit]
  ↓
Database (lab_results, patients, processing_audit)
```

### 9.3 Data Quality Requirements
- **Completeness:** All required fields (patient ID, test name, value, date) present
- **Accuracy:** Numeric values within expected ranges; units standardized
- **Consistency:** Patient records deduplicated; test codes consistent
- **Timeliness:** Results in database within 5 minutes of PDF upload
- **Integrity:** No orphaned records; relational constraints enforced

---

## 10. Constraints & Assumptions

### 10.1 Technical Constraints
- **PDF Formats:** Initially supports PDF format only (not scanned images; future OCR in Phase 2)
- **Performance:** Must process 100+ reports per batch in <10 minutes
- **Scalability:** Single-instance PostgreSQL (future: multi-region + read replicas in Phase 3)
- **Cost:** Must operate within AWS budget (S3 <$100/mo, RDS <$200/mo estimated)
- **Storage:** PDFs retained for 90 days; older reports archived

### 10.2 Regulatory & Compliance Constraints
- **HIPAA:** All PHI encrypted in transit (HTTPS) and at rest; audit logs immutable
- **CAP (College of American Pathologists):** Maintain processing documentation, version control
- **Data Retention:** Lab results retained for 7 years; audit logs for 5 years
- **Access Control:** Role-based access (read-only technician, admin, compliance officer)
- **Incident Response:** Data breach notification within 60 days if required

### 10.3 Operational Assumptions
- **S3 Availability:** AWS S3 is reliable; assume <0.1% data loss
- **Database Availability:** PostgreSQL operational 99.5% of time (planned maintenance windows)
- **Report Format Stability:** New lab report formats can be added without code changes (config-driven)
- **User Behavior:** Staff work 8 AM–6 PM; batch processing happens on-demand + scheduled
- **Volume Growth:** Linear growth from 5K to 50K reports/month over 24 months

### 10.4 Business Assumptions
- **Client Base:** Hospitals, diagnostic labs, healthcare providers (100+ potential clients)
- **Pricing Model:** SaaS (per-report processed or monthly subscription)
- **Team:** 1 product manager, 2 engineers (1 full-stack, 1 DevOps), 1 QA initially
- **Timeline:** MVP (Phase 1) ready in 6 months; Phase 2 (API, integrations) in 12 months

---

## 11. Success Metrics (KPIs)

### 11.1 Operational Metrics (System Health)

| Metric | Target | Measurement | Frequency |
|--------|--------|-------------|-----------|
| **Batch Completion Rate** | >99.5% | (Successful batches / Total scheduled) × 100 | Daily |
| **Processing Success Rate** | >99% | (Processed reports / Total reports in batch) × 100 | Per batch |
| **Avg Time per Report** | <5 sec | Total batch time ÷ report count | Per batch |
| **Data Extraction Accuracy** | >99% | Spot-check 50 randomly; verify against source | Weekly |
| **System Uptime** | >99.5% | Uptime / Total time × 100 | Monthly |
| **Failed Report Auto-Retry Rate** | >85% | (Recovered via retry / Failed) × 100 | Weekly |

### 11.2 Business Metrics (ROI & Adoption)

| Metric | Target | Measurement | Frequency |
|--------|--------|-------------|-----------|
| **Manual Data Entry Reduction** | >90% | Hours/month before vs. after | Monthly |
| **Cost per Report Processed** | <$0.50 | Total operational cost ÷ reports | Monthly |
| **Error Rate (before/after)** | <0.1% | Data entry errors / reports processed | Monthly |
| **Time to Report Availability** | <5 min | Time from PDF upload to DB query result | Per batch |
| **Customer Satisfaction** | >4.5/5 | NPS survey with lab staff | Quarterly |
| **On-time SLA Compliance** | >99% | Reports processed by deadline | Monthly |

### 11.3 Quality Metrics (Data Integrity)

| Metric | Target | Measurement | Frequency |
|--------|--------|-------------|-----------|
| **Data Completeness** | 100% | Required fields present for all records | Per batch |
| **Duplicate Detection Rate** | 100% | No duplicate processing of same report | Continuous |
| **Correction Override Rate** | <10% | Manual corrections / processed reports | Weekly |
| **Unit Normalization Success** | >99% | Successfully normalized unit formats | Per batch |
| **Reference Range Parsing** | >98% | Correctly parsed min/max bounds | Per batch |

### 11.4 Compliance Metrics

| Metric | Target | Measurement | Frequency |
|--------|--------|-------------|-----------|
| **Audit Log Completeness** | 100% | All processed reports traceable in logs | Daily |
| **Audit Trail Immutability** | 100% | No logs deleted/modified after creation | Continuous |
| **Compliance Report Generation** | <1 hr | Time to generate audit report on demand | Per audit |
| **Data Retention Compliance** | 100% | All retained data per regulatory policy | Quarterly |
| **Incident Response Time** | <4 hrs | Time to identify and contain data issues | Per incident |

---

## 12. Future Scope / Enhancements

### Phase 2 (Months 7–12)
1. **REST API for External Integration**
   - Enable EHR/LIS systems to query results
   - Webhook notifications on new results
   - Rate limiting, authentication, versioning

2. **Dashboard & Monitoring**
   - Real-time batch status UI
   - Performance analytics and trending
   - Alert management (email, SMS, Slack)

3. **Multi-Format Support**
   - Configuration-driven format definitions
   - Format auto-detection (ML-based)
   - Support 5+ lab report formats

4. **Advanced Reporting**
   - Patient lab history export (PDF, HL7)
   - Batch audit reports (compliance)
   - Performance trending and forecasting

5. **Enhanced Error Handling**
   - Automated duplicate detection and deduplication
   - Smart retry strategies (backoff, exponential)
   - Manual override interface for uncertain results

### Phase 3 (Months 13–24)
1. **OCR for Scanned Reports**
   - Support scanned PDFs (images) with OCR
   - Confidence scoring for OCR'd text
   - Fallback to manual verification

2. **Machine Learning Improvements**
   - Format auto-detection without config
   - Anomaly detection (unusual result values)
   - Predictive quality scoring

3. **Scalability & Performance**
   - Multi-region deployment
   - Read replicas for analytics queries
   - Celery + Redis for distributed job processing

4. **HL7/FHIR Export**
   - Export results in HL7 ADT, ORU messages
   - FHIR Observation resources
   - Integration with healthcare IT ecosystems

5. **Security Enhancements**
   - End-to-end encryption for PHI
   - Multi-factor authentication (MFA)
   - Role-based access control (RBAC) with fine-grained permissions
   - Compliance certifications (SOC 2, HIPAA Business Associate Agreement)

### Phase 4+ (24+ months)
- Mobile app for technician verification on-the-go
- Predictive analytics (patient health trends)
- AI-assisted diagnosis support (future compliance/regulatory review)
- White-label SaaS platform for resale
- Global expansion (support multiple languages, global lab standards)

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **PHI** | Protected Health Information (patient data regulated under HIPAA) |
| **S3** | Amazon Simple Storage Service (cloud object storage) |
| **API** | Application Programming Interface (enables system communication) |
| **PostgreSQL** | Relational database management system |
| **pdfplumber** | Python library for extracting text and tables from PDFs |
| **HIPAA** | Health Insurance Portability and Accountability Act (US privacy law) |
| **CAP** | College of American Pathologists (lab accreditation standard) |
| **Batch Processing** | Processing multiple reports in one scheduled run |
| **Idempotent** | Operation with same result regardless of repetitions |
| **Audit Trail** | Complete record of all system actions for compliance |
| **Reference Range** | Normal range of test values (min–max bounds) |
| **Abnormal Result** | Test value outside reference range (flags clinically significant finding) |

---

## Appendix B: Open Questions & Decisions Pending

1. **OCR Strategy:** When should scanned PDFs (images) be supported? Phase 2 or later?
2. **HL7/FHIR:** Which message types should be prioritized for integration (ADT, ORU, LRI)?
3. **Scaling Model:** At what report volume should we migrate from single-instance to distributed architecture?
4. **Pricing Model:** Per-report, monthly subscription, or hybrid?
5. **Data Retention:** Should we support hot archive in S3 Glacier after 90 days?

---

**Document Owner:** Senior Product Manager  
**Last Review Date:** March 23, 2026  
**Next Review Date:** June 23, 2026 (Quarterly Review)  
**Status:** Ready for Development Team Review  
