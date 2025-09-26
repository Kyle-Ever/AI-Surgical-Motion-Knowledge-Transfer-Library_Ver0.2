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
from app.ai_engine.processors.sam_tracker import SAMTracker
from app.services.metrics_calculator import MetricsCalculator
from app.core.config import settings

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
        self.video_type = None  # video_typeを保存するための変数を追加

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
        self.video_type = video_type  # video_typeをインスタンス変数として保存

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

            # Handle legacy EXTERNAL type as EXTERNAL_NO_INSTRUMENTS
            if video_type == VideoType.EXTERNAL or video_type == VideoType.EXTERNAL_NO_INSTRUMENTS or video_type == "external_no_instruments":
                # 外部カメラ（器具なし）: 骨格検出のみ
                await self._update_progress_detailed(
                    AnalysisStep.SKELETON_DETECTION,
                    0,
                    "手の骨格を検出中..."
                )
                skeleton_data = await self._detect_skeleton_with_progress(frames)

            elif video_type == VideoType.EXTERNAL_WITH_INSTRUMENTS or video_type == "external_with_instruments":
                # 外部カメラ（器具あり）: 骨格検出と器具検出の両方
                await self._update_progress_detailed(
                    AnalysisStep.SKELETON_DETECTION,
                    0,
                    "手の骨格を検出中..."
                )
                skeleton_data = await self._detect_skeleton_with_progress(frames)

                await self._update_progress_detailed(
                    AnalysisStep.INSTRUMENT_DETECTION,
                    0,
                    "手術器具を検出中..."
                )
                instrument_data = await self._detect_instruments_with_progress(frames, video_id)

            elif video_type == VideoType.INTERNAL:
                # 内視鏡: 器具検出（手の骨格も検出）
                await self._update_progress_detailed(
                    AnalysisStep.SKELETON_DETECTION,
                    0,
                    "手の骨格を検出中..."
                )
                skeleton_data = await self._detect_skeleton_with_progress(frames)

                await self._update_progress_detailed(
                    AnalysisStep.INSTRUMENT_DETECTION,
                    0,
                    "手術器具を検出中..."
                )
                instrument_data = await self._detect_instruments_with_progress(frames, video_id)

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

            # ステップ5.5: メトリクス計算
            await self._update_progress_detailed(
                AnalysisStep.MOTION_ANALYSIS,
                50,
                "動作メトリクスを計算中..."
            )

            # メトリクス計算
            metrics_calculator = MetricsCalculator(fps=video_info.get("fps", 30))
            calculated_metrics = metrics_calculator.calculate_all_metrics(skeleton_data)

            # motion_analysisにメトリクスを追加
            motion_analysis["metrics"] = calculated_metrics

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
            analysis_result.progress = 100

            # 統計情報を保存
            velocity_data = motion_analysis.get("速度解析", {})
            analysis_result.avg_velocity = velocity_data.get("avg_velocity", 0)
            analysis_result.max_velocity = velocity_data.get("max_velocity", 0)

            trajectory_data = motion_analysis.get("軌跡解析", {})
            analysis_result.total_distance = trajectory_data.get("total_distance", 0)

            analysis_result.status = AnalysisStatus.COMPLETED
            analysis_result.completed_at = datetime.now()
            analysis_result.current_step = "完了"

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
            # 外部動画（手術用）の場合は手袋検出モードを有効にする
            # すべての外部動画タイプで有効化
            enable_glove = (
                self.video_type == VideoType.EXTERNAL or
                self.video_type == VideoType.EXTERNAL_NO_INSTRUMENTS or
                self.video_type == VideoType.EXTERNAL_WITH_INSTRUMENTS or
                self.video_type == "external" or
                self.video_type == "external_no_instruments" or
                self.video_type == "external_with_instruments"
            )

            # デバッグログを追加
            logger.info(f"Video type: {self.video_type}, Enable glove detection: {enable_glove}")

            # 高性能な手袋検出器を使用するかどうかを設定で制御
            use_advanced_glove = enable_glove and getattr(settings, 'USE_ADVANCED_GLOVE_DETECTION', False)

            if use_advanced_glove:
                # 高性能な手袋検出器を使用
                from app.ai_engine.processors.glove_hand_detector import GloveHandDetector
                logger.info("Using advanced GloveHandDetector for blue glove detection")
                self.skeleton_detector = GloveHandDetector(
                    use_color_enhancement=True,
                    min_hand_confidence=0.2
                )
            else:
                # 標準の検出器（改善版）を使用
                # 最適化された閾値: 0.1で検出率が66.7%に向上
                glove_confidence = 0.1 if enable_glove else 0.5
                logger.info(f"Using HandSkeletonDetector with glove_detection={enable_glove}, "
                           f"min_detection_confidence={glove_confidence}")
                self.skeleton_detector = HandSkeletonDetector(
                    enable_glove_detection=enable_glove,
                    min_detection_confidence=glove_confidence,
                    min_tracking_confidence=glove_confidence,
                    static_image_mode=False,  # トラッキングモードを使用
                    max_num_hands=2  # 両手検出を有効化
                )

        skeleton_data = []
        total_frames = len(frames)

        for i, frame in enumerate(frames):
            # 骨格検出
            detection_result = self.skeleton_detector.detect_from_frame(frame)
            skeleton_data.append({
                "frame": i,
                "hands": detection_result.get("hands", [])
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
        frames: List[np.ndarray],
        video_id: str = None
    ) -> List[Dict]:
        """進捗通知付き器具検出（SAMまたはモック）"""

        # Check if SAM instruments are available
        sam_instruments = await self._load_sam_instruments(video_id) if video_id else None

        if sam_instruments:
            # Use SAM tracking for instruments
            return await self._detect_instruments_with_sam(frames, sam_instruments)
        else:
            # Use mock detection
            return await self._detect_instruments_mock(frames)

    async def _load_sam_instruments(self, video_id: str) -> Optional[List[Dict]]:
        """Load SAM-selected instruments if available"""
        try:
            instruments_file = Path(settings.UPLOAD_DIR) / f"{video_id}_instruments.json"
            if instruments_file.exists():
                with instruments_file.open("r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load SAM instruments: {e}")
        return None

    async def _detect_instruments_with_sam(
        self,
        frames: List[np.ndarray],
        sam_instruments: List[Dict]
    ) -> List[Dict]:
        """SAMを使用した器具トラッキング"""
        instrument_data = []
        total_frames = len(frames)

        # Initialize SAM tracker
        tracker = SAMTracker(use_mock=True)  # Use mock mode for now

        # Track each instrument through the video
        for inst in sam_instruments:
            initial_mask = inst.get("mask", "")
            initial_bbox = inst.get("bbox", [0, 0, 100, 100])

            # Track through frames
            tracking_results = await tracker.track_in_video(
                frames,
                initial_mask=initial_mask,
                initial_bbox=initial_bbox
            )

            # Merge tracking results
            for i, result in enumerate(tracking_results):
                if i >= len(instrument_data):
                    instrument_data.append({
                        "frame": i,
                        "detections": []
                    })

                if result:
                    instrument_data[i]["detections"].append({
                        "class": inst["name"],
                        "confidence": result.get("score", 0.9),
                        "bbox": {
                            "x": result["bbox"][0],
                            "y": result["bbox"][1],
                            "width": result["bbox"][2] - result["bbox"][0],
                            "height": result["bbox"][3] - result["bbox"][1]
                        }
                    })

                # Update progress
                if i % 5 == 0:
                    progress = (i / total_frames) * 100
                    await self._update_progress_detailed(
                        AnalysisStep.INSTRUMENT_DETECTION,
                        progress,
                        f"SAM器具トラッキング中... ({i}/{total_frames})"
                    )

        await self._update_progress_detailed(
            AnalysisStep.INSTRUMENT_DETECTION,
            100,
            f"SAM器具トラッキング完了: {len(sam_instruments)}個の器具を追跡"
        )

        return instrument_data

    async def _detect_instruments_mock(
        self,
        frames: List[np.ndarray]
    ) -> List[Dict]:
        """モック器具検出（従来の処理）"""
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
        """速度解析 - 実際の手の動きから速度を計算"""
        velocities = []

        # 連続するフレーム間の手の移動速度を計算
        for i in range(1, len(skeleton_data)):
            prev_frame = skeleton_data[i-1]
            curr_frame = skeleton_data[i]

            if prev_frame["hands"] and curr_frame["hands"]:
                # 両フレームに手が検出されている場合
                for prev_hand, curr_hand in zip(prev_frame["hands"], curr_frame["hands"]):
                    if prev_hand and curr_hand:
                        # 手のひら中心の移動距離を計算
                        prev_center = prev_hand.get("palm_center", {})
                        curr_center = curr_hand.get("palm_center", {})

                        if prev_center and curr_center:
                            dx = curr_center.get("x", 0) - prev_center.get("x", 0)
                            dy = curr_center.get("y", 0) - prev_center.get("y", 0)
                            distance = np.sqrt(dx**2 + dy**2)

                            # フレーム間隔を考慮した速度（ピクセル/フレーム）
                            velocities.append(distance)

        if velocities:
            return {
                "avg_velocity": float(np.mean(velocities)),
                "max_velocity": float(np.max(velocities)),
                "velocity_variance": float(np.var(velocities))
            }
        else:
            # 手が検出されなかった場合のデフォルト値
            return {
                "avg_velocity": 0.0,
                "max_velocity": 0.0,
                "velocity_variance": 0.0
            }

    def _analyze_trajectory(self, skeleton_data, instrument_data):
        """軌跡解析 - 実際の手の動きの軌跡を解析"""
        total_distance = 0.0
        path_points = []

        # 手の軌跡を収集
        for frame_data in skeleton_data:
            if frame_data["hands"]:
                for hand in frame_data["hands"]:
                    if hand and "palm_center" in hand:
                        center = hand["palm_center"]
                        path_points.append([center.get("x", 0), center.get("y", 0)])

        # 総移動距離を計算
        for i in range(1, len(path_points)):
            dx = path_points[i][0] - path_points[i-1][0]
            dy = path_points[i][1] - path_points[i-1][1]
            total_distance += np.sqrt(dx**2 + dy**2)

        # 滑らかさの計算（加速度の変化の少なさ）
        smoothness = 1.0
        if len(path_points) > 2:
            accelerations = []
            for i in range(2, len(path_points)):
                v1_x = path_points[i-1][0] - path_points[i-2][0]
                v1_y = path_points[i-1][1] - path_points[i-2][1]
                v2_x = path_points[i][0] - path_points[i-1][0]
                v2_y = path_points[i][1] - path_points[i-1][1]

                acc_x = v2_x - v1_x
                acc_y = v2_y - v1_y
                acc_magnitude = np.sqrt(acc_x**2 + acc_y**2)
                accelerations.append(acc_magnitude)

            if accelerations:
                # 加速度の変動が小さいほど滑らか（0-1の値に正規化）
                smoothness = max(0.0, 1.0 - np.std(accelerations) / (np.mean(accelerations) + 1e-6))

        # パス効率（始点と終点の直線距離に対する実際の移動距離の比）
        path_efficiency = 1.0
        if len(path_points) > 1 and total_distance > 0:
            start = path_points[0]
            end = path_points[-1]
            direct_distance = np.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
            path_efficiency = min(1.0, direct_distance / (total_distance + 1e-6))

        return {
            "total_distance": float(total_distance),
            "smoothness": float(smoothness),
            "path_efficiency": float(path_efficiency)
        }

    def _analyze_stability(self, skeleton_data, instrument_data):
        """安定性解析 - 手の震えや動きの一貫性を評価"""
        positions = []
        finger_angles_series = []

        # 各フレームの手の位置と指の角度を収集
        for frame_data in skeleton_data:
            if frame_data["hands"]:
                for hand in frame_data["hands"]:
                    if hand:
                        # 手の位置
                        if "palm_center" in hand:
                            center = hand["palm_center"]
                            positions.append([center.get("x", 0), center.get("y", 0)])

                        # 指の角度
                        if "finger_angles" in hand:
                            angles = list(hand["finger_angles"].values())
                            finger_angles_series.append(angles)

        # 震えレベルの計算（位置の高周波変動）
        tremor_level = 0.0
        if len(positions) > 10:
            # 移動平均との差分を計算
            positions_array = np.array(positions)
            window_size = 5
            moving_avg = np.convolve(positions_array[:, 0], np.ones(window_size)/window_size, mode='valid')

            if len(moving_avg) > 0:
                high_freq_component = positions_array[window_size-1:, 0] - moving_avg
                tremor_level = float(np.std(high_freq_component))
                # 正規化（0-1の範囲に）
                tremor_level = min(1.0, tremor_level / 50.0)

        # 一貫性の計算（指の角度の変動係数）
        consistency = 1.0
        if finger_angles_series:
            angles_array = np.array(finger_angles_series)
            if angles_array.shape[0] > 1:
                # 各指の角度の変動係数を計算
                cvs = []
                for finger_idx in range(angles_array.shape[1]):
                    finger_angles = angles_array[:, finger_idx]
                    mean_angle = np.mean(finger_angles)
                    if mean_angle > 0:
                        cv = np.std(finger_angles) / mean_angle
                        cvs.append(cv)

                if cvs:
                    # 変動係数が小さいほど一貫性が高い
                    consistency = max(0.0, 1.0 - np.mean(cvs))

        # 精度の計算（手の開き具合の安定性）
        precision = 0.8
        hand_openness_values = []
        for frame_data in skeleton_data:
            if frame_data["hands"]:
                for hand in frame_data["hands"]:
                    if hand and "hand_openness" in hand:
                        hand_openness_values.append(hand["hand_openness"])

        if hand_openness_values:
            # 手の開き具合の変動が小さいほど精度が高い
            openness_std = np.std(hand_openness_values)
            precision = max(0.0, 1.0 - openness_std / 100.0)

        return {
            "tremor_level": float(tremor_level),
            "consistency": float(consistency),
            "precision": float(precision)
        }

    def _analyze_efficiency(self, skeleton_data, instrument_data):
        """効率性解析 - 動作の効率性を評価"""
        # フレーム数から時間効率を推定
        total_frames = len(skeleton_data)
        frames_with_hands = sum(1 for f in skeleton_data if f["hands"])

        # 時間効率（手が検出されているフレームの割合）
        time_efficiency = frames_with_hands / max(1, total_frames)

        # 動作の経済性（必要最小限の動きか）
        motion_economy = 0.8
        total_movement = 0.0
        useful_movement = 0.0

        for i in range(1, len(skeleton_data)):
            prev = skeleton_data[i-1]
            curr = skeleton_data[i]

            if prev["hands"] and curr["hands"]:
                for p_hand, c_hand in zip(prev["hands"], curr["hands"]):
                    if p_hand and c_hand and "palm_center" in p_hand and "palm_center" in c_hand:
                        # 移動量を計算
                        dx = c_hand["palm_center"]["x"] - p_hand["palm_center"]["x"]
                        dy = c_hand["palm_center"]["y"] - p_hand["palm_center"]["y"]
                        movement = np.sqrt(dx**2 + dy**2)
                        total_movement += movement

                        # 有用な動き（一定速度以上）
                        if movement > 2.0:  # 閾値
                            useful_movement += movement

        if total_movement > 0:
            motion_economy = useful_movement / total_movement

        # 冗長性（無駄な反復動作の割合）
        redundancy = 0.1
        if len(skeleton_data) > 20:
            # 簡易的な反復検出（位置の周期性）
            positions = []
            for frame in skeleton_data:
                if frame["hands"] and frame["hands"][0] and "palm_center" in frame["hands"][0]:
                    center = frame["hands"][0]["palm_center"]
                    positions.append([center["x"], center["y"]])

            if len(positions) > 10:
                # 位置の自己相関を計算して周期性を検出
                positions_array = np.array(positions)
                # 簡易的に標準偏差で冗長性を推定
                position_std = np.std(positions_array, axis=0)
                avg_std = np.mean(position_std)
                # 動きが少ないほど冗長性が高い
                redundancy = max(0.0, min(1.0, 1.0 - avg_std / 100.0))

        return {
            "time_efficiency": float(time_efficiency),
            "motion_economy": float(motion_economy),
            "redundancy": float(redundancy)
        }

    async def _calculate_scores_with_progress(
        self,
        motion_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """進捗通知付きスコア計算 - 実際の解析結果からスコアを算出"""

        scores = {}

        # 速度スコアの計算
        await self._update_progress_detailed(
            AnalysisStep.SCORE_CALCULATION,
            0,
            "速度スコアを計算中..."
        )

        velocity_data = motion_analysis.get("速度解析", {})
        avg_velocity = velocity_data.get("avg_velocity", 0)
        velocity_variance = velocity_data.get("velocity_variance", 0)

        # 速度スコア: 適度な速度で変動が少ないほど高スコア
        speed_score = 0.0
        if avg_velocity > 0:
            # 理想速度を 10 ピクセル/フレームと仮定
            ideal_speed = 10.0
            speed_diff = abs(avg_velocity - ideal_speed) / ideal_speed
            speed_consistency = max(0, 1.0 - velocity_variance / (avg_velocity + 1e-6))
            speed_score = max(0, min(100, (1.0 - speed_diff * 0.5) * 50 + speed_consistency * 50))

        scores["速度スコア"] = speed_score
        await asyncio.sleep(0.1)

        # 精度スコアの計算
        await self._update_progress_detailed(
            AnalysisStep.SCORE_CALCULATION,
            25,
            "精度スコアを計算中..."
        )

        trajectory_data = motion_analysis.get("軌跡解析", {})
        smoothness = trajectory_data.get("smoothness", 0)
        path_efficiency = trajectory_data.get("path_efficiency", 0)

        # 精度スコア: 滑らかさとパス効率の組み合わせ
        precision_score = (smoothness * 60 + path_efficiency * 40) * 100
        scores["精度スコア"] = precision_score
        await asyncio.sleep(0.1)

        # 安定性スコアの計算
        await self._update_progress_detailed(
            AnalysisStep.SCORE_CALCULATION,
            50,
            "安定性スコアを計算中..."
        )

        stability_data = motion_analysis.get("安定性解析", {})
        tremor_level = stability_data.get("tremor_level", 1.0)
        consistency = stability_data.get("consistency", 0)
        precision = stability_data.get("precision", 0)

        # 安定性スコア: 震えが少なく、一貫性と精度が高いほど高スコア
        stability_score = ((1.0 - tremor_level) * 40 + consistency * 30 + precision * 30) * 100
        scores["安定性スコア"] = stability_score
        await asyncio.sleep(0.1)

        # 効率性スコアの計算
        await self._update_progress_detailed(
            AnalysisStep.SCORE_CALCULATION,
            75,
            "効率性スコアを計算中..."
        )

        efficiency_data = motion_analysis.get("効率性解析", {})
        time_efficiency = efficiency_data.get("time_efficiency", 0)
        motion_economy = efficiency_data.get("motion_economy", 0)
        redundancy = efficiency_data.get("redundancy", 1.0)

        # 効率性スコア: 時間効率、動作経済性、低冗長性
        efficiency_score = (time_efficiency * 40 + motion_economy * 40 + (1.0 - redundancy) * 20) * 100
        scores["効率性スコア"] = efficiency_score
        await asyncio.sleep(0.1)

        # 総合スコア計算（重み付き平均）
        weights = {
            "速度スコア": 0.25,
            "精度スコア": 0.25,
            "安定性スコア": 0.25,
            "効率性スコア": 0.25
        }

        total_score = sum(scores[key] * weights[key] for key in scores.keys())
        scores["total_score"] = total_score

        await self._update_progress_detailed(
            AnalysisStep.SCORE_CALCULATION,
            100,
            f"スコア計算完了: 総合スコア {total_score:.1f}点"
        )

        return scores