import sqlite3
import os

db_path = r"C:\Users\ajksk\Desktop\Dev\AI Surgical Motion Knowledge Transfer Library_Ver0.2\backend_experimental\aimotion_experimental.db"
video_id = "5ec1dce1-4159-4801-9f50-d1ba980be39b"

print(f"Checking video ID: {video_id} in {db_path}")
if not os.path.exists(db_path):
    print("DB file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, filename, created_at FROM videos WHERE id = ?", (video_id,))
row = cursor.fetchone()
if row:
    print("Found video:", row)
else:
    print("Video NOT found")
    # List all videos
    print("Listing all videos:")
    cursor.execute("SELECT id, filename FROM videos LIMIT 5")
    for v in cursor.fetchall():
        print(v)

conn.close()
