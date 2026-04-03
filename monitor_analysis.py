import sqlite3
import os
import time

db_path = r"C:\Users\ajksk\Desktop\Dev\AI Surgical Motion Knowledge Transfer Library_Ver0.2\backend_experimental\aimotion_experimental.db"
target_id = "fcdd3dca-f361-42cb-aa20-b92e879ce6ce"

print(f"Monitoring ID: {target_id}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

for i in range(20):  # Check for 20 times (approx 100 seconds)
    cursor.execute("SELECT status, progress, current_step, error_message FROM analysis_results WHERE id = ?", (target_id,))
    row = cursor.fetchone()
    if row:
        print(f"Status: {row[0]}, Progress: {row[1]}%, Step: {row[2]}")
        if row[0] == 'COMPLETED':
            print("Analysis COMPLETED!")
            break
        if row[0] == 'FAILED':
            print(f"Analysis FAILED: {row[3]}")
            break
    else:
        print("Record not found yet...")
    
    time.sleep(5)

conn.close()
