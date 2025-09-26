import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import asyncio
import json
import logging

from sqlalchemy.orm import Session
from app.models.reference import ReferenceModel, ReferenceType
from app.models.comparison import ComparisonResult, ComparisonStatus
from app.models.analysis import AnalysisResult
from app.schemas.scoring import (
    FeedbackItem, DetailedFeedback, ComparisonReport
)
from app.core.websocket import manager

logger = logging.getLogger(__name__)
# Fixed NoneType comparison issues in _generate_feedback

class ScoringService:
    """採点サービス - 手術動作の比較評価を行う"""

    def __init__(self):
        self.weight_defaults = {
            "speed": 0.25,
            "smoothness": 0.25,
            "stability": 0.25,
            "efficiency": 0.25
        }

    async def create_reference_model(
        self,
        db: Session,
        name: str,
        analysis_id: str,
        **kwargs
    ) -> ReferenceModel:
        """基準モデルを作成"""
        try:
            # 解析結果を取得
            analysis = db.query(AnalysisResult).filter(
                AnalysisResult.id == analysis_id
            ).first()

            if not analysis:
                raise ValueError(f"Analysis {analysis_id} not found")

            # スコアがない場合はNoneを使用（モーション軌跡での比較は可能）
            scores = analysis.scores or {}

            # 基準モデルを作成
            reference = ReferenceModel(
                name=name,
                analysis_id=analysis_id,
                avg_speed_score=scores.get("speed_score"),
                avg_smoothness_score=scores.get("smoothness_score"),
                avg_stability_score=scores.get("stability_score"),
                avg_efficiency_score=scores.get("efficiency_score"),
                **kwargs
            )

            db.add(reference)
            db.commit()
            db.refresh(reference)

            logger.info(f"Created reference model: {reference.id}")
            return reference

        except Exception as e:
            logger.error(f"Failed to create reference model: {str(e)}")
            db.rollback()
            raise

    async def start_comparison(
        self,
        db: Session,
        reference_model_id: str,
        learner_analysis_id: str
    ) -> ComparisonResult:
        """比較評価を開始"""
        try:
            # 基準モデルを取得
            reference = db.query(ReferenceModel).filter(
                ReferenceModel.id == reference_model_id
            ).first()

            if not reference:
                raise ValueError(f"Reference model {reference_model_id} not found")

            # 学習者の解析結果を取得
            learner_analysis = db.query(AnalysisResult).filter(
                AnalysisResult.id == learner_analysis_id
            ).first()

            if not learner_analysis:
                raise ValueError(f"Learner analysis {learner_analysis_id} not found")

            # 比較結果を作成
            comparison = ComparisonResult(
                reference_model_id=reference_model_id,
                learner_analysis_id=learner_analysis_id,
                status=ComparisonStatus.PROCESSING,
                progress=0
            )

            db.add(comparison)
            db.commit()
            db.refresh(comparison)

            # 非同期で比較処理を実行
            asyncio.create_task(
                self._perform_comparison(db, comparison.id)
            )

            return comparison

        except Exception as e:
            logger.error(f"Failed to start comparison: {str(e)}")
            db.rollback()
            raise

    async def _perform_comparison(
        self,
        db: Session,
        comparison_id: str
    ):
        """実際の比較処理を実行"""
        try:
            # 比較結果を取得
            comparison = db.query(ComparisonResult).filter(
                ComparisonResult.id == comparison_id
            ).first()

            if not comparison:
                logger.error(f"Comparison {comparison_id} not found")
                return

            # 基準モデルと解析結果を取得
            reference = comparison.reference_model
            reference_analysis = reference.analysis_result
            learner_analysis = comparison.learner_analysis

            # 進捗更新
            await self._update_progress(comparison_id, 10, "データ準備中...")

            # スケルトンデータの比較
            if reference_analysis.skeleton_data and learner_analysis.skeleton_data:
                dtw_distance, alignment = await self._compare_skeleton_data(
                    reference_analysis.skeleton_data,
                    learner_analysis.skeleton_data
                )
                comparison.dtw_distance = float(dtw_distance)
                comparison.temporal_alignment = alignment

            await self._update_progress(comparison_id, 40, "スコア計算中...")

            # スコアの比較
            score_comparison = await self._compare_scores(
                reference_analysis.scores or {},
                learner_analysis.scores or {},
                reference.weights or self.weight_defaults
            )

            comparison.overall_score = score_comparison["overall"]
            comparison.speed_score = score_comparison["speed"]
            comparison.smoothness_score = score_comparison["smoothness"]
            comparison.stability_score = score_comparison["stability"]
            comparison.efficiency_score = score_comparison["efficiency"]

            await self._update_progress(comparison_id, 60, "メトリクス比較中...")

            # 詳細メトリクスの比較
            metrics_comp = await self._compare_detailed_metrics(
                reference_analysis.motion_analysis or {},
                learner_analysis.motion_analysis or {}
            )
            comparison.metrics_comparison = metrics_comp

            await self._update_progress(comparison_id, 80, "フィードバック生成中...")

            # フィードバック生成
            feedback = await self._generate_feedback(
                score_comparison,
                metrics_comp,
                comparison.dtw_distance
            )
            comparison.feedback = feedback

            # 完了
            comparison.status = ComparisonStatus.COMPLETED
            comparison.progress = 100
            comparison.completed_at = datetime.utcnow()

            db.commit()
            await self._update_progress(comparison_id, 100, "比較完了")

            logger.info(f"Comparison {comparison_id} completed successfully")

        except Exception as e:
            logger.error(f"Comparison failed: {str(e)}")
            comparison.status = ComparisonStatus.FAILED
            comparison.error_message = str(e)
            db.commit()

    async def _compare_skeleton_data(
        self,
        reference_data: List[Dict],
        learner_data: List[Dict]
    ) -> Tuple[float, Dict]:
        """スケルトンデータをDTWで比較"""
        try:
            # 手の中心位置を抽出
            ref_trajectory = self._extract_trajectory(reference_data)
            learn_trajectory = self._extract_trajectory(learner_data)

            # DTW計算
            dtw_distance, alignment = self._calculate_dtw(
                ref_trajectory, learn_trajectory
            )

            return dtw_distance, {
                "reference_length": len(ref_trajectory),
                "learner_length": len(learn_trajectory),
                "alignment_path": alignment[:100]  # 最初の100点のみ保存
            }

        except Exception as e:
            logger.error(f"Skeleton comparison failed: {str(e)}")
            return 0.0, {}

    def _extract_trajectory(self, skeleton_data: List[Dict]) -> np.ndarray:
        """スケルトンデータから軌跡を抽出"""
        trajectory = []
        for frame in skeleton_data:
            if frame.get("hands") and len(frame["hands"]) > 0:
                hand = frame["hands"][0]
                if hand and "palm_center" in hand:
                    center = hand["palm_center"]
                    trajectory.append([center["x"], center["y"]])

        return np.array(trajectory) if trajectory else np.array([[0, 0]])

    def _calculate_dtw(
        self,
        seq1: np.ndarray,
        seq2: np.ndarray
    ) -> Tuple[float, List]:
        """Dynamic Time Warpingを計算"""
        n, m = len(seq1), len(seq2)
        dtw_matrix = np.full((n + 1, m + 1), np.inf)
        dtw_matrix[0, 0] = 0

        # DTW行列を計算
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = np.linalg.norm(seq1[i-1] - seq2[j-1])
                dtw_matrix[i, j] = cost + min(
                    dtw_matrix[i-1, j],      # insertion
                    dtw_matrix[i, j-1],      # deletion
                    dtw_matrix[i-1, j-1]    # match
                )

        # バックトラック
        alignment = []
        i, j = n, m
        while i > 0 and j > 0:
            alignment.append([i-1, j-1])
            if i == 0:
                j -= 1
            elif j == 0:
                i -= 1
            else:
                min_idx = np.argmin([
                    dtw_matrix[i-1, j-1],
                    dtw_matrix[i-1, j],
                    dtw_matrix[i, j-1]
                ])
                if min_idx == 0:
                    i, j = i-1, j-1
                elif min_idx == 1:
                    i -= 1
                else:
                    j -= 1

        return dtw_matrix[n, m] / max(n, m), alignment

    async def _compare_scores(
        self,
        reference_scores: Dict,
        learner_scores: Dict,
        weights: Dict
    ) -> Dict[str, float]:
        """スコアを比較"""
        comparison = {}

        # 各スコアの比較（100点満点に正規化）
        for key in ["speed", "smoothness", "stability", "efficiency"]:
            ref_score = reference_scores.get(f"{key}_score", 0) if reference_scores else 0
            learn_score = learner_scores.get(f"{key}_score", 0) if learner_scores else 0

            # None値をゼロに変換
            ref_score = ref_score if ref_score is not None else 0
            learn_score = learn_score if learn_score is not None else 0

            # 相対スコア計算（基準に対する達成率）
            if ref_score > 0:
                comparison[key] = min(100, (learn_score / ref_score) * 100)
            else:
                comparison[key] = learn_score if learn_score is not None else 0

        # 重み付き総合スコア
        comparison["overall"] = sum(
            comparison[key] * weights.get(key, 0.25)
            for key in ["speed", "smoothness", "stability", "efficiency"]
        )

        return comparison

    async def _compare_detailed_metrics(
        self,
        reference_metrics: Dict,
        learner_metrics: Dict
    ) -> Dict:
        """詳細メトリクスを比較"""
        comparison = {}

        # 速度解析の比較
        if "速度解析" in reference_metrics and "速度解析" in learner_metrics:
            comparison["velocity"] = {
                "reference": reference_metrics["速度解析"],
                "learner": learner_metrics["速度解析"],
                "difference": {
                    "avg_velocity": (
                        learner_metrics["速度解析"].get("avg_velocity", 0) -
                        reference_metrics["速度解析"].get("avg_velocity", 0)
                    )
                }
            }

        # 他のメトリクスも同様に比較
        for metric_key in ["軌跡解析", "安定性解析", "効率性解析"]:
            if metric_key in reference_metrics and metric_key in learner_metrics:
                key_map = {
                    "軌跡解析": "trajectory",
                    "安定性解析": "stability",
                    "効率性解析": "efficiency"
                }
                comparison[key_map[metric_key]] = {
                    "reference": reference_metrics[metric_key],
                    "learner": learner_metrics[metric_key],
                    "difference": {}  # 詳細な差分計算は省略
                }

        return comparison

    async def _generate_feedback(
        self,
        score_comparison: Dict,
        metrics_comparison: Dict,
        dtw_distance: float
    ) -> Dict:
        """フィードバックを生成"""
        feedback = {
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "detailed_analysis": {}
        }

        # スコアベースのフィードバック
        for key in ["speed", "smoothness", "stability", "efficiency"]:
            score = score_comparison.get(key, 0)
            # None値を0として扱う
            score = 0 if score is None else float(score)

            if score >= 80:
                feedback["strengths"].append({
                    "category": key,
                    "message": f"{self._get_metric_name(key)}が優秀です（{score:.1f}点）"
                })
            elif score < 60:
                feedback["weaknesses"].append({
                    "category": key,
                    "message": f"{self._get_metric_name(key)}に改善の余地があります（{score:.1f}点）"
                })

        # 具体的な改善提案
        speed_score = score_comparison.get("speed", 0)
        speed_score = 0 if speed_score is None else float(speed_score)
        if speed_score < 60:
            feedback["suggestions"].append({
                "category": "speed",
                "message": "動作速度を基準に近づけるため、より一定のペースで動作してください"
            })

        smoothness_score = score_comparison.get("smoothness", 0)
        smoothness_score = 0 if smoothness_score is None else float(smoothness_score)
        if smoothness_score < 60:
            feedback["suggestions"].append({
                "category": "smoothness",
                "message": "より滑らかな動作を心がけ、急激な方向転換を避けてください"
            })

        # DTW距離に基づくフィードバック
        dtw_distance = 0 if dtw_distance is None else float(dtw_distance)
        if dtw_distance < 0.3:
            feedback["strengths"].append({
                "category": "overall",
                "message": "全体的な動作パターンが基準に近いです"
            })
        elif dtw_distance > 0.7:
            feedback["suggestions"].append({
                "category": "overall",
                "message": "基準動作の軌跡をより意識して練習することを推奨します"
            })

        return feedback

    def _get_metric_name(self, key: str) -> str:
        """メトリクス名を日本語に変換"""
        name_map = {
            "speed": "動作速度",
            "smoothness": "動作の滑らかさ",
            "stability": "安定性",
            "efficiency": "効率性"
        }
        return name_map.get(key, key)

    async def _update_progress(
        self,
        comparison_id: str,
        progress: int,
        message: str
    ):
        """進捗をWebSocketで通知"""
        try:
            await manager.send_update(comparison_id, {
                "type": "comparison_progress",
                "progress": progress,
                "message": message
            })
        except Exception as e:
            logger.warning(f"Failed to send progress update: {str(e)}")

    async def get_comparison_report(
        self,
        db: Session,
        comparison_id: str
    ) -> ComparisonReport:
        """比較レポートを生成"""
        comparison = db.query(ComparisonResult).filter(
            ComparisonResult.id == comparison_id
        ).first()

        if not comparison:
            raise ValueError(f"Comparison {comparison_id} not found")

        # レポート生成
        report = ComparisonReport(
            comparison_id=comparison_id,
            reference_name=comparison.reference_model.name,
            comparison_date=comparison.created_at,
            overall_score=comparison.overall_score or 0,
            detailed_scores={
                "speed": comparison.speed_score or 0,
                "smoothness": comparison.smoothness_score or 0,
                "stability": comparison.stability_score or 0,
                "efficiency": comparison.efficiency_score or 0
            },
            feedback=DetailedFeedback(
                strengths=[
                    FeedbackItem(
                        category="strength",
                        title=item["category"],
                        description=item["message"],
                        importance=0.8
                    )
                    for item in comparison.feedback.get("strengths", [])
                ],
                weaknesses=[
                    FeedbackItem(
                        category="weakness",
                        title=item["category"],
                        description=item["message"],
                        importance=0.9
                    )
                    for item in comparison.feedback.get("weaknesses", [])
                ],
                suggestions=[
                    FeedbackItem(
                        category="suggestion",
                        title=item["category"],
                        description=item["message"],
                        importance=1.0
                    )
                    for item in comparison.feedback.get("suggestions", [])
                ],
                overall_summary=self._generate_summary(comparison),
                improvement_priority=self._get_improvement_priorities(comparison)
            ),
            improvement_plan=self._generate_improvement_plan(comparison)
        )

        return report

    def _generate_summary(self, comparison: ComparisonResult) -> str:
        """総評を生成"""
        overall = comparison.overall_score or 0
        if overall >= 80:
            return "全体的に優秀な手技です。基準動作に近いパフォーマンスを示しています。"
        elif overall >= 60:
            return "良好な手技ですが、いくつかの改善点があります。継続的な練習で向上が期待できます。"
        else:
            return "基本的な技術は身についていますが、複数の領域で改善が必要です。基準動作を参考に練習を重ねてください。"

    def _get_improvement_priorities(self, comparison: ComparisonResult) -> List[str]:
        """改善優先度を決定"""
        scores = {
            "速度": comparison.speed_score or 0,
            "滑らかさ": comparison.smoothness_score or 0,
            "安定性": comparison.stability_score or 0,
            "効率性": comparison.efficiency_score or 0
        }

        # スコアが低い順にソート
        sorted_metrics = sorted(scores.items(), key=lambda x: x[1])
        return [name for name, score in sorted_metrics if score < 70][:3]

    def _generate_improvement_plan(self, comparison: ComparisonResult) -> List[str]:
        """改善計画を生成"""
        plan = []

        if (comparison.speed_score or 0) < 60:
            plan.append("基準動作の速度を動画で確認し、同じペースで練習する")

        if (comparison.smoothness_score or 0) < 60:
            plan.append("手の動きを録画して軌跡を確認し、滑らかさを意識する")

        if (comparison.stability_score or 0) < 60:
            plan.append("手の震えを抑えるため、支点を安定させる練習を行う")

        if (comparison.efficiency_score or 0) < 60:
            plan.append("無駄な動きを減らし、最短経路を意識した動作を心がける")

        return plan