#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全てのステータス使用箇所を検出して影響範囲を特定
"""
import os
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def find_status_usages():
    print("=" * 80)
    print("Status Usage Analysis - Finding all impact points")
    print("=" * 80)

    # 検索パターン
    patterns = {
        'enum_comparison': r'AnalysisStatus\.(COMPLETED|FAILED|PENDING|PROCESSING)',
        'string_comparison': r"status\s*==\s*['\"](?:completed|COMPLETED|failed|FAILED|pending|PENDING|processing|PROCESSING)['\"]",
        'filter_comparison': r"filter\([^)]*status[^)]*\)",
        'where_clause': r"WHERE.*status.*(?:=|==).*['\"](?:completed|COMPLETED)['\"]",
    }

    results = {}
    base_dir = 'app'

    for root, dirs, files in os.walk(base_dir):
        # Skip __pycache__ and other non-source directories
        dirs[:] = [d for d in dirs if not d.startswith('__') and not d.startswith('.')]

        for file in files:
            if not file.endswith('.py'):
                continue

            filepath = os.path.join(root, file)
            relative_path = filepath.replace('\\', '/')

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for pattern_name, pattern in patterns.items():
                        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            # 行番号を見つける
                            line_num = content[:match.start()].count('\n') + 1
                            line_content = lines[line_num - 1].strip()

                            if pattern_name not in results:
                                results[pattern_name] = []

                            results[pattern_name].append({
                                'file': relative_path,
                                'line': line_num,
                                'content': line_content,
                                'match': match.group(0)
                            })
            except Exception as e:
                print(f"Error reading {filepath}: {e}")

    # 結果を整理して表示
    print("\n[1] ENUM COMPARISONS (AnalysisStatus.COMPLETED)")
    print("-" * 80)
    if 'enum_comparison' in results:
        files_affected = set([r['file'] for r in results['enum_comparison']])
        print(f"   Files affected: {len(files_affected)}")
        print(f"   Total usages: {len(results['enum_comparison'])}\n")

        for file in sorted(files_affected):
            file_matches = [r for r in results['enum_comparison'] if r['file'] == file]
            print(f"\n   {file}:")
            for match in file_matches:
                print(f"      Line {match['line']}: {match['match']}")
                print(f"         {match['content'][:100]}")
    else:
        print("   No Enum comparisons found")

    print("\n[2] STRING COMPARISONS (status == 'completed')")
    print("-" * 80)
    if 'string_comparison' in results:
        files_affected = set([r['file'] for r in results['string_comparison']])
        print(f"   Files affected: {len(files_affected)}")
        print(f"   Total usages: {len(results['string_comparison'])}\n")

        for file in sorted(files_affected):
            file_matches = [r for r in results['string_comparison'] if r['file'] == file]
            print(f"\n   {file}:")
            for match in file_matches:
                print(f"      Line {match['line']}: {match['match']}")
    else:
        print("   No string comparisons found")

    print("\n[3] FILTER CLAUSES")
    print("-" * 80)
    if 'filter_comparison' in results:
        files_affected = set([r['file'] for r in results['filter_comparison']])
        print(f"   Files affected: {len(files_affected)}")
        print(f"   Total usages: {len(results['filter_comparison'])}\n")

        for file in sorted(files_affected):
            file_matches = [r for r in results['filter_comparison'] if r['file'] == file]
            print(f"\n   {file}:")
            for match in file_matches[:5]:  # Show first 5
                print(f"      Line {match['line']}: {match['content'][:80]}")
    else:
        print("   No filter clauses found")

    # Summary
    print("\n" + "=" * 80)
    print("IMPACT SUMMARY")
    print("=" * 80)

    total_files = set()
    total_usages = 0
    for pattern_name, matches in results.items():
        total_usages += len(matches)
        total_files.update([m['file'] for m in matches])

    print(f"\nTotal files that need review: {len(total_files)}")
    print(f"Total usage points: {total_usages}")
    print(f"\nFiles requiring changes:")
    for file in sorted(total_files):
        count = sum(len([m for m in matches if m['file'] == file]) for matches in results.values())
        print(f"   {file}: {count} changes")

if __name__ == "__main__":
    find_status_usages()
