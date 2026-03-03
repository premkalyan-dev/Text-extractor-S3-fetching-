from db.db_config import get_connection
conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT current_database();")
print("Connected To DB:", cursor.fetchone()[0])


def insert_lab_data(df):

    conn = get_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():

        cursor.execute("""
        INSERT INTO public.lab_results (
            patient_id,
            patient_name,
            category,
            test_group,
            test_name,
            result,
            unit,
            reference_range,
            method,
            min_range,
            max_range
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (

            row['Patient_ID'],
            row['Patient_Name'],
            row['Category'],
            row['Test Group'],
            row['Test Name'],
            row['Result'],
            row['Unit'],
            row['Reference Range'],
            row['Method'],
            row['Min Range'],
            row['Max Range']
        ))

    conn.commit()

    # 👉 Get Patient Info from first row
    patient_id = df.iloc[0]['Patient_ID']
    patient_name = df.iloc[0]['Patient_Name']

    print(f"\nPatient Data Inserted Successfully ✅")
    print(f"Patient ID: {patient_id}")
    print(f"Patient Name: {patient_name}")

    cursor.close()
    conn.close()