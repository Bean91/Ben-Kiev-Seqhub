import os, psycopg2, secrets
from dotenv import load_dotenv

load_dotenv()

neon_db = os.environ["NEON_DB"]

def get_db_connection():
    return psycopg2.connect(neon_db)

def clear_chat_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE chat_history;")
    conn.commit()
    cursor.close()
    conn.close()

def create_chat_history_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            chat_id VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ai boolean DEFAULT FALSE
        );
        """
    )
    conn.commit()
    cursor.close()
    conn.close()

def email_to_username(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username FROM users WHERE email = %s;",
        (email,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def insert_message(user_id, chat_id, message, ai):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (user_id, chat_id, message, ai) VALUES (%s, %s, %s, %s);",
        (user_id, chat_id, message, ai)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_history(user_id, chat_id, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT message FROM chat_history WHERE user_id = %s AND chat_id = %s ORDER BY created_at DESC LIMIT %s;",
        (user_id, chat_id, limit)
    )
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages

def get_user_password(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password FROM users WHERE username = %s;",
        (username,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def get_user_name(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT first_name, last_name FROM users WHERE username = %s;",
        (username,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result if result else None

def create_user_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER NOT NULL,
            username VARCHAR(255) UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            first_name VARCHAR(255) NOT NULL,
            last_name VARCHAR(255) NOT NULL,
            total_tokens INTEGER DEFAULT 0,
            session_token TEXT
        );
        """
    )
    conn.commit()
    cursor.close()
    conn.close()

def create_user(username, hashed_password, email, first_name, last_name):
    user_id = secrets.token_urlsafe(32)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (id, username, password, email, first_name, last_name, session_token) VALUES (%s, %s, %s, %s, %s, %s, %s);",
        (user_id, username, hashed_password, email, first_name, last_name, "N/A")
    )
    conn.commit()
    cursor.close()
    conn.close()

def store_session(session_token, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET session_token = %s WHERE username = %s;",
        (session_token, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_session_user(session_token):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username FROM users WHERE session_token = %s;",
        (session_token,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def update_tokens(username, tokens):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET total_tokens = total_tokens + %s WHERE username = %s;",
        (tokens, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_user(current_user, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET username = %s WHERE username = %s;",
        (username, current_user)
    )
    cursor.execute(
        "UPDATE chat_history SET user_id = %s WHERE user_id = %s;",
        (username, current_user)
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_user_email(username, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET email = %s WHERE username = %s;",
        (email, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def delete_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM users WHERE username = %s;",
        (username,)
    )
    cursor.execute(
        "DELETE FROM chat_history WHERE user_id = %s;",
        (username,)
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_user_firstname(username, first_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET first_name = %s WHERE username = %s;",
        (first_name, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_user_lastname(username, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET last_name = %s WHERE username = %s;",
        (last_name, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_user_info(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, email, first_name, last_name FROM users WHERE username = %s;",
        (username,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result if result else None

def update_user_password(username, hashed_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password = %s WHERE username = %s;",
        (hashed_password, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def id_to_username(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username FROM users WHERE id = %s;",
        (id,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result if result else None