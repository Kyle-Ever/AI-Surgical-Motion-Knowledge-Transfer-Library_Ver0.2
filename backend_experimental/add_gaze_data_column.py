"""
データベースマイグレーション: gaze_dataカラムの追加

このスクリプトは analysis_results テーブルに gaze_data カラムを追加します。
視線解析機能の実装に必要なスキーマ変更です。
"""
import sqlite3
import sys
from pathlib import Path

# Windows環境でUTF-8出力を強制
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# データベースファイルのパス
DB_PATH = Path(__file__).parent / "aimotion_experimental.db"

def migrate():
    """gaze_dataカラムを追加するマイグレーション"""
    print(f"📊 データベース: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"❌ データベースファイルが見つかりません: {DB_PATH}")
        return False

    try:
        # データベースに接続
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 既存のカラムを確認
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print(f"✅ 既存カラム数: {len(column_names)}")

        # gaze_dataカラムが既に存在するか確認
        if 'gaze_data' in column_names:
            print("⚠️  gaze_data カラムは既に存在します（スキップ）")
            conn.close()
            return True

        # gaze_dataカラムを追加
        print("🔧 gaze_data カラムを追加中...")
        cursor.execute("""
            ALTER TABLE analysis_results
            ADD COLUMN gaze_data TEXT
        """)

        conn.commit()

        # 追加を確認
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns_after = cursor.fetchall()
        column_names_after = [col[1] for col in columns_after]

        if 'gaze_data' in column_names_after:
            print("✅ gaze_data カラムの追加に成功しました")
            print(f"📊 新しいカラム数: {len(column_names_after)}")

            # カラム情報を表示
            print("\n📋 analysis_resultsテーブルのスキーマ:")
            for col in columns_after:
                col_id, name, col_type, notnull, default, pk = col
                nullable = "NOT NULL" if notnull else "NULL"
                default_val = f"DEFAULT {default}" if default else ""
                print(f"  - {name}: {col_type} {nullable} {default_val}")

            conn.close()
            return True
        else:
            print("❌ gaze_data カラムの追加に失敗しました")
            conn.close()
            return False

    except sqlite3.Error as e:
        print(f"❌ SQLiteエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🗄️  データベースマイグレーション: gaze_dataカラム追加")
    print("=" * 60)
    print()

    success = migrate()

    print()
    print("=" * 60)
    if success:
        print("✅ マイグレーション完了")
        print("   バックエンドを再起動してください:")
        print("   > start_backend_experimental.bat")
    else:
        print("❌ マイグレーション失敗")
        print("   手動でデータベースを確認してください")
    print("=" * 60)
