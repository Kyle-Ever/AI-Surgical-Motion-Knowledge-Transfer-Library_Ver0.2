"""
視線解析プロセッサー（GazeAnalyzer）のユニットテスト

このテストは新規実装の視線解析機能を検証し、既存システムへの影響がないことを確認します。
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from app.ai_engine.processors.gaze_analyzer import GazeAnalyzer


class TestGazeAnalyzerInitialization:
    """GazeAnalyzerの初期化テスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def test_init_with_auto_device_cuda_available(self, mock_deepgaze, mock_torch):
        """自動デバイス選択でCUDA利用可能な場合"""
        mock_torch.cuda.is_available.return_value = True
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model

        analyzer = GazeAnalyzer(device="auto")

        assert analyzer.device == "cuda"
        mock_deepgaze.DeepGazeIII.assert_called_once_with(pretrained=True)
        mock_model.to.assert_called_once_with("cuda")
        mock_model.eval.assert_called_once()

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def test_init_with_auto_device_cuda_unavailable(self, mock_deepgaze, mock_torch):
        """自動デバイス選択でCUDA利用不可能な場合"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model

        analyzer = GazeAnalyzer(device="auto")

        assert analyzer.device == "cpu"
        mock_model.to.assert_called_once_with("cpu")

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def test_init_with_explicit_cpu_device(self, mock_deepgaze, mock_torch):
        """明示的にCPUを指定した場合"""
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model

        analyzer = GazeAnalyzer(device="cpu")

        assert analyzer.device == "cpu"
        mock_model.to.assert_called_once_with("cpu")

    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch', side_effect=ImportError("deepgaze not found"))
    def test_init_fails_when_deepgaze_not_installed(self, mock_deepgaze):
        """DeepGazeがインストールされていない場合のエラーハンドリング"""
        with pytest.raises(ImportError):
            GazeAnalyzer()


class TestCenterBiasLoading:
    """Center-biasマップのロード・キャッシュ機能テスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model
        self.analyzer = GazeAnalyzer(device="cpu")

    @patch('app.ai_engine.processors.gaze_analyzer.np.load')
    @patch('app.ai_engine.processors.gaze_analyzer.cv2.resize')
    @patch('app.ai_engine.processors.gaze_analyzer.logsumexp')
    @patch('app.ai_engine.processors.gaze_analyzer.Path')
    def test_load_centerbias_from_cache(self, mock_path, mock_logsumexp, mock_resize, mock_load):
        """既存のキャッシュファイルから読み込み"""
        # キャッシュファイルが存在する場合
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = True
        mock_path.return_value = mock_path_obj

        # ロードされたデータ
        mock_cb_data = np.random.rand(100, 100)
        mock_load.return_value = mock_cb_data

        # リサイズされたデータ
        mock_resized = np.random.rand(480, 640)
        mock_resize.return_value = mock_resized

        # logsumexpの戻り値
        mock_logsumexp.return_value = 0.5

        result = self.analyzer.load_centerbias(480, 640, cache_dir=".")

        mock_load.assert_called_once()
        mock_resize.assert_called_once_with(mock_cb_data, (640, 480))
        mock_logsumexp.assert_called_once()
        assert result is not None

    @patch('app.ai_engine.processors.gaze_analyzer.urllib.request.urlopen')
    @patch('app.ai_engine.processors.gaze_analyzer.Path')
    @patch('builtins.open', create=True)
    @patch('app.ai_engine.processors.gaze_analyzer.shutil.copyfileobj')
    @patch('app.ai_engine.processors.gaze_analyzer.np.load')
    @patch('app.ai_engine.processors.gaze_analyzer.cv2.resize')
    @patch('app.ai_engine.processors.gaze_analyzer.logsumexp')
    def test_load_centerbias_downloads_if_missing(
        self, mock_logsumexp, mock_resize, mock_load, mock_copyfileobj,
        mock_open_file, mock_path, mock_urlopen
    ):
        """キャッシュファイルがない場合はダウンロード"""
        # キャッシュファイルが存在しない
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = False
        mock_path.return_value = mock_path_obj

        # URLオープンのモック
        mock_response = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # ファイルオープンのモック
        mock_file = MagicMock()
        mock_open_file.return_value.__enter__.return_value = mock_file

        # ロードとリサイズのモック
        mock_cb_data = np.random.rand(100, 100)
        mock_load.return_value = mock_cb_data
        mock_resized = np.random.rand(480, 640)
        mock_resize.return_value = mock_resized
        mock_logsumexp.return_value = 0.5

        result = self.analyzer.load_centerbias(480, 640, cache_dir=".")

        # ダウンロードが実行されたことを確認
        mock_urlopen.assert_called_once()
        mock_copyfileobj.assert_called_once()
        assert result is not None


class TestSaliencyComputation:
    """サリエンシーマップ計算のテスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False

        # モデルのモック
        self.mock_model = MagicMock()
        self.mock_model.included_fixations = [1, 2, 3]  # 3 fixations required
        mock_deepgaze.DeepGazeIII.return_value = self.mock_model

        # torchのモック設定
        mock_torch.tensor.return_value = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        self.analyzer = GazeAnalyzer(device="cpu")

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    def test_compute_saliency_single_seed(self, mock_torch):
        """単一シードでのサリエンシー計算"""
        # 入力データ
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cb_log = np.random.rand(480, 640)
        seeds = [(320, 240)]

        # Tensorモック
        mock_tensor = MagicMock()
        mock_tensor.cpu.return_value.numpy.return_value = np.random.rand(480, 640)
        mock_torch.tensor.return_value = mock_tensor

        # モデルの推論結果をモック
        mock_output = MagicMock()
        mock_output.__getitem__.return_value.__getitem__.return_value = mock_tensor
        self.mock_model.return_value = mock_output

        result = self.analyzer.compute_saliency(frame, cb_log, seeds)

        assert result is not None
        assert result.shape == (480, 640)
        assert np.all(result >= 0)
        assert np.all(result <= 1)

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    def test_compute_saliency_multiple_seeds(self, mock_torch):
        """複数シードでのサリエンシー計算（平均化）"""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cb_log = np.random.rand(480, 640)
        seeds = [(320, 240), (160, 120), (480, 360)]

        # Tensorモック
        mock_tensor = MagicMock()
        mock_tensor.cpu.return_value.numpy.return_value = np.random.rand(480, 640)
        mock_torch.tensor.return_value = mock_tensor

        # モデルの推論結果をモック
        mock_output = MagicMock()
        mock_output.__getitem__.return_value.__getitem__.return_value = mock_tensor
        self.mock_model.return_value = mock_output

        result = self.analyzer.compute_saliency(frame, cb_log, seeds)

        # 3つのシードで3回推論が実行されるべき
        assert self.mock_model.call_count == 3
        assert result is not None


class TestIORApplication:
    """Inhibition of Return (IOR) のテスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model
        self.analyzer = GazeAnalyzer(device="cpu")

    def test_apply_ior_reduces_peak_values(self):
        """IOR適用後、ピーク値が減少すること"""
        # 中央にピークを持つサリエンシーマップ
        saliency = np.zeros((480, 640))
        saliency[240, 320] = 1.0  # 中央にピーク
        saliency[240:260, 310:330] = 0.8  # 周辺も高い

        result = self.analyzer.apply_ior(
            saliency,
            radius=30,
            decay=0.9,
            n_iterations=3
        )

        # ピーク周辺が抑制されているべき
        assert result[240, 320] < saliency[240, 320]
        # 正規化されているべき
        assert result.max() <= 1.0
        assert result.min() >= 0.0

    def test_apply_ior_with_zero_iterations(self):
        """反復回数0の場合は正規化のみ"""
        saliency = np.random.rand(100, 100)
        original_max_pos = np.unravel_index(saliency.argmax(), saliency.shape)

        result = self.analyzer.apply_ior(
            saliency,
            radius=10,
            decay=0.5,
            n_iterations=0
        )

        # 最大値の位置は変わらないはず（正規化のみ）
        result_max_pos = np.unravel_index(result.argmax(), result.shape)
        assert original_max_pos == result_max_pos


class TestFixationExtraction:
    """固視点抽出のテスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model
        self.analyzer = GazeAnalyzer(device="cpu")

    def test_extract_fixations_returns_correct_number(self):
        """指定された数の固視点が返されること"""
        saliency = np.random.rand(480, 640)
        num_fixations = 5

        result = self.analyzer.extract_fixations(
            saliency,
            num_fixations=num_fixations,
            radius=30,
            decay=0.9
        )

        assert len(result) == num_fixations
        assert all(isinstance(point, tuple) for point in result)
        assert all(len(point) == 2 for point in result)

    def test_extract_fixations_coordinates_within_bounds(self):
        """固視点の座標が画像範囲内であること"""
        h, w = 480, 640
        saliency = np.random.rand(h, w)

        result = self.analyzer.extract_fixations(
            saliency,
            num_fixations=8,
            radius=30,
            decay=0.9
        )

        for x, y in result:
            assert 0 <= x < w
            assert 0 <= y < h


class TestHeatmapOverlay:
    """ヒートマップオーバーレイ生成のテスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model
        self.analyzer = GazeAnalyzer(device="cpu")

    def test_create_heatmap_overlay_output_shape(self):
        """ヒートマップオーバーレイの出力形状が正しいこと"""
        h, w = 480, 640
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        saliency = np.random.rand(h, w)

        result = self.analyzer.create_heatmap_overlay(
            frame, saliency,
            alpha=0.6,
            gamma=1.2,
            blur_sigma=5,
            threshold=0.1
        )

        assert result.shape == (h, w, 3)
        assert result.dtype == np.uint8

    def test_create_heatmap_overlay_preserves_low_saliency_areas(self):
        """低サリエンシー領域では元のフレームが保持されること"""
        h, w = 100, 100
        frame = np.full((h, w, 3), 128, dtype=np.uint8)  # グレー
        saliency = np.zeros((h, w))  # 全て0（注目なし）

        result = self.analyzer.create_heatmap_overlay(
            frame, saliency,
            alpha=0.6,
            threshold=0.1
        )

        # 低サリエンシーなので元のフレームとほぼ同じはず
        assert np.allclose(result, frame, atol=10)


class TestGazePlot:
    """視線プロット生成のテスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model
        self.analyzer = GazeAnalyzer(device="cpu")

    def test_create_gaze_plot_output_shape(self):
        """視線プロットの出力形状が正しいこと"""
        h, w = 480, 640
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        fixations = [(320, 240), (400, 300), (200, 150)]

        result = self.analyzer.create_gaze_plot(
            frame, fixations,
            circle_size=6,
            line_thickness=2,
            show_numbers=False
        )

        assert result.shape == (h, w, 3)
        assert result.dtype == np.uint8

    def test_create_gaze_plot_with_empty_fixations(self):
        """固視点が空の場合でもエラーにならないこと"""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        fixations = []

        result = self.analyzer.create_gaze_plot(frame, fixations)

        # 元のフレームがコピーされて返されるべき
        assert result.shape == frame.shape


class TestAnalyzeFrame:
    """フレーム全体解析の統合テスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False

        self.mock_model = MagicMock()
        self.mock_model.included_fixations = [1, 2, 3]
        mock_deepgaze.DeepGazeIII.return_value = self.mock_model

        # torchのテンソルモック
        mock_tensor = MagicMock()
        mock_tensor.cpu.return_value.numpy.return_value = np.random.rand(480, 640)
        mock_torch.tensor.return_value = mock_tensor

        # モデルの推論結果
        mock_output = MagicMock()
        mock_output.__getitem__.return_value.__getitem__.return_value = mock_tensor
        self.mock_model.return_value = mock_output

        self.analyzer = GazeAnalyzer(device="cpu")

    @patch('app.ai_engine.processors.gaze_analyzer.GazeAnalyzer.load_centerbias')
    def test_analyze_frame_returns_all_required_fields(self, mock_load_centerbias):
        """analyze_frameが必要な全てのフィールドを返すこと"""
        # Center-biasモック
        mock_load_centerbias.return_value = np.random.rand(480, 640)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        params = {
            'num_fixations': 8,
            'gamma': 1.2,
            'blur_sigma': 5
        }

        result = self.analyzer.analyze_frame(frame, params)

        # 必須フィールドの存在確認
        assert 'saliency_map' in result
        assert 'fixations' in result
        assert 'heatmap_overlay' in result
        assert 'gaze_plot' in result
        assert 'stats' in result

        # statsの内容確認
        assert 'max_value' in result['stats']
        assert 'mean_value' in result['stats']
        assert 'high_attention_ratio' in result['stats']

    @patch('app.ai_engine.processors.gaze_analyzer.GazeAnalyzer.load_centerbias')
    def test_analyze_frame_with_default_params(self, mock_load_centerbias):
        """デフォルトパラメータでの解析"""
        mock_load_centerbias.return_value = np.random.rand(480, 640)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # パラメータなし
        result = self.analyzer.analyze_frame(frame, params=None)

        assert result is not None
        assert len(result['fixations']) == 8  # デフォルト値


class TestFailFastValidation:
    """Fail Fast原則のバリデーションテスト"""

    @patch('app.ai_engine.processors.gaze_analyzer.torch')
    @patch('app.ai_engine.processors.gaze_analyzer.deepgaze_pytorch')
    def setup_method(self, method, mock_deepgaze, mock_torch):
        """各テストの前にGazeAnalyzerを初期化"""
        mock_torch.cuda.is_available.return_value = False
        mock_model = MagicMock()
        mock_deepgaze.DeepGazeIII.return_value = mock_model
        self.analyzer = GazeAnalyzer(device="cpu")

    def test_compute_saliency_validates_empty_seeds(self):
        """シードが空の場合は適切にエラーを出すこと"""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cb_log = np.random.rand(480, 640)
        seeds = []

        # 空のシードリストでエラーまたは適切なデフォルト動作
        # （実装によってはデフォルトシードを使用する設計も可能）
        try:
            result = self.analyzer.compute_saliency(frame, cb_log, seeds)
            # エラーにならない場合、デフォルト動作があるはず
            assert result is not None
        except (ValueError, IndexError) as e:
            # エラーになる場合、明確なメッセージがあるべき
            assert "seed" in str(e).lower() or "empty" in str(e).lower()

    def test_extract_fixations_validates_num_fixations(self):
        """固視点数が不正な場合のバリデーション"""
        saliency = np.random.rand(100, 100)

        # 負の値
        with pytest.raises((ValueError, AssertionError)):
            self.analyzer.extract_fixations(saliency, num_fixations=-1, radius=10, decay=0.5)

        # ゼロ
        result = self.analyzer.extract_fixations(saliency, num_fixations=0, radius=10, decay=0.5)
        assert len(result) == 0


# 統合テスト: 既存システムへの非干渉確認
class TestNonInterferenceWithExistingSystems:
    """既存システムへの影響がないことを確認するテスト"""

    def test_gaze_analyzer_import_does_not_affect_skeleton_detector(self):
        """GazeAnalyzerのインポートがSkeletonDetectorに影響しないこと"""
        try:
            from app.ai_engine.processors.gaze_analyzer import GazeAnalyzer
            from app.ai_engine.processors.skeleton_detector import SkeletonDetector

            # 両方インポート可能
            assert GazeAnalyzer is not None
            assert SkeletonDetector is not None
        except ImportError as e:
            pytest.fail(f"Import interference detected: {e}")

    def test_gaze_analyzer_import_does_not_affect_sam_tracker(self):
        """GazeAnalyzerのインポートがSAMTrackerに影響しないこと"""
        try:
            from app.ai_engine.processors.gaze_analyzer import GazeAnalyzer
            from app.ai_engine.processors.sam_tracker import SAMTracker

            # 両方インポート可能
            assert GazeAnalyzer is not None
            assert SAMTracker is not None
        except ImportError as e:
            pytest.fail(f"Import interference detected: {e}")

    def test_video_type_enum_backwards_compatible(self):
        """VideoType enumの後方互換性確認"""
        from app.models.video import VideoType

        # 既存の4つのタイプが存在すること
        assert VideoType.INTERNAL.value == "internal"
        assert VideoType.EXTERNAL.value == "external"
        assert VideoType.EXTERNAL_NO_INSTRUMENTS.value == "external_no_instruments"
        assert VideoType.EXTERNAL_WITH_INSTRUMENTS.value == "external_with_instruments"

        # 新しいタイプも存在すること
        assert VideoType.EYE_GAZE.value == "eye_gaze"

        # 全部で5つのタイプ
        assert len(VideoType) == 5
