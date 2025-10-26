"""
視線解析プロセッサー - DeepGaze III ベース
参考: deepgaze3_eyeeye.py

このモジュールは既存のスケルトン検出・器具検出とは完全に独立しています。
"""
import logging
import os
import urllib.request
import shutil
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

import cv2
import numpy as np
from scipy.special import logsumexp

logger = logging.getLogger(__name__)


class GazeAnalyzer:
    """
    DeepGaze IIIを使用した視線注目度（サリエンシー）分析

    主な機能:
    - サリエンシーマップ計算
    - Inhibition of Return (IOR) 適用
    - 固視点抽出
    - ヒートマップオーバーレイ生成
    - 視線プロット生成
    """

    def __init__(self, device: str = "auto"):
        """
        DeepGaze IIIモデルを初期化

        Args:
            device: "auto", "cuda", "cpu" のいずれか
        """
        self.model = None
        self.device = None
        self._initialize_model(device)

    def _initialize_model(self, device: str):
        """
        DeepGaze IIIモデルを遅延初期化

        Args:
            device: デバイス指定
        """
        try:
            import torch
            import deepgaze_pytorch

            # デバイス自動選択
            if device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self.device = device

            logger.info(f"[GAZE] Loading DeepGaze III model on {self.device}...")

            # モデル読み込み
            self.model = deepgaze_pytorch.DeepGazeIII(pretrained=True).to(self.device).eval()

            logger.info(f"[GAZE] DeepGaze III model loaded successfully on {self.device}")

        except ImportError as e:
            logger.error(f"[GAZE] deepgaze_pytorch not found: {e}")
            logger.error("[GAZE] Install with: pip install git+https://github.com/matthias-k/DeepGaze.git")
            raise
        except Exception as e:
            logger.error(f"[GAZE] Model initialization failed: {e}")
            raise

    def load_centerbias(self, h: int, w: int, cache_dir: str = ".") -> np.ndarray:
        """
        MIT1003 Center-biasマップをロード・リサイズ

        Args:
            h: 画像高さ
            w: 画像幅
            cache_dir: キャッシュディレクトリ

        Returns:
            Center-biasマップ（log空間）
        """
        cache_path = Path(cache_dir) / "centerbias_mit1003.npy"

        # ダウンロード（初回のみ）
        if not cache_path.exists():
            logger.info("[GAZE] Downloading center-bias map...")
            url = ("https://github.com/matthias-k/DeepGaze/"
                   "releases/download/v1.0.0/centerbias_mit1003.npy")
            try:
                with urllib.request.urlopen(url) as r, open(cache_path, "wb") as f:
                    shutil.copyfileobj(r, f)
                logger.info("[GAZE] Center-bias map downloaded successfully")
            except Exception as e:
                logger.error(f"[GAZE] Failed to download center-bias map: {e}")
                raise

        # ロード＆リサイズ
        cb = np.load(cache_path)
        cb_resized = cv2.resize(cb, (w, h))
        cb_resized -= logsumexp(cb_resized)  # 正規化

        return cb_resized

    def compute_saliency(
        self,
        frame: np.ndarray,
        cb_log: np.ndarray,
        seeds: List[Tuple[int, int]]
    ) -> np.ndarray:
        """
        DeepGaze IIIでサリエンシーマップを計算

        Args:
            frame: RGB画像 (H x W x 3)
            cb_log: Center-biasマップ（log空間）
            seeds: シード固視点 [(x, y), ...]

        Returns:
            サリエンシーマップ (H x W), 値範囲 [0, 1]
        """
        import torch

        # 複数シードで計算して平均化
        saliency_maps = []
        for seed_x, seed_y in seeds:
            # DeepGaze IIIは複数固視点を受け取る（最初のみ使用）
            hx = [seed_x] + [np.nan] * (len(self.model.included_fixations) - 1)
            hy = [seed_y] + [np.nan] * (len(self.model.included_fixations) - 1)

            # Tensor変換（警告を避けるため先にnumpy配列に変換）
            frame_transposed = np.array(frame.transpose(2, 0, 1))
            it = torch.tensor([frame_transposed], dtype=torch.float32).to(self.device)
            ct = torch.tensor([cb_log], dtype=torch.float32).to(self.device)
            xt = torch.tensor([hx], dtype=torch.float32).to(self.device)
            yt = torch.tensor([hy], dtype=torch.float32).to(self.device)

            # 推論
            with torch.no_grad():
                log_map = self.model(it, ct, xt, yt)[0, 0].cpu().numpy()

            saliency_maps.append(np.exp(log_map))

        # 平均化
        saliency = np.mean(saliency_maps, axis=0)
        return saliency

    def apply_ior(
        self,
        saliency: np.ndarray,
        radius: int,
        decay: float,
        n_iterations: int = 5
    ) -> np.ndarray:
        """
        Inhibition of Return (IOR) を適用
        同じ場所への注目を抑制し、視線の自然な分散を模擬

        Args:
            saliency: サリエンシーマップ
            radius: 抑制半径（ピクセル）
            decay: 減衰係数 [0, 1]
            n_iterations: 反復回数

        Returns:
            IOR適用後のサリエンシーマップ
        """
        q = saliency.copy()

        for _ in range(n_iterations):
            # 最大値の位置を取得
            y, x = np.unravel_index(q.argmax(), q.shape)

            # 抑制マスク生成
            mask = np.zeros_like(q)
            cv2.circle(mask, (x, y), radius, 1, -1)
            mask = cv2.GaussianBlur(mask, (0, 0), radius / 2)

            # 抑制適用
            q *= 1 - decay * mask

        # 正規化
        return q / (q.max() + 1e-8)

    def extract_fixations(
        self,
        saliency: np.ndarray,
        num_fixations: int,
        radius: int,
        decay: float
    ) -> List[Tuple[int, int]]:
        """
        サリエンシーマップから固視点座標を抽出

        Args:
            saliency: サリエンシーマップ
            num_fixations: 抽出する固視点数
            radius: IOR半径
            decay: IOR減衰係数

        Returns:
            固視点座標リスト [(x, y), ...]
        """
        fixations = []
        q = saliency.copy()

        for _ in range(num_fixations):
            # 最大値の位置を取得
            y, x = np.unravel_index(q.argmax(), q.shape)
            fixations.append((int(x), int(y)))  # NumPy int64をPython intに変換

            # IOR適用
            mask = np.zeros_like(q)
            cv2.circle(mask, (x, y), radius, 1, -1)
            mask = cv2.GaussianBlur(mask, (0, 0), radius / 2)
            q *= 1 - decay * mask

        return fixations

    def create_heatmap_overlay(
        self,
        frame: np.ndarray,
        saliency: np.ndarray,
        alpha: float = 0.6,
        gamma: float = 1.2,
        blur_sigma: int = 5,
        threshold: float = 0.1
    ) -> np.ndarray:
        """
        ヒートマップオーバーレイを生成

        Args:
            frame: 元のRGB画像
            saliency: サリエンシーマップ
            alpha: オーバーレイ不透明度
            gamma: ガンマ補正値（コントラスト強調）
            blur_sigma: ぼかし量
            threshold: 表示閾値（低い値を除去）

        Returns:
            ヒートマップオーバーレイ画像
        """
        h, w = frame.shape[:2]

        # ガンマ補正
        sal_gamma = np.power(saliency, gamma)

        # 閾値処理
        sal_thresh = np.where(sal_gamma > threshold, sal_gamma, 0)

        # ぼかし
        if blur_sigma > 0:
            k = max(3, int(blur_sigma * 2) // 2 * 2 + 1)
            sal_thresh = cv2.GaussianBlur(sal_thresh, (k, k), blur_sigma,
                                          borderType=cv2.BORDER_REPLICATE)

        # 正規化
        sal_final = sal_thresh / (sal_thresh.max() + 1e-8)

        # 強調
        sal_enhanced = np.power(sal_final, 0.7)

        # JETカラーマップ適用
        heatmap = cv2.applyColorMap((sal_enhanced * 255).astype(np.uint8), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # マスク生成
        heat_mask = sal_enhanced > 0.1

        # オーバーレイ
        overlay = frame.copy().astype(np.float32)
        heatmap_f = heatmap.astype(np.float32)

        for i in range(3):
            overlay[..., i] = np.where(
                heat_mask,
                frame[..., i] * (1 - alpha) + heatmap_f[..., i] * alpha,
                frame[..., i]
            )

        return overlay.astype(np.uint8)

    def create_gaze_plot(
        self,
        frame: np.ndarray,
        fixations: List[Tuple[int, int]],
        circle_size: int = 6,
        line_thickness: int = 2,
        show_numbers: bool = False
    ) -> np.ndarray:
        """
        視線プロットを生成（固視点 + 移動経路）

        Args:
            frame: 元のRGB画像
            fixations: 固視点座標リスト
            circle_size: 円のサイズ
            line_thickness: 線の太さ
            show_numbers: 固視番号を表示するか

        Returns:
            視線プロット画像
        """
        plot = frame.copy()

        # 線を描画
        for i in range(1, len(fixations)):
            cv2.line(plot, fixations[i-1], fixations[i],
                    (255, 255, 255), line_thickness + 1, cv2.LINE_AA)
            cv2.line(plot, fixations[i-1], fixations[i],
                    (0, 255, 0), line_thickness, cv2.LINE_AA)

        # 円を描画
        for i, (x, y) in enumerate(fixations):
            # 外側の白い円
            cv2.circle(plot, (x, y), circle_size + 1, (255, 255, 255), -1)
            # 内側の緑の円
            cv2.circle(plot, (x, y), circle_size, (0, 255, 0), -1)

            # 番号表示（オプション）
            if show_numbers:
                cv2.putText(plot, str(i + 1), (x + circle_size + 2, y + circle_size + 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(plot, str(i + 1), (x + circle_size + 2, y + circle_size + 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        return plot

    def analyze_frame(
        self,
        frame: np.ndarray,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        1フレーム全体を解析（統一インターフェース）

        Args:
            frame: RGB画像
            params: 解析パラメータ
                - center_bias_weight: float (default: 0.6)
                - saccade_radius: int (default: 60)
                - ior_decay: float (default: 0.9)
                - add_corner_seeds: bool (default: True)
                - num_fixations: int (default: 8)
                - gamma: float (default: 1.2)
                - blur_sigma: int (default: 5)
                - alpha: float (default: 0.6)
                - heat_threshold: float (default: 0.1)
                - circle_size: int (default: 6)
                - line_thickness: int (default: 2)
                - show_numbers: bool (default: False)

        Returns:
            解析結果辞書
                - saliency_map: np.ndarray
                - fixations: List[Tuple[int, int]]
                - heatmap_overlay: np.ndarray
                - gaze_plot: np.ndarray
                - stats: Dict (max_value, mean_value, etc.)
        """
        if params is None:
            params = {}

        h, w = frame.shape[:2]

        # パラメータ取得
        cb_weight = params.get('center_bias_weight', 0.6)
        sac_radius = params.get('saccade_radius', 60)
        ior_decay = params.get('ior_decay', 0.9)
        add_corners = params.get('add_corner_seeds', True)
        num_fix = params.get('num_fixations', 8)

        # Center-biasロード
        cb_log = self.load_centerbias(h, w) * cb_weight

        # シード設定
        seeds = [(w // 2, h // 2)]  # 中央
        if add_corners:
            seeds += [
                (w // 4, h // 4),
                (3 * w // 4, h // 4),
                (w // 4, 3 * h // 4),
                (3 * w // 4, 3 * h // 4)
            ]

        # サリエンシー計算
        saliency = self.compute_saliency(frame, cb_log, seeds)
        saliency_normalized = saliency / (saliency.max() + 1e-8)

        # IOR適用
        saliency_ior = self.apply_ior(saliency_normalized, sac_radius, ior_decay)

        # 固視点抽出
        fixations = self.extract_fixations(saliency_ior, num_fix, sac_radius, ior_decay)

        # ヒートマップオーバーレイ生成
        heatmap_overlay = self.create_heatmap_overlay(
            frame,
            saliency_ior,
            alpha=params.get('alpha', 0.6),
            gamma=params.get('gamma', 1.2),
            blur_sigma=params.get('blur_sigma', 5),
            threshold=params.get('heat_threshold', 0.1)
        )

        # 視線プロット生成
        gaze_plot = self.create_gaze_plot(
            frame,
            fixations,
            circle_size=params.get('circle_size', 6),
            line_thickness=params.get('line_thickness', 2),
            show_numbers=params.get('show_numbers', False)
        )

        # 統計情報
        stats = {
            'max_value': float(saliency_ior.max()),
            'mean_value': float(saliency_ior.mean()),
            'high_attention_ratio': float((saliency_ior > 0.5).sum() / saliency_ior.size)
        }

        return {
            'saliency_map': saliency_ior.tolist(),  # NumPy配列をリストに変換
            'fixations': fixations,  # 既にintのタプルリスト
            'heatmap_overlay': heatmap_overlay.tolist(),  # NumPy配列をリストに変換
            'gaze_plot': gaze_plot.tolist(),  # NumPy配列をリストに変換
            'stats': stats
        }
