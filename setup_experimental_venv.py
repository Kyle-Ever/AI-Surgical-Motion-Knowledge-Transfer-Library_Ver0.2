"""
実験版バックエンドのvenv311をセットアップ
"""
import shutil
from pathlib import Path

def main():
    base_dir = Path(__file__).parent
    src_venv = base_dir / "backend" / "venv311"
    dst_venv = base_dir / "backend_experimental" / "venv311"

    if not src_venv.exists():
        print(f"ERROR: Source venv not found: {src_venv}")
        return 1

    if dst_venv.exists():
        print(f"venv311 already exists at: {dst_venv}")
        return 0

    print(f"Copying venv311 from {src_venv} to {dst_venv}...")
    try:
        shutil.copytree(src_venv, dst_venv, dirs_exist_ok=True)
        print(f"SUCCESS: venv311 copied to {dst_venv}")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to copy venv: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
