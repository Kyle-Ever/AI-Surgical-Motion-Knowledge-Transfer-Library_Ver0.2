import sqlite3
import os

db_path = r"C:\Users\ajksk\Desktop\Dev\AI Surgical Motion Knowledge Transfer Library_Ver0.2\backend_experimental\aimotion_experimental.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
target_id = "f26d8044-20d5-42c7-a26b-a533fb06e1b1"
print(f"Checking for ID: {target_id}")
cursor.execute("SELECT id, status, created_at, error_message FROM analysis_results WHERE id = ?", (target_id,))
row = cursor.fetchone()
if row:
    print("Found:", row)
else:
    print("Not found")
conn.close()
