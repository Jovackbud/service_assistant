import sqlite3
import datetime
from config import TICKET_DB_PATH, FEEDBACK_DB_PATH


def init_db():
    """Initializes the SQLite databases for tickets and feedback if they don't exist."""
    # Initialize Ticket DB
    with sqlite3.connect(TICKET_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_role TEXT,
                question TEXT,
                chat_history TEXT,
                suggested_team TEXT,
                selected_team TEXT,
                status TEXT DEFAULT 'Open'
            )
        ''')
        conn.commit()

    # Initialize Feedback DB
    with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_role TEXT,
                question TEXT,
                answer TEXT,
                rating TEXT CHECK(rating IN ('👍', '👎'))
            )
        ''')
        conn.commit()


def save_ticket(user_role, question, chat_history, suggested_team, selected_team):
    """Saves a new ticket to the database."""
    try:
        with sqlite3.connect(TICKET_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tickets (user_role, question, chat_history, suggested_team, selected_team)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_role, question, chat_history, suggested_team, selected_team))
            conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error saving ticket: {e}")
        return False


def save_feedback(user_role, question, answer, rating):
    """Saves user feedback to the database."""
    try:
        with sqlite3.connect(FEEDBACK_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (user_role, question, answer, rating)
                VALUES (?, ?, ?, ?)
            ''', (user_role, question, answer, rating))
            conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error saving feedback: {e}")
        return False


# Initialize databases when this module is imported
init_db()
