"""動画解析サービス - 改善版"""

import asyncio
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging
from enum import Enum

from app.core.websocket import manager
from app.models import SessionLocal
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.models.video import VideoType
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.video_analyzer import VideoAnalyzer
from app.ai_engine.processors.frame_extractor import FrameExtractor

logger = logging.getLogger(__name__)


class AnalysisStep(str, Enum):
    """解析ステップの定義"""
    INITIALIZING = "initializing"
    VIDEO_INFO = "video_info"
    FRAME_EXTRACTION = "frame_extraction"
    SKELETON_DETECTION = "skeleton_detection"
    INSTRUMENT_DETECTION = "instrument_detection"
    MOTION_ANALYSIS = "motion_analysis"
    SCORE_CALCULATION = "score_calculation"
    DATA_SAVING = "data_saving"
    COMPLETED = "completed"


class AnalysisService:
    """動画解析処理サービス - 詳細進捗版"""

    # ステップごとの進捗範囲定義
    PROGRESS_RANGES = {
        AnalysisStep.INITIALIZING: (0, 5),
        AnalysisStep.VIDEO_INFO: (5, 10),
        AnalysisStep.FRAME_EXTRACTION: (10, 30),
        AnalysisStep.SKELETON_DETECTION: (30, 50),
        AnalysisStep.INSTRUMENT_DETECTION: (30, 50),
        AnalysisStep.MOTION_ANALYSIS: (50, 70),
        AnalysisStep.SCORE_CALCULATION: (70, 85),
        AnalysisStep.DATA_SAVING: (85, 95),
        AnalysisStep.COMPLETED: (95, 100),
    }

    def __init__(self):
        self.skeleton_detector = None
        self.current_progress = 0
        self.analysis_id = None
        self.current_step = AnalysisStep.INITIALIZING

    async def process_video(
        self,
        video_id: str,
        video_path: str,
        video_type: str,
        analysis_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        動画を解析してモーションデータを抽出（詳細進捗付き）

        Args:
            video_id: 動画ID
            video_path: 動画ファイルパス
            video_type: 動画タイプ (internal/external)
            analysis_id: 解析ID
            progress_callback: 進捗通知用コールバック

        Returns:
            解析結果
        """
        self.analysis_id = analysis_id

        try:
            # ステップ1: 初期化
            await self._update_progress_detailed(
                AnalysisStep.INITIALIZING,
                0,
                "解析を初期化しています..."
            )

            # DBセッション作成
            db = SessionLocal()
            analysis_result = db.query(AnalysisResult).filter(
                AnalysisResult.id == analysis_id
            ).first()

            if not analysis_result:
                raise ValueError(f"Analysis not found: {analysis_id}")

            # ステップ2: 動画情報取得
            await self._update_progress_detailed(
                AnalysisStep.VIDEO_INFO,
                0,
                "動画情報を取得中..."
            )

            video_info = self._get_video_info(video_path)
            await self._update_progress_detailed(
                AnalysisStep.VIDEO_INFO,
                100,
                f"動画情報取得完了: {video_info['width']}x{video_info['height']}, {video_info['fps']:.1f}fps"
            )

            # ステップ3: フレーム抽出
            await self._update_progress_detailed(
                AnalysisStep.FRAME_EXTRACTION,
                0,
                "フレームを抽出中..."
            )

            frames = await self._extract_frames_with_progress(video_path, fps=5)

            # ステップ4: AI検出処理（動画タイプに応じて分岐）
            skeleton_data = []
            instrument_data = []

            if video_type == VideoType.EXTERNAL:
                # 外部カメラ: 骨格検出
                await self._update_progress_detailed(
                    AnalysisStep.SKELETON_DETECTION,
                    0,
                    "手の骨格を検出中..."
                )
                skeleton_data = await self._detect_skeleton_with_progress(frames)

            elif video_type == VideoType.INTERNAL:
                # 内部カメラ: 器具検出
                await self._update_progress_detailed(
                    AnalysisStep.INSTRUMENT_DETECTION,
                    0,
                    "手術器具を検出中..."
                )
                instrument_data = await self._detect_instruments_with_progress(frames)

            # ステップ5: モーション解析
            await self._update_progress_detailed(
                AnalysisStep.MOTION_ANALYSIS,
                0,
                "モーションを解析中..."
            )

            motion_analysis = await self._analyze_motion_with_progress(
                skeleton_data,
                instrument_data
            )

            # ステップ6: スコア計算
            await self._update_progress_detailed(
                AnalysisStep.SCORE_CALCULATION,
                0,
                "スコアを計算中..."
            )

            scores = await self._calculate_scores_with_progress(motion_analysis)

            # ステップ7: データ保存
            await self._update_progress_detailed(
                AnalysisStep.DATA_SAVING,
                0,
                "解析結果を保存中..."
            )

            # 結果をDBに保存
            analysis_result.skeleton_data = skeleton_data
            analysis_result.instrument_data = instrument_data
            analysis_result.motion_analysis = motion_analysis
            analysis_result.scores = scores
            analysis_result.total_frames = len(frames)
            analysis_result.status = AnalysisStatus.COMPLETED
            analysis_result.completed_at = datetime.now()

            db.commit()

            # ステップ8: 完了
            await self._update_progress_detailed(
                AnalysisStep.COMPLETED,
                100,
                "解析が完了しました！"
            )

            db.close()

            return {
                "video_id": video_id,
                "analysis_id": analysis_id,
                "video_info": video_info,
                "skeleton_data": skeleton_data,
                "instrument_data": instrument_data,
                "motion_analysis": motion_analysis,
                "scores": scores,
                "total_frames": len(frames),
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")

            # エラー時の処理
            try:
                db = SessionLocal()
                analysis_result = db.query(AnalysisResult).filter(
                    AnalysisResult.id == analysis_id
                ).first()
                if analysis_result:
                    analysis_result.status = AnalysisStatus.FAILED
                    analysis_result.error_message = str(e)
                    db.commit()
                db.close()
            except:
                pass

            await self._update_progress_detailed(
                self.current_step,
                0,
                f"エラーが発生しました: {str(e)}",
                status="failed"
            )

            raise

    async def _update_progress_detailed(
        self,
        step: AnalysisStep,
        step_progress: float,  # 0-100 (ステップ内の進捗)
        message: str,
        status: str = "processing"
    ):
        """詳細な進捗更新"""
        self.current_step = step

        # ステップの進捗範囲を取得
        min_progress, max_progress = self.PROGRESS_RANGES.get(
            step, (0, 100)
        )

        # 全体進捗を計算
        progress_range = max_progress - min_progress
        self.current_progress = min_progress + (progress_range * step_progress / 100)

        # WebSocket経由で進捗を送信
        await manager.send_progress(self.analysis_id, {
            "type": "progress",
            "progress": int(self.current_progress),
            "step": step.value,
            "step_progress": step_progress,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"[{self.analysis_id}] {step.value}: {self.current_progress:.1f}% - {message}")

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """動画情報を取得"""
        with FrameExtractor(video_path) as extractor:
            info = extractor.get_info()
            return {
                "width": info.width,
                "height": info.height,
                "fps": info.fps,
                "total_frames": info.total_frames,
                "duration": info.duration
            }

    async def _extract_frames_with_progress(
        self,
        video_path: str,
        fps: int = 5
    ) -> List[np.ndarray]:
        """進捗通知付きフレーム抽出"""
        frames = []

        with FrameExtractor(video_path, target_fps=fps) as extractor:
            video_info = extractor.get_info()
            expected_frames = int(video_info.duration * fps)

            for i, (frame_num, frame) in enumerate(extractor.extract_frames_generator()):
                frames.append(frame)

                # 10フレームごとに進捗更新
                if i % 10 == 0:
                    progress = min(100, (i / expected_frames) * 100)
                    await self._update_progress_detailed(
                        AnalysisStep.FRAME_EXTRACTION,
                        progress,
                        f"フレーム抽出中... ({i}/{expected_frames})"
                    )

        await self._update_progress_detailed(
            AnalysisStep.FRAME_EXTRACTION,
            100,
            f"フレーム抽出完了: {len(frames)}フレーム"
        )

        return frames

    async def _detect_skeleton_with_progress(
        self,
        frames: List[np.ndarray]
    ) -> List[Dict]:
        """進捗通知付き骨格検出"""
        if not self.skeleton_detector:
            self.skeleton_detector = HandSkeletonDetector()

        skeleton_data = []
        total_frames = len(frames)

        for i, frame in enumerate(frames):
            # 骨格検出
            hands = self.skeleton_detector.detect(frame)
            skeleton_data.append({
                "frame": i,
                "hands": hands
            })

            # 5フレームごとに進捗更新
            if i % 5 == 0:
                progress = (i / total_frames) * 100
                await self._update_progress_detailed(
                    AnalysisStep.SKELETON_DETECTION,
                    progress,
                    f"骨格検出中... ({i}/{total_frames})"
                )

        await self._update_progress_detailed(
            AnalysisStep.SKELETON_DETECTION,
            100,
            f"骨格検出完了: {len([d for d in skeleton_data if d['hands']])}フレームで検出"
        )

        return skeleton_data

    async def _detect_instruments_with_progress(
        self,
        frames: List[np.ndarray]
    ) -> List[Dict]:
        """進捗通知付き器具検出（モック）"""
        instrument_data = []
        total_frames = len(frames)

        for i, frame in enumerate(frames):
            # モック器具検出
            instrument_data.append({
                "frame": i,
                "detections": self._mock_instrument_detection_single(i)
            })

            # 5フレームごとに進捗更新
            if i % 5 == 0:
                progress = (i / total_frames) * 100
                await self._update_progress_detailed(
                    AnalysisStep.INSTRUMENT_DETECTION,
                    progress,
                    f"器具検出中... ({i}/{total_frames})"
                )

        await self._update_progress_detailed(
            AnalysisStep.INSTRUMENT_DETECTION,
            100,
            f"器具検出完了: {len([d for d in instrument_data if d['detections']])}フレームで検出"
        )

        return instrument_data

    def _mock_instrument_detection_single(self, frame_num: int) -> List[Dict]:
        """単一フレーム用モック器具検出"""
        import random

        if random.random() > 0.7:  # 70%の確率で検出
            return []

        return [{
            "class": random.choice(["forceps", "scissors", "needle_holder"]),
            "confidence": random.uniform(0.7, 0.99),
            "bbox": {
                "x": random.uniform(100, 500),
                "y": random.uniform(100, 300),
                "width": random.uniform(50, 150),
                "height": random.uniform(30, 100)
            }
        }]

    async def _analyze_motion_with_progress(
        self,
        skeleton_data: List[Dict],
        instrument_data: List[Dict]
    ) -> Dict[str, Any]:
        """進捗通知付きモーション解析"""

        # 複数の解析タスクを実行
        tasks = [
            ("速度解析", self._analyze_velocity),
            ("軌跡解析", self._analyze_trajectory),
            ("安定性解析", self._analyze_stability),
            ("効率性解析", self._analyze_efficiency)
        ]

        results = {}

        for i, (task_name, task_func) in enumerate(tasks):
            progress = (i / len(tasks)) * 100
            await self._update_progress_detailed(
                AnalysisStep.MOTION_ANALYSIS,
                progress,
                f"{task_name}を実行中..."
            )

            # 少し待機（実際の処理時間をシミュレート）
            await asyncio.sleep(0.5)

            results[task_name] = task_func(skeleton_data, instrument_data)

        await self._update_progress_detailed(
            AnalysisStep.MOTION_ANALYSIS,
            100,
            "モーション解析完了"
        )

        return results

    def _analyze_velocity(self, skeleton_data, instrument_data):
        """速度解析"""
        return {
            "avg_velocity": np.random.uniform(5, 15),
            "max_velocity": np.random.uniform(20, 40),
            "velocity_variance": np.random.uniform(1, 5)
        }

    def _analyze_trajectory(self, skeleton_data, instrument_data):
        """軌跡解析"""
        return {
            "total_distance": np.random.uniform(500, 2000),
            "smoothness": np.random.uniform(0.6, 0.95),
            "path_efficiency": np.random.uniform(0.7, 0.95)
        }

    def _analyze_stability(self, skeleton_data, instrument_data):
        """安定性解析"""
        return {
            "tremor_level": np.random.uniform(0.1, 0.5),
            "consistency": np.random.uniform(0.7, 0.95),
            "precision": np.random.uniform(0.8, 0.98)
        }

    def _analyze_efficiency(self, skeleton_data, instrument_data):
        """効率性解析"""
        return {
            "time_efficiency": np.random.uniform(0.7, 0.95),
            "motion_economy": np.random.uniform(0.6, 0.9),
            "redundancy": np.random.uniform(0.05, 0.3)
        }

    async def _calculate_scores_with_progress(
        self,
        motion_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """進捗通知付きスコア計算"""

        score_components = [
            ("速度スコア", 25),
            ("精度スコア", 25),
            ("安定性スコア", 25),
            ("効率性スコア", 25)
        ]

        scores = {}

        for i, (component_name, weight) in enumerate(score_components):
            progress = (i / len(score_components)) * 100
            await self._update_progress_detailed(
                AnalysisStep.SCORE_CALCULATION,
                progress,
                f"{component_name}を計算中..."
            )

            # スコア計算（モック）
            scores[component_name] = np.random.uniform(70, 95)
            await asyncio.sleep(0.2)

        # 総合スコア計算
        scores["total_score"] = sum(scores.values()) / len(scores)

        await self._update_progress_detailed(
            AnalysisStep.SCORE_CALCULATION,
            100,
            f"スコア計算完了: 総合スコア {scores['total_score']:.1f}点"
        )

        return scores