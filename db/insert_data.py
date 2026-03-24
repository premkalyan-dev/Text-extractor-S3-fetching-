from db.db_config import get_connection
import pandas as pd
import uuid

# ======================================================
# STATUS HELPER FUNCTION
# ======================================================
def get_status_id(cursor, status_name):
    """Retrieve the status_id for a given status_name."""
    cursor.execute("""
        SELECT status_id
        FROM dev.status_details
        WHERE status_name = %s
    """, (status_name,))
    result = cursor.fetchone()
    if not result:
        raise Exception(f"Status not found: {status_name}")
    return result[0]

# ======================================================
# MAIN INSERT FUNCTION
# ======================================================
def insert_lab_data(header_data, df, s3_path):
    """
    Insert lab report data into the database.

    Args:
        header_data (dict): Contains patient info like "Patient Name", "Age", "Gender".
        df (DataFrame): Extracted test results with columns:
                        Test Group, Test Name, Result, Min Range, Max Range,
                        Reference Range, Method, Abnormal, Category.
        s3_path (str): S3 path of the original file.

    Returns:
        int or None: report_id if successful, None otherwise.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # --- Status IDs ---
        success_status = get_status_id(cursor, "success")
        failed_status = get_status_id(cursor, "failed")
        permanent_failed_status = get_status_id(cursor, "permanent failed")

        # --- 1. Check if file already processed ---
        cursor.execute("""
            SELECT report_id, retry_count, upload_status_id
            FROM dev.reports_upload_details
            WHERE s3_path = %s
        """, (s3_path,))
        existing = cursor.fetchone()

        if existing:
            report_id, retry_count, status_id = existing
            if status_id == success_status:
                print("Report already processed successfully.")
                return report_id
            if status_id == permanent_failed_status:
                print("Report is permanently failed. Skipping.")
                return None
            # Otherwise, it's a failed record that can be retried
        else:
            # First time seeing this file → create initial record
            cursor.execute("""
                INSERT INTO dev.reports_upload_details
                (lab_id, patient_id, s3_path, uploaded_at, upload_status_id, retry_count)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, 0)
                RETURNING report_id
            """, (None, None, s3_path, failed_status))
            report_id = cursor.fetchone()[0]
            retry_count = 0

        # --- 2. Handle extraction failure (empty or None df) ---
        if df is None or df.empty:
            new_retry = retry_count + 1
            if new_retry >= 4:
                new_status = permanent_failed_status
                print(f"File permanently failed after {new_retry} attempts.")
            else:
                new_status = failed_status
                print(f"Extraction failed, retry count now {new_retry}")

            cursor.execute("""
                UPDATE dev.reports_upload_details
                SET retry_count = %s,
                    upload_status_id = %s,
                    patient_id = NULL
                WHERE report_id = %s
            """, (new_retry, new_status, report_id))
            conn.commit()
            return None

        # --- 3. Extraction succeeded → handle patient details ---
        patient_name = header_data.get("Patient Name", "Unknown Patient")
        age = header_data.get("Age")
        gender = header_data.get("Gender")

        cursor.execute("""
            SELECT patient_id
            FROM dev.patients_details
            WHERE name = %s AND age = %s AND gender = %s
        """, (patient_name, age, gender))
        patient = cursor.fetchone()

        if patient:
            patient_id = patient[0]
        else:
            cursor.execute("""
                INSERT INTO dev.patients_details
                (lab_id, name, age, gender)
                VALUES (%s, %s, %s, %s)
                RETURNING patient_id
            """, (None, patient_name, age, gender))
            patient_id = cursor.fetchone()[0]

        # --- 4. Mark report as successful ---
        cursor.execute("""
            UPDATE dev.reports_upload_details
            SET upload_status_id = %s,
                patient_id = %s,
                retry_count = 0
            WHERE report_id = %s
        """, (success_status, patient_id, report_id))

        print("Report ID:", report_id)
        print("\nExtracted Tests Preview:")
        print(df[['Test Group', 'Test Name', 'Result', 'Abnormal']].head())

        # --- 5. Panel handling ---
        lab_id = None  # Adjust if lab_id is known
        category = df.iloc[0].get("Category", "General Panel")

        cursor.execute("""
            SELECT panel_id
            FROM dev.test_panel_details
            WHERE panel_name = %s AND lab_id = %s
        """, (category, lab_id))
        panel = cursor.fetchone()

        if panel:
            panel_id = panel[0]
        else:
            cursor.execute("""
                INSERT INTO dev.test_panel_details
                (panel_name, lab_id)
                VALUES (%s, %s)
                RETURNING panel_id
            """, (category, lab_id))
            panel_id = cursor.fetchone()[0]

        # --- 6. Insert each test result ---
        for _, row in df.iterrows():
            test_group_name = row.get("Test Group")
            test_name = row.get("Test Name")
            if not test_name:
                continue

            result_value = row.get("Result")
            min_range = row.get("Min Range")
            max_range = row.get("Max Range")
            method = row.get("Method")
            reference_range = row.get("Reference Range")
            abnormal = row.get("Abnormal", 0)

            cursor.execute("""
                INSERT INTO dev.patient_result_details
                (result_id, report_id, test_group, test_name,
                 result_value, min_range, max_range,
                 reference_range, method, abnormality_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                report_id,
                test_group_name,
                test_name,
                result_value,
                min_range,
                max_range,
                reference_range,
                method,
                abnormal
            ))

        conn.commit()
        print("All Data Inserted Successfully")
        return report_id

    except Exception as e:
        conn.rollback()
        # Check for duplicate S3 path constraint violation
        if "unique_s3_path" in str(e):
            print("Duplicate file detected:", s3_path)
            return None
        print("Database Error:", e)
        return None

    finally:
        cursor.close()
        conn.close()