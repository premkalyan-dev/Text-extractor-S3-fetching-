from db.db_config import get_connection


# ---------------- PERMANENT FAILED ----------------

def get_permanent_failed():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s3_key
        FROM failed_reports
        WHERE status = 'permanent_failed'
    """)

    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows]

# ---------------- FAILED INSERT ----------------

def insert_failed_report(patient_name, key, error):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO failed_reports (patient_name, s3_key, error_message)
        VALUES (%s, %s, %s)
    """, (patient_name, key, error))

    conn.commit()
    conn.close()


# ---------------- SUCCESS INSERT ----------------

def insert_success_report(patient_name, key):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO success_reports (patient_name, s3_key)
        VALUES (%s, %s)
    """, (patient_name, key))

    conn.commit()
    conn.close()


# ---------------- GET FAILED ----------------

def get_failed_reports():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT patient_name, s3_key
    FROM failed_reports
    WHERE retry_count < 3
    ORDER BY last_attempt
    LIMIT 2
""")

    rows = cursor.fetchall()
    conn.close()

    return rows


# ---------------- UPDATE RETRY ----------------

def update_retry(key):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE failed_reports
    SET retry_count = retry_count + 1,
        status = CASE 
                    WHEN retry_count + 1 >= 3 THEN 'permanent_failed'
                    ELSE 'retrying'
                 END,
        last_attempt = CURRENT_TIMESTAMP
    WHERE s3_key = %s
""", (key,))

    conn.commit()
    conn.close()
    
    # ---------------- DELETE FAILED AFTER SUCCESS ----------------

def delete_failed(key):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM failed_reports
        WHERE s3_key = %s
    """, (key,))

    conn.commit()
    conn.close()