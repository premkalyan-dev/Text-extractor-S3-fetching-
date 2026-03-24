from db.db_config import get_connection

# ---------------- CREATE REPORT ENTRY ----------------
def create_report_entry(s3_path):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO dev.reports_upload_details
        (s3_path, upload_status_id, uploaded_at)
        VALUES (%s, 2, CURRENT_TIMESTAMP)
        RETURNING report_id
    """, (s3_path,))

    result = cursor.fetchone()

    if not result:
        conn.commit()
        cursor.close()
        conn.close()
        raise Exception("Failed to create report entry")

    report_id = result[0]

    conn.commit()

    cursor.close()
    conn.close()

    return report_id


# ---------------- GET PERMANENT FAILED ----------------
def get_permanent_failed():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s3_path
        FROM dev.reports_upload_details
        WHERE upload_status_id = 5
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [row[0] for row in rows]


# ---------------- MARK FAILED ----------------
def insert_failed_report(report_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE dev.reports_upload_details
        SET upload_status_id = 4
        WHERE report_id = %s
    """, (report_id,))

    conn.commit()

    cursor.close()
    conn.close()


# ---------------- MARK SUCCESS ----------------
def insert_success_report(report_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE dev.reports_upload_details
        SET upload_status_id = 3
        WHERE report_id = %s
    """, (report_id,))

    conn.commit()

    cursor.close()
    conn.close()


# ---------------- GET FAILED REPORTS ----------------
def get_failed_reports(limit=2):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.report_id, r.s3_path
        FROM dev.reports_upload_details r
        JOIN dev.patient_notification_details n
        ON r.report_id = n.report_id
        WHERE r.upload_status_id = 4
        AND n.retry_count < 3
        ORDER BY r.uploaded_at ASC
        LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


# ---------------- UPDATE RETRY ----------------
def update_retry(report_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE dev.patient_notification_details
        SET retry_count = retry_count + 1
        WHERE report_id = %s
        RETURNING retry_count
    """, (report_id,))

    result = cursor.fetchone()

    if not result:
        print("No retry record found for report:", report_id)
        conn.commit()
        cursor.close()
        conn.close()
        return

    retry_count = result[0]

    if retry_count >= 3:

        cursor.execute("""
            UPDATE dev.reports_upload_details
            SET upload_status_id = 5
            WHERE report_id = %s
        """, (report_id,))

    else:

        cursor.execute("""
            UPDATE dev.reports_upload_details
            SET upload_status_id = 4
            WHERE report_id = %s
        """, (report_id,))

    conn.commit()

    cursor.close()
    conn.close()


# ---------------- CLEAR FAILURE AFTER SUCCESS ----------------
def delete_failed(report_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE dev.reports_upload_details
        SET upload_status_id = 3
        WHERE report_id = %s
    """, (report_id,))

    conn.commit()

    cursor.close()
    conn.close()