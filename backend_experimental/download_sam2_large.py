#!/usr/bin/env python3
"""
SAM2.1 Largeモデルチェックポイントのダウンロードスクリプト

ファイルサイズ: ~220MB
ダウンロード先: https://dl.fbaipublicfiles.com/segment_anything_2/
"""
import urllib.request
import sys
from pathlib import Path


def download_with_progress(url: str, output_path: Path):
    """進捗表示付きダウンロード"""
    print(f"Downloading: {url}")
    print(f"To: {output_path}")

    def show_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, (downloaded / total_size) * 100)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        print(f"\r進捗: {percent:.1f}% ({mb_downloaded:.1f}MB / {mb_total:.1f}MB)", end='')

    try:
        urllib.request.urlretrieve(url, output_path, show_progress)
        print("\n✅ ダウンロード完了!")
        return True
    except Exception as e:
        print(f"\n❌ ダウンロード失敗: {e}")
        return False


def main():
    # Largeモデルの情報
    MODEL_URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"
    OUTPUT_FILE = Path("sam2.1_hiera_large.pt")

    # 既に存在する場合はスキップ
    if OUTPUT_FILE.exists():
        print(f"⚠️  {OUTPUT_FILE} は既に存在します。")
        response = input("再ダウンロードしますか？ (y/N): ")
        if response.lower() != 'y':
            print("ダウンロードをスキップしました。")
            return
        OUTPUT_FILE.unlink()

    # ダウンロード実行
    print("=" * 60)
    print("SAM2.1 Largeモデルをダウンロードします")
    print("=" * 60)
    success = download_with_progress(MODEL_URL, OUTPUT_FILE)

    if success:
        size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
        print(f"📦 ファイルサイズ: {size_mb:.1f}MB")
        print(f"✅ 保存先: {OUTPUT_FILE.absolute()}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
