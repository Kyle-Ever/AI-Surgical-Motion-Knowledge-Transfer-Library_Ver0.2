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

    def __init__(self, fps: float = 30.0, config: Dict[str, Any] = None):
        self.fps = fps
        sp = config.get("sparc", {}) if config else {}
        sc = config.get("scoring", {}) if config else {}
        self.sparc_freq_cutoff = sp.get("freq_cutoff_hz", 20.0)
        self.sparc_amp_threshold = sp.get("amplitude_threshold", 0.05)
        self.a3_corr_weight = sc.get("a3_correlation_weight", 0.60)
        self.a3_bal_weight = sc.get("a3_balance_weight", 0.40)
        self.a3_min_both_ratio = sc.get("a3_both_hands_min_ratio", 0.30)

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
        left_sparc = self._calculate_sparc(
            data.left_velocities, self.sparc_freq_cutoff, self.sparc_amp_threshold)
        right_sparc = self._calculate_sparc(
            data.right_velocities, self.sparc_freq_cutoff, self.sparc_amp_threshold)

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

        # 外れ値クリップ（P99）: MediaPipeの一時的な誤検出による
        # 極端なスパイクがSPARCを不当に悪化させるのを防止
        if len(valid) > 20:
            p99 = np.percentile(valid, 99)
            valid = np.clip(valid, 0, p99)

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

        GOALSフレームワーク (Vassiliou et al. 2005) の "bimanual dexterity" に対応。

        両手が十分に検出されている場合:
          2つのサブ指標の重み付き複合:
          1. velocity_correlation: 速度プロファイルの相互相関（タイミング同期度）
          2. balance_ratio: 速度比の安定性（左右のバランス）

        両手検出率が低い場合（片手保持フォールバック）:
          手術では片手が組織を保持（静止）し、他方が操作するのが正常。
          非操作手の位置安定性を評価する:
          - 検出されている手の位置分散が小さい = 安定した保持 = 高スコア
          evaluation_mode を "holding_stability" に設定して区別する。
        """
        paired = []
        both_detected = 0
        total = max(len(data.left_velocities), len(data.right_velocities))

        for l, r in zip(data.left_velocities, data.right_velocities):
            if l is not None and r is not None:
                paired.append((l, r))
                both_detected += 1

        both_ratio = both_detected / total if total > 0 else 0

        # 速度比による片手保持パターン検出
        # 左右の平均速度比が大きい場合は、検出率に関係なく片手保持モードに
        is_holding_pattern = False
        velocity_ratio = None
        if len(paired) >= 10:
            left_arr_check = np.array([p[0] for p in paired])
            right_arr_check = np.array([p[1] for p in paired])
            left_mean = float(np.mean(left_arr_check))
            right_mean = float(np.mean(right_arr_check))
            if left_mean > 0 and right_mean > 0:
                velocity_ratio = max(left_mean, right_mean) / min(left_mean, right_mean)
                # 速度比が3倍以上 → 片手が操作、他方が保持のパターン
                if velocity_ratio >= 3.0:
                    is_holding_pattern = True
                    logger.info(
                        f"[A3] Holding pattern detected: velocity ratio={velocity_ratio:.1f} "
                        f"(left={left_mean:.1f}, right={right_mean:.1f})"
                    )

        # 両手検出率が十分 かつ 片手保持パターンでない場合: 速度相関+バランス
        if len(paired) >= 10 and both_ratio >= self.a3_min_both_ratio and not is_holding_pattern:
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

            # 複合（相関 + バランスの重み付き）
            coordination = self.a3_corr_weight * max(0.0, correlation) + self.a3_bal_weight * balance

            return {
                "coordination_value": round(coordination, 4),
                "velocity_correlation": round(correlation, 4),
                "balance_ratio": round(balance, 4),
                "both_hands_detected_ratio": round(both_ratio, 3),
                "evaluation_method": "bimanual_correlation",
            }

        # フォールバック: 片手保持安定性
        # 検出数が多い方の手を「操作手」、少ない方を「保持手」と推定
        # 保持手の位置分散が小さければ安定した保持 = 良好な協調
        result = self._holding_stability_fallback(data, both_ratio)
        if velocity_ratio is not None:
            result["velocity_ratio"] = round(velocity_ratio, 2)
        return result

    def _holding_stability_fallback(
        self, data: PreprocessedData, both_ratio: float
    ) -> Dict[str, Any]:
        """
        片手保持安定性のフォールバック計算

        片手が操作、他方が保持（静止）する手技パターンを評価。
        保持手の位置分散が小さいほど高スコア。
        """
        # 各手の有効フレーム数を比較
        left_valid = [p for p in data.left_positions if p is not None]
        right_valid = [p for p in data.right_positions if p is not None]

        if len(left_valid) < 5 and len(right_valid) < 5:
            return {
                "coordination_value": 0.0,
                "holding_stability": 0.0,
                "both_hands_detected_ratio": round(both_ratio, 3),
                "evaluation_method": "insufficient_data",
                "insufficient_data": True,
            }

        # 検出数が少ない手を「保持手」と推定
        # 両方十分にある場合は速度が低い方を保持手とする
        left_vels = [v for v in data.left_velocities if v is not None]
        right_vels = [v for v in data.right_velocities if v is not None]

        left_mean_vel = np.mean(left_vels) if left_vels else float("inf")
        right_mean_vel = np.mean(right_vels) if right_vels else float("inf")

        if len(left_valid) >= 5 and len(right_valid) >= 5:
            # 両方検出されている場合、速度が低い方が保持手
            holding_positions = left_valid if left_mean_vel <= right_mean_vel else right_valid
        elif len(left_valid) >= 5:
            holding_positions = left_valid
        else:
            holding_positions = right_valid

        # 保持手の位置分散を計算（正規化）
        xs = np.array([p["x"] for p in holding_positions])
        ys = np.array([p["y"] for p in holding_positions])
        variance = float(np.var(xs) + np.var(ys))

        # 分散をスコアに変換（小さい分散 = 高い安定性）
        # ピクセル座標と正規化座標で閾値を変更
        if data.is_pixel_coords:
            max_variance = 5000.0  # ピクセル座標時の分散上限
        else:
            max_variance = 0.01  # 正規化座標時の分散上限

        stability = max(0.0, min(1.0, 1.0 - variance / max_variance))

        return {
            "coordination_value": round(stability, 4),
            "holding_stability": round(stability, 4),
            "holding_variance": round(variance, 6),
            "both_hands_detected_ratio": round(both_ratio, 3),
            "evaluation_method": "holding_stability",
        }
