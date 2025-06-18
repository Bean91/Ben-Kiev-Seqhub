import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

neon_db = os.environ["NEON_DB"]

def get_db_connection():
    return psycopg2.connect(neon_db)

def create_chat_history_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    cursor.close()
    conn.close()

def insert_message(user_id, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (user_id, message) VALUES (%s, %s);",
        (user_id, message)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_history(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT message FROM chat_history WHERE user_id = %s ORDER BY created_at DESC;",
        (user_id,)
    )
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages