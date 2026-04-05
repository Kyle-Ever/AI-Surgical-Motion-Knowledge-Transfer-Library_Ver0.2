"""
スコア変換モジュール — 6指標の生値を0-100スコアに変換
Layer 1 (絶対評価): 基準値なしで暫定スコアを算出
Layer 2 (相対評価): エキスパート基準値との比率でスコア算出
"""

from typing import Dict, Any, Optional

from .types import MetricResult, ExpertBaseline


class MetricScorer:
    """6指標のスコア変換"""

    # =========================================================================
    # A1: 動作経済性
    # =========================================================================

    def score_economy_of_motion(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        total_path = raw["total_path_length"]
        expert = baseline.economy_of_motion if baseline else None

        if expert is not None and expert > 0:
            ratio = total_path / expert
            score = max(0.0, min(100.0, (2.0 - ratio) * 100.0))
            mode = "relative"
        else:
            # Layer 1: ピクセル座標 vs 正規化座標で閾値切替
            # path_length > 100 → ピクセル座標（上限50000）
            # path_length <= 100 → 正規化座標（上限10.0）
            max_path = 50000.0 if total_path > 100 else 10.0
            score = max(0.0, min(100.0, (1.0 - total_path / max_path) * 100.0))
            ratio = None
            mode = "absolute"

        return MetricResult(
            metric_id="A1", metric_name="economy_of_motion",
            metric_label_ja="動作経済性", group="motion_quality",
            raw_values=raw, score=round(score, 1),
            ratio_to_expert=round(ratio, 3) if ratio is not None else None,
            evaluation_mode=mode,
        )

    # =========================================================================
    # A2: 動作滑らかさ (SPARC)
    # =========================================================================

    def score_smoothness(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        sparc = raw["sparc_value"]
        expert = baseline.sparc if baseline else None

        if expert is not None:
            if abs(expert) < 1e-6:
                ratio = 1.0
            else:
                ratio = abs(sparc) / abs(expert)
            score = max(0.0, min(100.0, (2.0 - ratio) * 100.0))
            mode = "relative"
        else:
            # Layer 1: SPARC -1→100点, -7→0点 の線形マッピング
            score = max(0.0, min(100.0, (sparc + 7.0) / 6.0 * 100.0))
            ratio = None
            mode = "absolute"

        return MetricResult(
            metric_id="A2", metric_name="smoothness",
            metric_label_ja="動作滑らかさ", group="motion_quality",
            raw_values=raw, score=round(score, 1),
            ratio_to_expert=round(ratio, 3) if ratio is not None else None,
            evaluation_mode=mode,
        )

    # =========================================================================
    # A3: 両手協調性
    # =========================================================================

    # 両手検出率がこの閾値以下の場合、A3はN/A扱い
    A3_MIN_DETECTION_RATIO = 0.3

    def score_bimanual_coordination(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        coord = raw["coordination_value"]
        both_ratio = raw.get("both_hands_detected_ratio", 0)
        expert = baseline.bimanual_coordination if baseline else None

        # 両手検出率が低い場合はN/A（スコアに-1を設定してフロントで判定）
        if both_ratio < self.A3_MIN_DETECTION_RATIO:
            return MetricResult(
                metric_id="A3", metric_name="bimanual_coordination",
                metric_label_ja="両手協調性", group="motion_quality",
                raw_values={**raw, "insufficient_data": True},
                score=-1.0,  # N/Aフラグ
                ratio_to_expert=None,
                evaluation_mode="insufficient_data",
            )

        if expert is not None and expert > 0:
            ratio = coord / expert
            score = max(0.0, min(100.0, ratio * 100.0))
            mode = "relative"
        else:
            # Layer 1: coordination_value (0-1) → 0-100
            score = coord * 100.0
            ratio = None
            mode = "absolute"

        return MetricResult(
            metric_id="A3", metric_name="bimanual_coordination",
            metric_label_ja="両手協調性", group="motion_quality",
            raw_values=raw, score=round(score, 1),
            ratio_to_expert=round(ratio, 3) if ratio is not None else None,
            evaluation_mode=mode,
        )

    # =========================================================================
    # B1: ロスタイム
    # =========================================================================

    def score_lost_time(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        lost_ratio = raw["lost_time_ratio"]
        expert = baseline.lost_time_ratio if baseline else None

        if expert is not None:
            if expert < 1e-6:
                score = max(0.0, (1.0 - lost_ratio * 10) * 100.0)
                ratio = None
            else:
                ratio = lost_ratio / expert
                score = max(0.0, min(100.0, (2.0 - ratio) * 100.0))
            mode = "relative"
        else:
            # Layer 1: ratio 0%→100点, 30%以上→0点
            score = max(0.0, min(100.0, (1.0 - lost_ratio / 0.30) * 100.0))
            ratio = None
            mode = "absolute"

        return MetricResult(
            metric_id="B1", metric_name="lost_time",
            metric_label_ja="ロスタイム", group="waste_detection",
            raw_values=raw, score=round(score, 1),
            ratio_to_expert=round(ratio, 3) if ratio is not None else None,
            evaluation_mode=mode,
        )

    # =========================================================================
    # B2: 動作回数効率
    # =========================================================================

    def score_movement_count(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        mpm = raw["movements_per_minute"]
        expert = baseline.movements_per_minute if baseline else None

        if expert is not None and expert > 0:
            ratio = mpm / expert
            score = max(0.0, min(100.0, (2.0 - ratio) * 100.0))
            mode = "relative"
        else:
            # Layer 1: 暫定60回/分上限
            ratio_val = min(mpm / 60.0, 1.0)
            score = (1.0 - ratio_val) * 100.0
            ratio = None
            mode = "absolute"

        return MetricResult(
            metric_id="B2", metric_name="movement_count",
            metric_label_ja="動作回数効率", group="waste_detection",
            raw_values=raw, score=round(max(score, 0.0), 1),
            ratio_to_expert=round(ratio, 3) if ratio is not None else None,
            evaluation_mode=mode,
        )

    # =========================================================================
    # B3: 作業空間偏差
    # =========================================================================

    def score_working_volume(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        hull_area = raw["convex_hull_area"]
        expert = baseline.working_volume_area if baseline else None

        if expert is not None and expert > 0:
            ratio = hull_area / expert
            # 双方向: 1.0が中心、上下どちらに離れても減点
            deviation = abs(ratio - 1.0)
            score = max(0.0, min(100.0, (1.0 - deviation) * 100.0))
            direction = "larger" if ratio > 1.0 else "smaller" if ratio < 1.0 else "equal"
            mode = "relative"
        else:
            # Layer 1: 暫定の一方向評価
            if hull_area > 100:
                max_area = 500000.0  # ピクセル座標
            else:
                max_area = 0.10      # 正規化座標
            r = min(hull_area / max_area, 1.0) if max_area > 0 else 0
            score = (1.0 - r) * 100.0
            ratio = None
            direction = None
            mode = "absolute"

        result = MetricResult(
            metric_id="B3", metric_name="working_volume",
            metric_label_ja="作業空間偏差", group="waste_detection",
            raw_values=raw, score=round(max(score, 0.0), 1),
            ratio_to_expert=round(ratio, 3) if ratio is not None else None,
            evaluation_mode=mode,
        )
        # 追加情報
        if direction:
            result.raw_values["deviation_direction"] = direction
        return result
