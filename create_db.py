import sqlite3

conn = sqlite3.connect('bachat.db')
cur = conn.cursor()

# Users table: store username and password hash and budget (nullable)
cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    budget REAL
);
''')

# Expenses table
cur.execute('''
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    note TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
''')

conn.commit()
conn.close()
print('Database and tables created (bachat.db)')
