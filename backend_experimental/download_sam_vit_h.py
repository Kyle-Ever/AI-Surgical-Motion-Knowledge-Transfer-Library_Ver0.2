"""
SAM vit_h モデルのダウンロード（GPU用）
RTX 3060での高速・高精度推論のため
"""
import urllib.request
from pathlib import Path
import sys
import hashlib

def download_sam_vit_h():
    """SAM vit_h モデルをダウンロード"""
    url = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
    output_path = Path("sam_vit_h_4b8939.pth")

    # 既存ファイルチェック
    if output_path.exists():
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"✅ {output_path} already exists ({size_mb:.1f}MB)")

        # サイズチェック
        expected_size = 2446  # ~2.4GB（実際のファイルサイズ）
        if abs(size_mb - expected_size) > 50:
            print(f"⚠️ File size ({size_mb:.1f}MB) differs from expected ({expected_size}MB)")
            response = input("Re-download? (y/n): ")
            if response.lower() != 'y':
                return True
            print("Deleting existing file...")
            output_path.unlink()
        else:
            print("File size OK. Skipping download.")
            return True

    print()
    print("=" * 70)
    print("📥 Downloading SAM vit_h model for GPU inference")
    print("=" * 70)
    print(f"URL: {url}")
    print(f"Output: {output_path}")
    print(f"Size: ~2.56GB")
    print(f"Target GPU: RTX 3060 (12GB VRAM)")
    print()
    print("This will take 5-15 minutes depending on your internet speed...")
    print()

    def progress_hook(block_num, block_size, total_size):
        """進捗バーの表示"""
        downloaded = block_num * block_size
        percent = min(100, downloaded / total_size * 100)
        mb_downloaded = downloaded / 1024 / 1024
        mb_total = total_size / 1024 / 1024

        bar_length = 50
        filled = int(bar_length * percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        # 推定残り時間（簡易計算）
        if block_num > 0:
            speed_mbps = mb_downloaded / (block_num * 0.1)  # 簡易速度推定
            remaining_mb = mb_total - mb_downloaded
            eta_sec = remaining_mb / speed_mbps if speed_mbps > 0 else 0
            eta_min = eta_sec / 60

            sys.stdout.write(
                f'\r[{bar}] {percent:.1f}% '
                f'({mb_downloaded:.1f}MB / {mb_total:.1f}MB) '
                f'ETA: {eta_min:.1f}min'
            )
        else:
            sys.stdout.write(f'\r[{bar}] {percent:.1f}% ({mb_downloaded:.1f}MB / {mb_total:.1f}MB)')

        sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, output_path, progress_hook)
        print()
        print()
        print(f"✅ Download completed: {output_path}")

        # ファイルサイズ確認
        size_mb = output_path.stat().st_size / 1024 / 1024
        expected_size = 2446  # ~2.4GB（実際のファイルサイズ）

        print(f"   File size: {size_mb:.1f}MB")

        if abs(size_mb - expected_size) > 50:
            print(f"⚠️ Warning: File size ({size_mb:.1f}MB) differs from expected ({expected_size}MB)")
            print(f"   The download may be corrupted. Please try again.")
            return False

        print(f"✅ File size verified")
        return True

    except KeyboardInterrupt:
        print("\n\n⚠️ Download interrupted by user")
        if output_path.exists():
            print(f"Cleaning up partial download...")
            output_path.unlink()
        return False

    except Exception as e:
        print(f"\n\n❌ Download failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False

def verify_model_file():
    """モデルファイルの整合性チェック"""
    model_path = Path("sam_vit_h_4b8939.pth")

    if not model_path.exists():
        print("❌ Model file not found")
        return False

    print()
    print("=" * 70)
    print("Verifying model file...")
    print("=" * 70)

    try:
        # PyTorchでロード可能かチェック
        import torch

        print("Loading model file with PyTorch...")
        state_dict = torch.load(model_path, map_location='cpu')

        if isinstance(state_dict, dict):
            num_keys = len(state_dict.keys())
            print(f"✅ Model file is valid PyTorch checkpoint")
            print(f"   Number of parameters: {num_keys}")

            # サンプルキーを表示
            sample_keys = list(state_dict.keys())[:3]
            print(f"   Sample keys: {sample_keys}")

            return True
        else:
            print(f"⚠️ Unexpected format: {type(state_dict)}")
            return False

    except Exception as e:
        print(f"❌ Model file verification failed: {e}")
        return False

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("SAM vit_h Model Download for GPU (RTX 3060)")
    print("=" * 70)
    print()
    print("This script will download SAM vit_h checkpoint (~2.56GB)")
    print("Required for high-precision GPU inference on RTX 3060")
    print()

    # ダウンロード実行
    success = download_sam_vit_h()

    if success:
        # 検証
        verify_success = verify_model_file()

        print()
        print("=" * 70)
        if verify_success:
            print("🎉 Model ready for GPU inference!")
            print()
            print("Next steps:")
            print("1. Install PyTorch with CUDA:")
            print("   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
            print("2. Run check_cuda.py to verify GPU environment")
            print("3. Run test_sam_gpu.py to test SAM vit_h on GPU")
        else:
            print("⚠️ Model file may be corrupted")
            print("   Please delete sam_vit_h_4b8939.pth and run this script again")
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("❌ Download failed")
        print("   Please check your internet connection and try again")
        print("=" * 70)
