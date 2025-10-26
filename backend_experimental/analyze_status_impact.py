#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Status値の大文字・小文字不一致 - 影響範囲調査
なぜこのような構造になっているのか、変更による影響範囲を分析
"""
import sqlite3
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def analyze_impact():
    conn = sqlite3.connect('aimotion.db')
    c = conn.cursor()

    print("=" * 80)
    print("Status Value Case Mismatch - Impact Analysis")
    print("=" * 80)

    # 1. 現在のデータベース状態を詳細に分析
    print("\n[1] DATABASE CURRENT STATE ANALYSIS")
    print("-" * 80)

    # 1.1 analysis_results のステータス分布（大文字小文字別）
    print("\n1.1 analysis_results status distribution:")
    c.execute("""
        SELECT status, COUNT(*) as count
        FROM analysis_results
        GROUP BY status
        ORDER BY count DESC
    """)
    total_analyses = 0
    for row in c.fetchall():
        total_analyses += row[1]
        print(f"   '{row[0]}': {row[1]} records ({row[1]/total_analyses*100:.1f}% if total else 0)")
    print(f"   TOTAL: {total_analyses} records")

    # 1.2 comparison_results のステータス分布
    print("\n1.2 comparison_results status distribution:")
    c.execute("""
        SELECT status, COUNT(*) as count
        FROM comparison_results
        GROUP BY status
        ORDER BY count DESC
    """)
    total_comparisons = 0
    for row in c.fetchall():
        total_comparisons += row[1]
        print(f"   '{row[0]}': {row[1]} records ({row[1]/total_comparisons*100:.1f}% if total else 0)")
    print(f"   TOTAL: {total_comparisons} records")

    # 2. 大文字・小文字の混在状況
    print("\n[2] CASE MIXING DETECTION")
    print("-" * 80)

    # 2.1 analysis_results で大文字と小文字が混在しているか
    c.execute("""
        SELECT
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as upper_completed,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as lower_completed,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as upper_failed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as lower_failed,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as upper_pending,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as lower_pending,
            SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) as upper_processing,
            SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as lower_processing
        FROM analysis_results
    """)
    row = c.fetchone()
    print("\n2.1 analysis_results case distribution:")
    print(f"   COMPLETED (upper): {row[0]}")
    print(f"   completed (lower): {row[1]}")
    print(f"   FAILED (upper): {row[2]}")
    print(f"   failed (lower): {row[3]}")
    print(f"   PENDING (upper): {row[4]}")
    print(f"   pending (lower): {row[5]}")
    print(f"   PROCESSING (upper): {row[6]}")
    print(f"   processing (lower): {row[7]}")

    # 2.2 comparison_results で大文字と小文字が混在しているか
    c.execute("""
        SELECT
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as upper_completed,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as lower_completed,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as upper_failed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as lower_failed,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as upper_pending,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as lower_pending,
            SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) as upper_processing,
            SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as lower_processing
        FROM comparison_results
    """)
    row = c.fetchone()
    print("\n2.2 comparison_results case distribution:")
    print(f"   COMPLETED (upper): {row[0]}")
    print(f"   completed (lower): {row[1]}")
    print(f"   FAILED (upper): {row[2]}")
    print(f"   failed (lower): {row[3]}")
    print(f"   PENDING (upper): {row[4]}")
    print(f"   pending (lower): {row[5]}")
    print(f"   PROCESSING (upper): {row[6]}")
    print(f"   processing (lower): {row[7]}")

    # 3. いつからこの状態になったのか（タイムスタンプ分析）
    print("\n[3] TEMPORAL ANALYSIS - When did this state begin?")
    print("-" * 80)

    # 3.1 最初のCOMPLETED（大文字）レコード
    c.execute("""
        SELECT id, status, created_at
        FROM analysis_results
        WHERE status = 'COMPLETED'
        ORDER BY created_at ASC
        LIMIT 1
    """)
    row = c.fetchone()
    if row:
        print(f"\n3.1 First COMPLETED (upper) analysis:")
        print(f"   ID: {row[0][:8]}...")
        print(f"   Status: '{row[1]}'")
        print(f"   Created: {row[2]}")

    # 3.2 最初のcompleted（小文字）レコード（もしあれば）
    c.execute("""
        SELECT id, status, created_at
        FROM analysis_results
        WHERE status = 'completed'
        ORDER BY created_at ASC
        LIMIT 1
    """)
    row = c.fetchone()
    if row:
        print(f"\n3.2 First completed (lower) analysis:")
        print(f"   ID: {row[0][:8]}...")
        print(f"   Status: '{row[1]}'")
        print(f"   Created: {row[2]}")
    else:
        print(f"\n3.2 No 'completed' (lower) records found")

    # 4. Reference Modelsとの依存関係
    print("\n[4] DEPENDENCY ANALYSIS - Reference Models")
    print("-" * 80)

    # 4.1 Reference Modelsが参照しているAnalysisのステータス
    c.execute("""
        SELECT a.status, COUNT(*) as count
        FROM reference_models rm
        JOIN analysis_results a ON a.id = rm.analysis_id
        GROUP BY a.status
    """)
    print("\n4.1 Analysis status referenced by Reference Models:")
    for row in c.fetchall():
        print(f"   '{row[0]}': {row[1]} reference models")

    # 4.2 Comparisonsが参照しているAnalysisのステータス
    c.execute("""
        SELECT a.status, COUNT(*) as count
        FROM comparison_results cr
        JOIN analysis_results a ON a.id = cr.learner_analysis_id
        GROUP BY a.status
    """)
    print("\n4.2 Learner Analysis status in Comparisons:")
    for row in c.fetchall():
        print(f"   '{row[0]}': {row[1]} comparisons")

    # 5. 影響を受けるクエリのシミュレーション
    print("\n[5] QUERY IMPACT SIMULATION")
    print("-" * 80)

    # 5.1 現在のコード（小文字）でのマッチ数
    c.execute("""
        SELECT COUNT(*) FROM analysis_results WHERE status = 'completed'
    """)
    lower_match = c.fetchone()[0]

    # 5.2 大文字でのマッチ数
    c.execute("""
        SELECT COUNT(*) FROM analysis_results WHERE status = 'COMPLETED'
    """)
    upper_match = c.fetchone()[0]

    # 5.3 ケースインセンシティブでのマッチ数
    c.execute("""
        SELECT COUNT(*) FROM analysis_results WHERE LOWER(status) = 'completed'
    """)
    case_insensitive_match = c.fetchone()[0]

    print("\n5.1 Query result comparison:")
    print(f"   WHERE status = 'completed' (current code): {lower_match} records")
    print(f"   WHERE status = 'COMPLETED' (database actual): {upper_match} records")
    print(f"   WHERE LOWER(status) = 'completed' (case-insensitive): {case_insensitive_match} records")
    print(f"   LOST RECORDS: {case_insensitive_match - lower_match} ({(case_insensitive_match - lower_match) / case_insensitive_match * 100 if case_insensitive_match > 0 else 0:.1f}%)")

    # 6. SQLAlchemyとSQLiteの相互作用
    print("\n[6] SQLALCHEMY-SQLITE INTERACTION ANALYSIS")
    print("-" * 80)
    print("""
    WHY is the database using uppercase?

    Possible reasons:
    1. SQLAlchemy Enum handling with SQLite:
       - SQLAlchemy may convert Enum values to uppercase by default
       - SQLite stores text as-is without case normalization

    2. Migration or initial data:
       - Alembic migrations may have used uppercase
       - Initial seed data may have used uppercase

    3. Code evolution:
       - Enum definitions may have changed from uppercase to lowercase
       - Database was populated before the change

    Current Python Enum definition (from models/analysis.py):
       class AnalysisStatus(str, enum.Enum):
           COMPLETED = "completed"  # Value is lowercase
           FAILED = "failed"
           PENDING = "pending"
           PROCESSING = "processing"

    But database contains: 'COMPLETED', 'FAILED', 'PENDING', 'PROCESSING'

    This suggests:
    - Either SQLAlchemy is converting to uppercase on INSERT
    - Or there's a mismatch between old and new Enum definitions
    """)

    conn.close()

    # 7. 修正方法の比較分析
    print("\n[7] FIX APPROACH COMPARISON")
    print("-" * 80)
    print("""
    Option A: Update Database to lowercase
    ----------------------------------------
    Pros:
      + Matches current Python Enum definitions
      + No code changes needed
      + Clean and consistent

    Cons:
      - Requires database migration
      - Risk if backup not available
      - Downtime during migration

    SQL:
      UPDATE analysis_results SET status = LOWER(status);
      UPDATE comparison_results SET status = LOWER(status);

    Impact:
      - All 284 COMPLETED → completed
      - All 58 FAILED → failed
      - All 3 PENDING → pending
      - All 3 PROCESSING → processing


    Option B: Update Python Enum to uppercase
    ------------------------------------------
    Pros:
      + No database changes
      + Matches existing data (284 records)
      + Zero migration risk

    Cons:
      - Requires code changes in all files using Enum
      - May break frontend expectations
      - Against Python naming conventions (lowercase for values)

    Code:
      class AnalysisStatus(str, enum.Enum):
          COMPLETED = "COMPLETED"
          FAILED = "FAILED"
          PENDING = "PENDING"
          PROCESSING = "PROCESSING"

    Impact:
      - 12 files need updates (from grep analysis)
      - All AnalysisStatus.COMPLETED comparisons work
      - Need to verify frontend compatibility


    Option C: Case-insensitive queries (RECOMMENDED)
    -------------------------------------------------
    Pros:
      + No database changes
      + Minimal code changes
      + Backward compatible
      + Works with both cases

    Cons:
      - Slight performance overhead (negligible)
      - Query syntax is longer

    Code:
      # Before
      WHERE status == AnalysisStatus.COMPLETED

      # After
      WHERE func.lower(status) == 'completed'
      # Or
      WHERE status.in_(['COMPLETED', 'completed'])

    Impact:
      - ~10 query locations need updates
      - Zero data migration
      - Safe and reversible
    """)

    print("\n" + "=" * 80)
    print("RECOMMENDATION: Option C (Case-insensitive queries)")
    print("=" * 80)
    print("""
    Reasons:
    1. SAFEST: No data changes, no migration risk
    2. COMPATIBLE: Works with existing uppercase data
    3. FUTURE-PROOF: Works if data becomes lowercase
    4. MINIMAL IMPACT: Only query code changes needed
    5. REVERSIBLE: Can easily revert if issues arise
    """)

if __name__ == "__main__":
    analyze_impact()
