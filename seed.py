"""Insert dummy students for testing (no real personal data)."""
import sqlite3
from main import DB_PATH, init_db

init_db()
rows = [
    ("Asha Verma", "2004-03-14", "asha@example.com", "9000000001", "Python", "Hyderabad", "2024-06-01"),
    ("Ravi Kumar", "2005-11-02", "ravi@example.com", "9000000002", "Data Science", "Vijayawada", "2024-06-01"),
    ("Meena Reddy", "2006-07-21", "meena@example.com", "9000000003", "Python", "Warangal", "2025-01-10"),
    ("Karthik Rao", "2003-01-30", "karthik@example.com", "9000000004", "Web Dev", "Guntur", "2023-08-15"),
]
with sqlite3.connect(DB_PATH) as conn:
    conn.executemany(
        "INSERT OR IGNORE INTO students (name, date_of_birth, email, phone, course, address, enrollment_date) "
        "VALUES (?,?,?,?,?,?,?)",
        rows,
    )
print("Seeded", len(rows), "dummy students")
