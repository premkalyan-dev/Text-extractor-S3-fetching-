from db.db_config import get_connection
import pandas as pd


def insert_lab_data(df):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT current_database();")
    print("Connected To DB:", cursor.fetchone()[0])

    try:
        # ======================================================
        # 1️⃣ LMS (Prevent duplicate category)
        # ======================================================
        category = df.iloc[0].get('Category')

        cursor.execute("""
            SELECT lmsid FROM public.lms WHERE name = %s
        """, (category,))
        lms = cursor.fetchone()

        if lms:
            Lmsid = lms[0]
        else:
            cursor.execute("""
                INSERT INTO public.lms (name)
                VALUES (%s)
                RETURNING lmsid
            """, (category,))
            Lmsid = cursor.fetchone()[0]

        # ======================================================
        # 2️⃣ LAB (Prevent duplicate lab)
        # ======================================================
        lab_name = "Default Lab"

        cursor.execute("""
            SELECT labid FROM public.lab
            WHERE labname = %s AND lmsid = %s
        """, (lab_name, Lmsid))

        lab = cursor.fetchone()

        if lab:
            labid = lab[0]
        else:
            cursor.execute("""
                INSERT INTO public.lab (labname, lmsid, createdate)
                VALUES (%s, %s, CURRENT_DATE)
                RETURNING labid
            """, (lab_name, Lmsid))
            labid = cursor.fetchone()[0]

        # ======================================================
        # 3️⃣ PATIENT (Auto Increment ID)
        # ======================================================
        patient_name = df.iloc[0].get('Patient_Name')

        cursor.execute("""
            INSERT INTO public.patient (name, age, gender, labid)
            VALUES (%s,%s,%s,%s)
            RETURNING patientid
        """, (
            patient_name,
            None,
            None,
            labid
        ))

        patient_id = cursor.fetchone()[0]

        # ======================================================
        # 4️⃣ LOOP THROUGH TEST ROWS
        # ======================================================
        for _, row in df.iterrows():

            test_group_name = row.get('Test Group')
            test_name = row.get('Test Name')

            min_range = row.get('Min Range')
            max_range = row.get('Max Range')
            result_value = row.get('Result')

            min_range = min_range if pd.notna(min_range) else None
            max_range = max_range if pd.notna(max_range) else None
            result_value = result_value if pd.notna(result_value) else None

            # ------------------------------------------
            # 4.1 TESTGROUP (Prevent duplicate)
            # ------------------------------------------
            cursor.execute("""
                SELECT testgroupid FROM public.testgroup
                WHERE testgroupname = %s AND lmsid = %s
            """, (test_group_name, Lmsid))

            tg = cursor.fetchone()

            if tg:
                testgroupid = tg[0]
            else:
                cursor.execute("""
                    INSERT INTO public.testgroup (testgroupname, lmsid)
                    VALUES (%s,%s)
                    RETURNING testgroupid
                """, (test_group_name, Lmsid))
                testgroupid = cursor.fetchone()[0]

            # ------------------------------------------
            # 4.2 TESTPARAMETER (Prevent duplicate)
            # ------------------------------------------
            cursor.execute("""
                SELECT testparameterid FROM public.testparameter
                WHERE parametername = %s AND testgroupid = %s
            """, (test_name, testgroupid))

            tp = cursor.fetchone()

            if tp:
                testparameterid = tp[0]
            else:
                cursor.execute("""
                    INSERT INTO public.testparameter (
                        lmsid,
                        testgroupid,
                        parametername,
                        ref_min_range,
                        ref_max_range,
                        age,
                        gender
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING testparameterid
                """, (
                    Lmsid,
                    testgroupid,
                    test_name,
                    min_range,
                    max_range,
                    None,
                    None
                ))
                testparameterid = cursor.fetchone()[0]

            # ------------------------------------------
            # 4.3 TESTRESULT (Idempotent Insert)
            # ------------------------------------------
            cursor.execute("""
                INSERT INTO public.testresult (patientid, testparameterid, resultvalue)
                VALUES (%s,%s,%s)
                ON CONFLICT (patientid, testparameterid)
                DO UPDATE SET resultvalue = EXCLUDED.resultvalue
            """, (
                patient_id,
                testparameterid,
                result_value
            ))

        # ======================================================
        # COMMIT TRANSACTION
        # ======================================================
        conn.commit()

        print("\nAll Data Inserted Successfully ✅")
        print("Patient ID:", patient_id)
        print("Patient Name:", patient_name)

    except Exception as e:
        conn.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        conn.close()