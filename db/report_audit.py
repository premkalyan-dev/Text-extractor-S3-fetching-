from db.db_config import get_connection


# ---------------- GET PERMANENT FAILED ----------------
def get_permanent_failed():
    """
    Returns list of s3_keys that are permanently failed
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s3_key
        FROM public.failed_reports
        WHERE status = 'permanent_failed'
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [row[0] for row in rows]


# ---------------- INSERT FAILED REPORT ----------------
def insert_failed_report(patient_name, key, error):
    """
    Insert a new failed report.
    Default retry_count = 0
    Default status = 'retrying'
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO public.failed_reports 
        (patient_name, s3_key, error_message, retry_count, status, last_attempt)
        VALUES (%s, %s, %s, 0, 'retrying', CURRENT_TIMESTAMP)
        ON CONFLICT (s3_key)
        DO NOTHING
    """, (patient_name, key, error))

    conn.commit()

    cursor.close()
    conn.close()


# ---------------- INSERT SUCCESS REPORT ----------------
def insert_success_report(patient_name, key):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO public.success_reports (patient_name, s3_key)
        VALUES (%s, %s)
        ON CONFLICT (s3_key)
        DO NOTHING
    """, (patient_name, key))

    conn.commit()
    cursor.close()
    conn.close()


# ---------------- GET FAILED REPORTS FOR RETRY ----------------
def get_failed_reports(limit=2):
    """
    Fetch only retryable reports.
    Permanent failed will NEVER be returned.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT patient_name, s3_key
        FROM public.failed_reports
        WHERE status != 'permanent_failed'
        ORDER BY last_attempt ASC
        LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


# ---------------- UPDATE RETRY COUNT ----------------
def update_retry(key):
    """
    Increase retry count.
    If retry_count >= 3 → mark as permanent_failed
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE public.failed_reports
        SET 
            retry_count = retry_count + 1,
            status = CASE 
                        WHEN retry_count + 1 >= 3 
                            THEN 'permanent_failed'
                        ELSE 'retrying'
                     END,
            last_attempt = CURRENT_TIMESTAMP
        WHERE s3_key = %s
        AND status != 'permanent_failed'
    """, (key,))

    conn.commit()

    cursor.close()
    conn.close()


# ---------------- DELETE FAILED AFTER SUCCESS ----------------
def delete_failed(key):
    """
    Remove from failed table once processing succeeds
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM public.failed_reports
        WHERE s3_key = %s
    """, (key,))

    conn.commit()

    cursor.close()
    conn.close()