import psycopg2

def get_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="TablesScript",
        user="postgres",
        password="your_password",
        port="5432"
    )
    return conn