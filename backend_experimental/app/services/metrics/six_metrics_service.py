"""
6指標統合計算サービス
前処理 → Group A/B 計算 → スコア化 → 統合結果
+ タイムライン計算（各時点での累積スコア）
"""

import math
import logging
from typing import List, Dict, Any, Optional

from .types import ExpertBaseline, SixMetricsResult, PreprocessedData
from .preprocessor import preprocess_skeleton_data
from .motion_quality_calculator import MotionQualityCalculator
from .waste_detector import WasteDetector
from .metric_scorer import MetricScorer

logger = logging.getLogger(__name__)


class SixMetricsService:
    """6指標統合計算サービス"""

    # Group A 重み
    WEIGHT_A1 = 0.40  # 動作経済性（最も判別力が高い）
    WEIGHT_A2 = 0.35  # 動作滑らかさ
    WEIGHT_A3 = 0.25  # 両手協調性

    # Group B 重み
    WEIGHT_B1 = 0.40  # ロスタイム（時間コスト直結）
    WEIGHT_B2 = 0.30  # 動作回数
    WEIGHT_B3 = 0.30  # 作業空間偏差

    # 総合
    WEIGHT_GROUP_A = 0.50
    WEIGHT_GROUP_B = 0.50

    def __init__(self, fps: float = 30.0):
        self.fps = fps
        self.motion_quality = MotionQualityCalculator(fps)
        self.waste_detector = WasteDetector(fps)
        self.scorer = MetricScorer()

    def calculate(
        self,
        skeleton_data: List[Dict],
        expert_baseline: Optional[ExpertBaseline] = None,
    ) -> SixMetricsResult:
        """
        6指標を一括計算

        Args:
            skeleton_data: 骨格データ（V1/V2形式）
            expert_baseline: エキスパート基準値（なければ絶対評価）
        """
        # 1. 前処理
        data = preprocess_skeleton_data(skeleton_data, self.fps)

        logger.info(
            f"[SIX_METRICS] Preprocessed: {data.total_frames} frames, "
            f"duration={data.total_duration_seconds}s, "
            f"pixel_coords={data.is_pixel_coords}"
        )

        # 2. Group A 計算
        a1_raw = self.motion_quality.economy_of_motion(data)
        a2_raw = self.motion_quality.smoothness_sparc(data)
        a3_raw = self.motion_quality.bimanual_coordination(data)

        # 3. Group B 計算
        b1_raw = self.waste_detector.lost_time(data)
        b2_raw = self.waste_detector.movement_count(data)
        b3_raw = self.waste_detector.working_volume(data)

        # 4. スコア化
        a1 = self.scorer.score_economy_of_motion(a1_raw, expert_baseline)
        a2 = self.scorer.score_smoothness(a2_raw, expert_baseline)
        a3 = self.scorer.score_bimanual_coordination(a3_raw, expert_baseline)
        b1 = self.scorer.score_lost_time(b1_raw, expert_baseline)
        b2 = self.scorer.score_movement_count(b2_raw, expert_baseline)
        b3 = self.scorer.score_working_volume(b3_raw, expert_baseline)

        # 5. 複合スコア（A3がN/Aの場合は重み再配分）
        if a3.score < 0:
            # A3がN/A: A1とA2で重み再配分
            a1_w = self.WEIGHT_A1 + self.WEIGHT_A3 * (self.WEIGHT_A1 / (self.WEIGHT_A1 + self.WEIGHT_A2))
            a2_w = self.WEIGHT_A2 + self.WEIGHT_A3 * (self.WEIGHT_A2 / (self.WEIGHT_A1 + self.WEIGHT_A2))
            mq_score = a1.score * a1_w + a2.score * a2_w
        else:
            mq_score = (a1.score * self.WEIGHT_A1 +
                        a2.score * self.WEIGHT_A2 +
                        a3.score * self.WEIGHT_A3)

        wd_score = (b1.score * self.WEIGHT_B1 +
                    b2.score * self.WEIGHT_B2 +
                    b3.score * self.WEIGHT_B3)

        overall = (mq_score * self.WEIGHT_GROUP_A +
                   wd_score * self.WEIGHT_GROUP_B)

        mode = "relative" if expert_baseline else "absolute"

        logger.info(
            f"[SIX_METRICS] Scores: "
            f"A1={a1.score} A2={a2.score} A3={a3.score} "
            f"B1={b1.score} B2={b2.score} B3={b3.score} "
            f"MQ={mq_score:.1f} WD={wd_score:.1f} Overall={overall:.1f} "
            f"mode={mode}"
        )

        return SixMetricsResult(
            metrics=[a1, a2, a3, b1, b2, b3],
            motion_quality_score=round(mq_score, 1),
            waste_detection_score=round(wd_score, 1),
            overall_score=round(overall, 1),
            evaluation_mode=mode,
            expert_baseline_used=expert_baseline is not None,
        )

    def calculate_timeline(
        self,
        skeleton_data: List[Dict],
        interval_sec: float = 0.5,
        expert_baseline: Optional[ExpertBaseline] = None,
    ) -> List[Dict[str, Any]]:
        """
        各時点での累積6指標スコアを計算

        skeleton_dataを先頭からinterval_secごとにスライスし、
        その時点までのデータで6指標を計算する。
        最終エントリの値は calculate() の結果と完全一致する。

        Args:
            skeleton_data: 骨格データ
            interval_sec: サンプリング間隔（秒）
            expert_baseline: エキスパート基準値

        Returns:
            [{"timestamp": 0.5, "overall": 45, "mq": 40, "wd": 50,
              "a1": 30, "a2": 55, "a3": 0, "b1": 100, "b2": 100, "b3": 60}, ...]
        """
        if not skeleton_data or len(skeleton_data) < 2:
            return []

        # タイムスタンプを取得
        first_ts = skeleton_data[0].get("timestamp", 0) or 0
        last_ts = skeleton_data[-1].get("timestamp", 0) or 0
        if last_ts <= first_ts:
            # タイムスタンプがない場合はフレーム数からfps推定
            last_ts = len(skeleton_data) / self.fps

        # サンプリング時点を生成
        sample_times = []
        t = interval_sec
        while t < last_ts:
            sample_times.append(t)
            t += interval_sec
        sample_times.append(last_ts)  # 最終時点を必ず含める

        timeline = []
        for target_time in sample_times:
            # target_timeまでのデータをスライス
            slice_data = [
                f for f in skeleton_data
                if (f.get("timestamp", 0) or 0) <= target_time
            ]

            if len(slice_data) < 3:
                # データ不足 → ゼロ
                timeline.append({
                    "timestamp": round(target_time, 2),
                    "overall": 0, "mq": 0, "wd": 0,
                    "a1": 0, "a2": 0, "a3": 0,
                    "b1": 0, "b2": 0, "b3": 0,
                })
                continue

            # この時点までの6指標を計算
            result = self.calculate(slice_data, expert_baseline)

            timeline.append({
                "timestamp": round(target_time, 2),
                "overall": result.overall_score,
                "mq": result.motion_quality_score,
                "wd": result.waste_detection_score,
                "a1": result.metrics[0].score,  # economy_of_motion
                "a2": result.metrics[1].score,  # smoothness
                "a3": result.metrics[2].score,  # bimanual_coordination
                "b1": result.metrics[3].score,  # lost_time
                "b2": result.metrics[4].score,  # movement_count
                "b3": result.metrics[5].score,  # working_volume
            })

        logger.info(
            f"[SIX_METRICS] Timeline: {len(timeline)} samples, "
            f"interval={interval_sec}s, duration={last_ts:.1f}s"
        )

        return timeline
