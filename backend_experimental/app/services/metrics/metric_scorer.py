"""
スコア変換モジュール — 6指標の生値を0-100スコアに変換
Layer 1 (絶対評価): 基準値なしで暫定スコアを算出
Layer 2 (相対評価): エキスパート基準値との比率でスコア算出
"""

from typing import Dict, Any, Optional

from .types import MetricResult, ExpertBaseline


class MetricScorer:
    """6指標のスコア変換"""

    def __init__(self, config: Dict[str, Any] = None):
        s = config.get("scoring", {}) if config else {}
        self.a1_max_path_pixel = s.get("a1_max_path_pixel", 50000.0)
        self.a1_max_path_normalized = s.get("a1_max_path_normalized", 10.0)
        self.a2_sparc_min = s.get("a2_sparc_min", -7.0)
        self.a2_sparc_max = s.get("a2_sparc_max", -1.0)
        self.a3_both_hands_min_ratio = s.get("a3_both_hands_min_ratio", 0.30)
        self.a3_corr_weight = s.get("a3_correlation_weight", 0.60)
        self.a3_bal_weight = s.get("a3_balance_weight", 0.40)
        self.b1_max_idle_ratio = s.get("b1_max_idle_ratio", 0.30)
        self.b2_max_mpm = s.get("b2_max_movements_per_minute", 60.0)
        self.b3_max_area_pixel = s.get("b3_max_area_pixel", 500000.0)
        self.b3_max_area_normalized = s.get("b3_max_area_normalized", 0.10)

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
            max_path = self.a1_max_path_pixel if total_path > 100 else self.a1_max_path_normalized
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
            # Layer 1: SPARC sparc_max→100点, sparc_min→0点 の線形マッピング
            sparc_range = self.a2_sparc_max - self.a2_sparc_min
            score = max(0.0, min(100.0, (sparc - self.a2_sparc_min) / sparc_range * 100.0)) if sparc_range != 0 else 50.0
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

    def score_bimanual_coordination(
        self, raw: Dict[str, Any], baseline: Optional[ExpertBaseline] = None
    ) -> MetricResult:
        coord = raw["coordination_value"]
        eval_method = raw.get("evaluation_method", "bimanual_correlation")
        expert = baseline.bimanual_coordination if baseline else None

        # データ不足の場合はN/A
        if raw.get("insufficient_data"):
            return MetricResult(
                metric_id="A3", metric_name="bimanual_coordination",
                metric_label_ja="両手協調性", group="motion_quality",
                raw_values=raw,
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
            # bimanual_correlationでもholding_stabilityでも同じスケール
            score = coord * 100.0
            ratio = None
            mode = "absolute"

        # 評価手法を記録（フロントで表示切替に使用）
        if eval_method == "holding_stability":
            mode = f"{mode}_holding"

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
            # Layer 1: ratio 0%→100点, max_idle_ratio以上→0点
            score = max(0.0, min(100.0, (1.0 - lost_ratio / self.b1_max_idle_ratio) * 100.0))
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
            # Layer 1: max_mpm上限
            ratio_val = min(mpm / self.b2_max_mpm, 1.0)
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
                max_area = self.b3_max_area_pixel
            else:
                max_area = self.b3_max_area_normalized
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
