"""
バックエンドを実験版にコピーするスクリプト
"""
import shutil
import os
from pathlib import Path

# ベースディレクトリ
base_dir = Path(__file__).parent
backend_src = base_dir / "backend"
backend_dst = base_dir / "backend_experimental"

# 除外するディレクトリとファイル
EXCLUDE_DIRS = {'venv', 'venv311', '__pycache__', '.pytest_cache', 'data', 'uploads', '.git'}
EXCLUDE_FILES = {'.pyc', '.db', '.db-journal'}

def should_copy(path: Path) -> bool:
    """コピーすべきかどうかを判定"""
    # 除外ディレクトリのチェック
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False

    # 除外ファイル拡張子のチェック
    if path.suffix in EXCLUDE_FILES:
        return False

    return True

def copy_directory(src: Path, dst: Path):
    """ディレクトリを再帰的にコピー"""
    print(f"Copying {src} to {dst}...")

    # 既存のディレクトリを削除
    if dst.exists():
        print(f"Removing existing {dst}...")
        shutil.rmtree(dst, ignore_errors=True)

    # 新規作成
    dst.mkdir(parents=True, exist_ok=True)

    # ファイルとディレクトリをコピー
    copied_count = 0
    skipped_count = 0

    for src_file in src.rglob('*'):
        if not should_copy(src_file):
            skipped_count += 1
            continue

        # 相対パスを計算
        rel_path = src_file.relative_to(src)
        dst_file = dst / rel_path

        try:
            if src_file.is_dir():
                dst_file.mkdir(parents=True, exist_ok=True)
            else:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied_count += 1

                if copied_count % 100 == 0:
                    print(f"  Copied {copied_count} files...")
        except Exception as e:
            print(f"  Warning: Failed to copy {src_file}: {e}")
            skipped_count += 1

    print("Copy completed!")
    print(f"  Copied: {copied_count} files")
    print(f"  Skipped: {skipped_count} items")

if __name__ == "__main__":
    print("=" * 60)
    print("Creating experimental backend")
    print("=" * 60)

    if not backend_src.exists():
        print(f"Error: {backend_src} not found")
        exit(1)

    copy_directory(backend_src, backend_dst)

    print("\n" + "=" * 60)
    print("Experimental backend created successfully!")
    print("=" * 60)
