"""
CUDA環境の検証（RTX 3060対応）
"""
import sys

print("=" * 70)
print("CUDA環境チェック（RTX 3060）")
print("=" * 70)
print()

# PyTorchのインポート確認
try:
    import torch
    print(f"✅ PyTorch imported successfully")
    print(f"   Version: {torch.__version__}")
except ImportError as e:
    print(f"❌ PyTorch not installed: {e}")
    print("   Please install: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
    sys.exit(1)

print()
print("=" * 70)
print("CUDA Availability")
print("=" * 70)

if not torch.cuda.is_available():
    print("❌ CUDA is NOT available")
    print()
    print("Possible causes:")
    print("1. PyTorch CPU版がインストールされている")
    print("   解決策: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
    print("2. NVIDIA ドライバーが古い")
    print("   解決策: https://www.nvidia.com/Download/index.aspx からドライバーを更新")
    print("3. CUDA Toolkitがインストールされていない")
    print("   解決策: PyTorch CUDA版をインストール（上記コマンド）")
    print()
    sys.exit(1)

print(f"✅ CUDA is available")
print(f"   CUDA version (compiled): {torch.version.cuda}")
print(f"   cuDNN version: {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else 'N/A'}")
print()

print("=" * 70)
print("GPU Information")
print("=" * 70)

gpu_count = torch.cuda.device_count()
print(f"GPU count: {gpu_count}")
print()

for i in range(gpu_count):
    props = torch.cuda.get_device_properties(i)
    print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
    print(f"   Total VRAM: {props.total_memory / 1024**3:.2f} GB")
    print(f"   CUDA Compute Capability: {props.major}.{props.minor}")
    print(f"   Multi-processors: {props.multi_processor_count}")
    print(f"   Max threads per block: {props.max_threads_per_block}")
    print()

# 現在のGPU
current_device = torch.cuda.current_device()
print(f"Current GPU: {current_device} ({torch.cuda.get_device_name(current_device)})")
print()

print("=" * 70)
print("VRAM Status")
print("=" * 70)

allocated = torch.cuda.memory_allocated() / 1024**2
reserved = torch.cuda.memory_reserved() / 1024**2
total = torch.cuda.get_device_properties(0).total_memory / 1024**2

print(f"Allocated: {allocated:.1f} MB")
print(f"Reserved: {reserved:.1f} MB")
print(f"Total: {total:.1f} MB ({total/1024:.2f} GB)")
print(f"Free: {total - reserved:.1f} MB")
print()

print("=" * 70)
print("GPU Test")
print("=" * 70)

try:
    # テストテンソルをGPUに配置
    test_tensor = torch.randn(1000, 1000).cuda()
    result = torch.matmul(test_tensor, test_tensor)

    print(f"✅ GPU computation test passed")
    print(f"   Test tensor device: {test_tensor.device}")
    print(f"   Test tensor shape: {test_tensor.shape}")
    print(f"   Computation result shape: {result.shape}")

    # VRAM使用量確認
    allocated_after = torch.cuda.memory_allocated() / 1024**2
    print(f"   VRAM used by test: {allocated_after - allocated:.1f} MB")

    # クリーンアップ
    del test_tensor, result
    torch.cuda.empty_cache()

except Exception as e:
    print(f"❌ GPU computation test failed: {e}")
    sys.exit(1)

print()
print("=" * 70)
print("SAM vit_h Requirements Check")
print("=" * 70)

total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
required_vram_gb = 3.0  # SAM vit_h推奨

print(f"Total VRAM: {total_vram_gb:.2f} GB")
print(f"Required for SAM vit_h: {required_vram_gb:.1f} GB")

if total_vram_gb >= required_vram_gb:
    print(f"✅ Sufficient VRAM for SAM vit_h")
    print(f"   余裕: {total_vram_gb - required_vram_gb:.2f} GB")
else:
    print(f"⚠️ VRAM may be insufficient")
    print(f"   不足: {required_vram_gb - total_vram_gb:.2f} GB")
    print(f"   推奨: vit_l または vit_b を使用")

print()
print("=" * 70)
print("🎉 CUDA環境は正常です！")
print("   RTX 3060でSAM vit_h GPUを実行可能")
print("=" * 70)
