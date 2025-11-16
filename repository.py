import os
import sqlite3

from dotenv import load_dotenv

# --- SQLite ---
load_dotenv()
DB_PATH = os.getenv('DB_PATH')

def init_db():
    init_debts()
    init_users()

def init_debts():
    """Tworzy tabelę, jeśli nie istnieje"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debts (
            debt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_id TEXT NOT NULL,
            creditor_id TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_amount REAL NOT NULL DEFAULT 0,
            description TEXT,
            is_paid BOOLEAN NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (debtor_id) REFERENCES users(user_id),
            FOREIGN KEY (creditor_id) REFERENCES users(user_id)
        )
    """)
    conn.commit()
    conn.close()

def init_users():
    """Tworzy tabelę, jeśli nie istnieje"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            phone TEXT
        )
    """)
    conn.commit()
    conn.close()

# Dodanie długu
def add_debt(debtor_id, creditor_id, amount, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO debts(debtor_id, creditor_id, amount, description)
        VALUES (?, ?, ?, ?)
    """, (debtor_id, creditor_id, amount, description))
    conn.commit()
    conn.close()

# Lista wszystkich długów użytkownika
def get_user_debts(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.debt_id, u.username, u.phone, d.amount, d.paid_amount, d.description
        FROM debts d
        JOIN users u ON d.creditor_id = u.user_id
        WHERE d.debtor_id = ? AND d.is_paid = 0
        ORDER BY u.username
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Lista wszystkich długów zgrupowana
def get_all_debts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.debtor_id, u.username, u.phone, d.amount, d.paid_amount, d.description
        FROM debts d
        JOIN users u ON d.creditor_id = u.user_id
        WHERE d.is_paid = 0
        ORDER BY u.username
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# Lista długów użytkownika względem kredytodawcy
def get_user_debts_for_creditor(debtor_id, creditor_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT debt_id, amount, paid_amount
        FROM debts
        WHERE debtor_id = ? AND creditor_id = ? AND is_paid = 0
        ORDER BY created_at
    """, (debtor_id, creditor_id))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Lista wszystkich kredytów użytkownika
def get_user_credit(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.username, d.amount, d.paid_amount, d.description
        FROM debts d
        JOIN users u ON d.debtor_id = u.user_id
        WHERE d.creditor_id = ? AND d.is_paid = 0
        ORDER BY u.username
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Dodaje użytkownika do tabeli users, jeśli jeszcze nie istnieje
def ensure_user_exists(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users(user_id, username, phone)
        VALUES (?, ?, NULL)
        ON CONFLICT(user_id) DO NOTHING
    """, (user_id, username))
    conn.commit()
    conn.close()

# rejestracja numeru użytkownika
def register_user(user_id, username, phone):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users(user_id, username, phone)
        VALUES(?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone
    """, (user_id, username, phone))
    conn.commit()
    conn.close()

# spłacenie całego długu
def pay_debt(debt_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE debts
        SET paid_amount = amount, is_paid = 1
        WHERE debt_id = ?
    """, (debt_id,))
    conn.commit()
    conn.close()

# skpłacenie długu częściowo
def pay_debt_partial(debt_id, paid_amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE debts
        SET paid_amount = ?
        WHERE debt_id = ?
    """, (paid_amount, debt_id))
    conn.commit()
    conn.close()