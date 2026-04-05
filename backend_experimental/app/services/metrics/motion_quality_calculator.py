"""
Group A: 動作品質 (Motion Quality)
  A1: 動作経済性 (Economy of Motion) — 総移動距離
  A2: 動作滑らかさ (Smoothness / SPARC) — スペクトル弧長
  A3: 両手協調性 (Bimanual Coordination) — 速度相互相関
"""

import numpy as np
from typing import List, Dict, Any, Optional
import logging

from .types import PreprocessedData

logger = logging.getLogger(__name__)


class MotionQualityCalculator:
    """Group A: 動作品質の3指標を計算"""

    def __init__(self, fps: float = 30.0):
        self.fps = fps

    # =========================================================================
    # A1: 動作経済性 (Economy of Motion)
    # =========================================================================

    def economy_of_motion(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        A1: 総移動距離ベースの動作経済性

        JIGSAWSデータセットで最も判別力が高い指標。
        エキスパートは必要最小限の動作で手技を完了するため、総移動距離が短い。
        """
        left_path = self._path_length(data.left_positions)
        right_path = self._path_length(data.right_positions)
        total_path = left_path + right_path

        duration = data.total_duration_seconds
        path_per_sec = total_path / duration if duration > 0 else 0

        return {
            "total_path_length": round(total_path, 4),
            "left_path_length": round(left_path, 4),
            "right_path_length": round(right_path, 4),
            "path_length_per_second": round(path_per_sec, 4),
            "total_duration_seconds": duration,
        }

    @staticmethod
    def _path_length(positions: List[Optional[Dict[str, float]]]) -> float:
        total = 0.0
        prev = None
        for p in positions:
            if p is not None and prev is not None:
                dx = p["x"] - prev["x"]
                dy = p["y"] - prev["y"]
                total += np.sqrt(dx ** 2 + dy ** 2)
            if p is not None:
                prev = p
        return total

    # =========================================================================
    # A2: 動作滑らかさ (SPARC — Spectral Arc Length)
    # =========================================================================

    def smoothness_sparc(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        A2: SPARC (Spectral Arc Length)

        Balasubramanian et al., 2012, 2015 に基づく。
        速度プロファイルの周波数スペクトルの弧長で滑らかさを評価。
        滑らかな動き → 周波数成分が単純 → スペクトル弧長が短い（0に近い）。

        SPARC値の一般的な範囲:
          -1.0付近: 非常に滑らか（単一ベル型速度プロファイル）
          -4.0付近: 中程度
          -7.0付近: 非常にぎこちない（多数のサブムーブメント）
        """
        # 左右の手それぞれでSPARCを計算し、平均
        left_sparc = self._calculate_sparc(data.left_velocities)
        right_sparc = self._calculate_sparc(data.right_velocities)

        # 有効な方のみで平均
        valid = [v for v in [left_sparc, right_sparc] if v is not None]
        avg_sparc = np.mean(valid) if valid else -7.0

        return {
            "sparc_value": round(float(avg_sparc), 4),
            "left_sparc": round(float(left_sparc), 4) if left_sparc is not None else None,
            "right_sparc": round(float(right_sparc), 4) if right_sparc is not None else None,
        }

    def _calculate_sparc(
        self,
        velocities: List[Optional[float]],
        freq_cutoff: float = 20.0,
        amplitude_threshold: float = 0.05,
    ) -> Optional[float]:
        """単一の手のSPARCを計算"""
        valid = np.array([v for v in velocities if v is not None], dtype=float)
        if len(valid) < 4:
            return None

        # 速度ピークで正規化
        v_peak = np.max(np.abs(valid))
        if v_peak < 1e-9:
            return -7.0
        v_norm = valid / v_peak

        # FFT
        N = len(v_norm)
        V = np.fft.rfft(v_norm)
        freqs = np.fft.rfftfreq(N, d=1.0 / self.fps)
        V_mag = np.abs(V)
        V_mag_norm = V_mag / (V_mag[0] if V_mag[0] > 0 else 1.0)

        # 適応カットオフ: 振幅が閾値を下回る最初の周波数
        adaptive_cutoff = freq_cutoff
        for i, amp in enumerate(V_mag_norm):
            if freqs[i] > 1.0 and amp < amplitude_threshold:
                adaptive_cutoff = freqs[i]
                break

        actual_cutoff = min(freq_cutoff, adaptive_cutoff)
        mask = freqs <= actual_cutoff
        V_masked = V_mag_norm[mask]
        f_masked = freqs[mask]

        if len(f_masked) < 2:
            return -7.0

        # スペクトル弧長
        dfreq = np.diff(f_masked)
        dV = np.diff(V_masked)
        arc_length = -float(np.sum(np.sqrt(dfreq ** 2 + dV ** 2)))

        return arc_length

    # =========================================================================
    # A3: 両手協調性 (Bimanual Coordination)
    # =========================================================================

    def bimanual_coordination(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        A3: 両手協調性

        2つのサブ指標:
        1. velocity_correlation: 速度プロファイルの正規化相互相関（タイミング同期度）
        2. balance_ratio: 速度比の安定性（左右のバランス）

        GEARSのBimanual Dexterity評価軸に対応。
        """
        paired = []
        both_detected = 0
        total = max(len(data.left_velocities), len(data.right_velocities))

        for l, r in zip(data.left_velocities, data.right_velocities):
            if l is not None and r is not None:
                paired.append((l, r))
                both_detected += 1

        both_ratio = both_detected / total if total > 0 else 0

        if len(paired) < 10:
            return {
                "coordination_value": 0.0,
                "velocity_correlation": 0.0,
                "balance_ratio": 0.0,
                "both_hands_detected_ratio": round(both_ratio, 3),
            }

        left_arr = np.array([p[0] for p in paired])
        right_arr = np.array([p[1] for p in paired])

        # サブ指標1: 速度相互相関
        if np.std(left_arr) < 1e-6 or np.std(right_arr) < 1e-6:
            correlation = 0.0
        else:
            correlation = float(np.corrcoef(left_arr, right_arr)[0, 1])
            if np.isnan(correlation):
                correlation = 0.0

        # サブ指標2: 速度バランス
        max_vals = np.maximum(left_arr, right_arr) + 1e-9
        min_vals = np.minimum(left_arr, right_arr)
        balance = float(np.mean(min_vals / max_vals))

        # 複合（相関60% + バランス40%）
        coordination = 0.6 * max(0.0, correlation) + 0.4 * balance

        return {
            "coordination_value": round(coordination, 4),
            "velocity_correlation": round(correlation, 4),
            "balance_ratio": round(balance, 4),
            "both_hands_detected_ratio": round(both_ratio, 3),
        }
