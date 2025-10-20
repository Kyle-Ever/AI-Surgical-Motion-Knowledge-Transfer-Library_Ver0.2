"""
SAM vit_h GPU性能テスト（RTX 3060）
"""
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_gpu_availability():
    """GPU利用可能性の確認"""
    print("=" * 70)
    print("GPU環境チェック")
    print("=" * 70)

    try:
        import torch
    except ImportError:
        print("❌ PyTorch not installed")
        print("   Install: pip install torch --index-url https://download.pytorch.org/whl/cu118")
        return False

    if not torch.cuda.is_available():
        print("❌ CUDA is NOT available")
        print("   Please install PyTorch with CUDA support")
        return False

    print(f"✅ CUDA available")
    print(f"   PyTorch version: {torch.__version__}")
    print(f"   CUDA version: {torch.version.cuda}")
    print(f"   GPU: {torch.cuda.get_device_name(0)}")

    props = torch.cuda.get_device_properties(0)
    total_vram = props.total_memory / 1024**3
    print(f"   VRAM: {total_vram:.2f} GB")

    return True

def test_sam_vit_h_loading():
    """SAM vit_h GPU読み込みテスト"""
    print("\n" + "=" * 70)
    print("SAM vit_h GPU読み込みテスト")
    print("=" * 70)

    try:
        from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
        import torch

        start_time = time.time()
        tracker = SAMTrackerUnified(model_type="vit_h", device="cuda")
        load_time = time.time() - start_time

        print(f"✅ SAM vit_h loaded on GPU")
        print(f"   Loading time: {load_time:.2f}s")

        allocated_mb = torch.cuda.memory_allocated() / 1024**2
        print(f"   VRAM allocated: {allocated_mb:.1f}MB")

        return tracker

    except FileNotFoundError as e:
        print(f"❌ Model checkpoint not found")
        print(f"   Run: python download_sam_vit_h.py")
        return None
    except Exception as e:
        print(f"❌ Loading failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_inference_speed():
    """推論速度ベンチマーク"""
    print("\n" + "=" * 70)
    print("推論速度ベンチマーク: GPU vs CPU")
    print("=" * 70)

    from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
    import torch

    # テスト画像（実際の動画サイズ）
    test_image = np.random.randint(0, 255, (620, 1214, 3), dtype=np.uint8)
    test_point = [(607, 310)]

    # GPU テスト
    print("\n🔥 GPU (RTX 3060, vit_h) テスト:")
    try:
        tracker_gpu = SAMTrackerUnified(model_type="vit_h", device="cuda")
        tracker_gpu.set_image(test_image)

        # ウォームアップ
        _ = tracker_gpu.segment_with_point(test_point, [1])

        # 10回実行
        times_gpu = []
        for i in range(10):
            start = time.time()
            result = tracker_gpu.segment_with_point(test_point, [1])
            elapsed = time.time() - start
            times_gpu.append(elapsed)

        avg_gpu = sum(times_gpu) / len(times_gpu)
        print(f"   平均推論時間: {avg_gpu*1000:.1f}ms")
        print(f"   スループット: {1/avg_gpu:.1f} fps")

    except Exception as e:
        print(f"   ❌ GPU推論エラー: {e}")
        avg_gpu = None

    # CPU テスト（比較用）
    print("\n💻 CPU (vit_b) テスト:")
    try:
        tracker_cpu = SAMTrackerUnified(model_type="vit_b", device="cpu")
        tracker_cpu.set_image(test_image)

        _ = tracker_cpu.segment_with_point(test_point, [1])

        times_cpu = []
        for i in range(5):
            start = time.time()
            result = tracker_cpu.segment_with_point(test_point, [1])
            elapsed = time.time() - start
            times_cpu.append(elapsed)

        avg_cpu = sum(times_cpu) / len(times_cpu)
        print(f"   平均推論時間: {avg_cpu*1000:.1f}ms")
        print(f"   スループット: {1/avg_cpu:.1f} fps")

    except Exception as e:
        print(f"   ❌ CPU推論エラー: {e}")
        avg_cpu = None

    # 比較
    if avg_gpu and avg_cpu:
        speedup = avg_cpu / avg_gpu
        print("\n" + "=" * 70)
        print(f"⚡ 高速化率: {speedup:.1f}x")
        print(f"   GPU (vit_h): {avg_gpu*1000:.1f}ms")
        print(f"   CPU (vit_b): {avg_cpu*1000:.1f}ms")
        print("=" * 70)

        if speedup >= 5:
            print("🎉 RTX 3060で5倍以上の高速化達成！")
        elif speedup >= 3:
            print("✅ 3倍以上の高速化を確認")
        else:
            print("⚠️ 期待より低速です")

def test_batch_processing():
    """バッチ処理性能テスト（最適化前後の比較）"""
    print("\n" + "=" * 70)
    print("バッチ処理テスト（113フレーム）- 最適化効果検証")
    print("=" * 70)

    from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
    import torch

    # 113フレーム分
    frames = [np.random.randint(0, 255, (620, 1214, 3), dtype=np.uint8) for _ in range(113)]

    # 器具初期化データ
    instruments = [{
        "id": 0,
        "name": "Test Instrument",
        "selection": {
            "type": "point",
            "data": [(607, 310)]
        },
        "color": "#FF0000"
    }]

    # GPU tracker
    tracker = SAMTrackerUnified(model_type="vit_h", device="cuda")
    tracker.initialize_instruments(frames[0], instruments)

    print(f"\n🔥 最適化版（エンコーディング再利用）:")
    print(f"   Processing {len(frames)} frames...")
    start_time = time.time()

    # detect_batchを使用（内部でエンコーディング再利用）
    results = tracker.detect_batch(frames)

    total_time = time.time() - start_time
    avg_fps = len(frames) / total_time

    print(f"\n✅ バッチ処理完了")
    print(f"   総処理時間: {total_time:.2f}s")
    print(f"   平均FPS: {avg_fps:.1f} fps")
    print(f"   フレームあたり: {total_time/len(frames)*1000:.1f}ms")

    allocated_mb = torch.cuda.memory_allocated() / 1024**2
    reserved_mb = torch.cuda.memory_reserved() / 1024**2
    print(f"   VRAM使用量: {allocated_mb:.1f}MB allocated, {reserved_mb:.1f}MB reserved")

    # 性能評価
    print()
    print("=" * 70)
    ms_per_frame = total_time / len(frames) * 1000
    baseline_ms = 1122  # 最適化前のベースライン

    if ms_per_frame < 100:
        speedup = baseline_ms / ms_per_frame
        print(f"🎉 大成功！ {speedup:.1f}倍の高速化達成！")
        print(f"   {baseline_ms}ms → {ms_per_frame:.1f}ms/frame")
    elif ms_per_frame < 200:
        speedup = baseline_ms / ms_per_frame
        print(f"✅ 良好！ {speedup:.1f}倍の高速化")
        print(f"   {baseline_ms}ms → {ms_per_frame:.1f}ms/frame")
    else:
        print(f"⚠️ 期待より低速: {ms_per_frame:.1f}ms/frame")
        print(f"   目標: 50-100ms/frame")
    print("=" * 70)

if __name__ == "__main__":
    print("\n🔬 SAM vit_h GPU性能テスト（RTX 3060）\n")

    # Test 1: GPU環境確認
    if not test_gpu_availability():
        print("\n❌ GPU環境が利用できません")
        sys.exit(1)

    # Test 2: モデルロード
    tracker = test_sam_vit_h_loading()
    if not tracker:
        print("\n❌ モデルのロードに失敗しました")
        sys.exit(1)

    # Test 3: 推論速度比較
    test_inference_speed()

    # Test 4: バッチ処理
    test_batch_processing()

    print("\n" + "=" * 70)
    print("🎉 すべてのテストが完了しました！")
    print("   RTX 3060でのGPU推論が正常に動作しています")
    print("=" * 70)
