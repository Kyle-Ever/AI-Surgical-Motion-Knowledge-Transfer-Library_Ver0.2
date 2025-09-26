import sqlite3
import json

# Connect to database
conn = sqlite3.connect('aimotion.db')
cursor = conn.cursor()

# Check analysis results
cursor.execute("SELECT id, status, created_at, completed_at FROM analysis_results ORDER BY created_at DESC LIMIT 10")
results = cursor.fetchall()

print("Analysis Results:")
print("-" * 80)
for row in results:
    print(f"ID: {row[0][:8]}... | Status: {row[1]} | Created: {row[2]} | Completed: {row[3]}")

# Count by status
cursor.execute("SELECT status, COUNT(*) FROM analysis_results GROUP BY status")
status_counts = cursor.fetchall()

print("\nStatus Summary:")
print("-" * 40)
for status, count in status_counts:
    print(f"{status}: {count}")

conn.close()