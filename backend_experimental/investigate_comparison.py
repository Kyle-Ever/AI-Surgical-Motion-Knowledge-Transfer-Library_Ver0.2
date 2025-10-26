#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scoring mode problem root cause investigation
"""
import sqlite3
import json
from datetime import datetime
import sys

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def investigate():
    conn = sqlite3.connect('aimotion.db')
    c = conn.cursor()

    print("=" * 80)
    print("Scoring Mode Problem - Root Cause Investigation")
    print("=" * 80)

    # 1. Check target Comparison ID
    print("\n[1] Comparison ID: 29eadcf7-b399-4ce3-907d-20874a558f7c")
    c.execute("""
        SELECT COUNT(*)
        FROM comparison_results
        WHERE id = '29eadcf7-b399-4ce3-907d-20874a558f7c'
    """)
    exists = c.fetchone()[0]
    print(f"   Exists in DB: {'YES' if exists > 0 else 'NO [X]'}")

    # 2. All Comparison status
    print("\n[2] All Comparison Results Status")
    c.execute("""
        SELECT status, COUNT(*) as count
        FROM comparison_results
        GROUP BY status
    """)
    for row in c.fetchall():
        print(f"   {row[0]}: {row[1]} records")

    # 3. FAILED Comparison details (error messages)
    print("\n[3] FAILED Comparisons Error Details")
    c.execute("""
        SELECT id, reference_model_id, learner_analysis_id, error_message, created_at
        FROM comparison_results
        WHERE status = 'FAILED'
        LIMIT 5
    """)
    for row in c.fetchall():
        print(f"\n   ID: {row[0]}")
        print(f"   Reference Model: {row[1]}")
        print(f"   Learner Analysis: {row[2]}")
        print(f"   Error: {row[3]}")
        print(f"   Created: {row[4]}")

    # 4. Reference Models status
    print("\n[4] Reference Models Status")
    c.execute("""
        SELECT id, name, analysis_id, is_active, created_at
        FROM reference_models
        ORDER BY created_at DESC
        LIMIT 5
    """)
    print("   Latest 5 records:")
    for row in c.fetchall():
        print(f"   - {row[1]} (ID: {row[0][:8]}..., Active: {row[3]}, Analysis: {row[2][:8]}...)")

    # 5. Completed Analysis Results
    print("\n[5] Completed Analysis Results")
    c.execute("""
        SELECT a.id, v.filename, a.status,
               CASE WHEN a.skeleton_data IS NOT NULL THEN 'YES' ELSE 'NO' END as has_skeleton,
               CASE WHEN a.scores IS NOT NULL THEN 'YES' ELSE 'NO' END as has_scores,
               a.created_at
        FROM analysis_results a
        JOIN videos v ON v.id = a.video_id
        WHERE a.status = 'completed'
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    print("   Latest completed analyses (5 records):")
    for row in c.fetchall():
        print(f"   - {row[1]}")
        print(f"     ID: {row[0][:8]}..., Skeleton: {row[3]}, Scores: {row[4]}, Created: {row[5]}")

    # 6. Skeleton data format check (sample)
    print("\n[6] Skeleton Data Format Check")
    c.execute("""
        SELECT a.id, v.filename, a.skeleton_data
        FROM analysis_results a
        JOIN videos v ON v.id = a.video_id
        WHERE a.status = 'completed' AND a.skeleton_data IS NOT NULL
        ORDER BY a.created_at DESC
        LIMIT 1
    """)
    row = c.fetchone()
    if row:
        print(f"   Analysis: {row[1]} (ID: {row[0][:8]}...)")
        skeleton_data = json.loads(row[2]) if row[2] else None
        if skeleton_data:
            print(f"   Skeleton data length: {len(skeleton_data)} frames")
            if len(skeleton_data) > 0:
                sample = skeleton_data[0]
                print(f"   Sample frame keys: {list(sample.keys())}")
                if 'landmarks' in sample:
                    print(f"   Landmarks keys: {list(sample['landmarks'].keys())[:5]}...")
                if 'hands' in sample:
                    print(f"   Hands format (V1): {len(sample['hands'])} hands")
        else:
            print("   Skeleton data is NULL")
    else:
        print("   No completed analysis found")

    # 7. Video type distribution
    print("\n[7] Video Type Distribution (video_type)")
    c.execute("""
        SELECT v.video_type, COUNT(*) as count
        FROM videos v
        JOIN analysis_results a ON a.video_id = v.id
        WHERE a.status = 'completed'
        GROUP BY v.video_type
    """)
    for row in c.fetchall():
        print(f"   {row[0]}: {row[1]} records")

    # 8. Check actual status values in database
    print("\n[8] Analysis Status Values (case check)")
    c.execute("""
        SELECT DISTINCT status, COUNT(*) as count
        FROM analysis_results
        GROUP BY status
    """)
    print("   Status values found:")
    for row in c.fetchall():
        print(f"   '{row[0]}': {row[1]} records")

    # 9. Get completed analyses (case-insensitive)
    print("\n[9] Completed Analyses (case-insensitive)")
    c.execute("""
        SELECT a.id, v.filename,
               CASE WHEN a.skeleton_data IS NOT NULL THEN 'YES' ELSE 'NO' END as has_skeleton,
               a.created_at
        FROM analysis_results a
        JOIN videos v ON v.id = a.video_id
        WHERE LOWER(a.status) = 'completed'
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    for row in c.fetchall():
        print(f"   - {row[1]}")
        print(f"     ID: {row[0][:8]}..., Skeleton: {row[2]}, Created: {row[3]}")

    conn.close()

    print("\n" + "=" * 80)
    print("Investigation Complete")
    print("=" * 80)

if __name__ == "__main__":
    investigate()
