import sqlite3

def init_db():
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            item TEXT,
            quantity INTEGER,
            price INTEGER,
            total INTEGER,
            order_time TEXT
        )
    """)

    conn.commit()
    conn.close()
