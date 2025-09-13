"""動画解析サービス"""

import asyncio
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.core.websocket import manager
from app.models.database import AnalysisResult, SessionLocal, AnalysisStatus
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.video_analyzer import VideoAnalyzer

logger = logging.getLogger(__name__)


class AnalysisService:
    """動画解析処理サービス"""
    
    def __init__(self):
        self.skeleton_detector = None
        self.current_progress = 0
        self.analysis_id = None
        
    async def process_video(
        self, 
        video_id: str,
        video_path: str, 
        video_type: str,
        analysis_id: str
    ) -> Dict[str, Any]:
        """
        動画を解析してモーションデータを抽出
        
        Args:
            video_id: 動画ID
            video_path: 動画ファイルパス
            video_type: 動画タイプ (internal/external)
            analysis_id: 解析ID
        
        Returns:
            解析結果
        """
        self.analysis_id = analysis_id
        
        try:
            # ステップ1: 動画情報取得
            await self._update_progress("動画情報を取得中...", 10, "preprocessing")
            video_info = self._get_video_info(video_path)
            
            # ステップ2: フレーム抽出
            await self._update_progress("フレームを抽出中...", 20, "frame_extraction")
            frames = await self._extract_frames(video_path, fps=5)
            
            # ステップ3: 骨格検出 (外部カメラの場合のみ)
            skeleton_data = []
            if video_type == "external":
                await self._update_progress("手の骨格を検出中...", 40, "skeleton_detection")
                skeleton_data = await self._detect_skeleton(frames)
            
            # ステップ4: 器具検出 (内部カメラの場合 - 将来実装)
            instrument_data = []
            if video_type == "internal":
                await self._update_progress("手術器具を検出中...", 40, "instrument_detection")
                # TODO: YOLO実装
                instrument_data = self._mock_instrument_detection(len(frames))
            
            # ステップ5: モーション解析
            await self._update_progress("モーションを解析中...", 60, "motion_analysis")
            motion_analysis = await self._analyze_motion(skeleton_data, instrument_data)
            
            # ステップ6: スコア計算
            await self._update_progress("スコアを計算中...", 80, "scoring")
            scores = self._calculate_scores(motion_analysis)
            
            # ステップ7: データ保存
            await self._update_progress("データを保存中...", 90, "saving")
            await self._save_results(
                video_id,
                analysis_id,
                video_info,
                skeleton_data,
                instrument_data,
                motion_analysis,
                scores
            )
            
            # 完了
            await self._update_progress("解析完了", 100, "completed")
            
            return {
                "video_id": video_id,
                "analysis_id": analysis_id,
                "video_info": video_info,
                "motion_analysis": motion_analysis,
                "scores": scores,
                "frame_count": len(frames),
                "skeleton_detected": len(skeleton_data) > 0,
                "instrument_detected": len(instrument_data) > 0
            }
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            await self._update_progress(f"エラーが発生しました: {str(e)}", self.current_progress, "failed")
            raise
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """動画情報を取得"""
        cap = cv2.VideoCapture(video_path)
        
        info = {
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "duration": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS))
        }
        
        cap.release()
        return info
    
    async def _extract_frames(self, video_path: str, fps: int = 5) -> List[Dict[str, Any]]:
        """動画からフレームを抽出"""
        frames = []
        cap = cv2.VideoCapture(video_path)
        
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(original_fps / fps)
        frame_count = 0
        extracted_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frames.append({
                    "frame_number": extracted_count,
                    "timestamp": frame_count / original_fps,
                    "image": frame
                })
                extracted_count += 1
                
                # 進捗更新
                if extracted_count % 10 == 0:
                    progress = 20 + (extracted_count / (cap.get(cv2.CAP_PROP_FRAME_COUNT) / frame_interval)) * 10
                    await self._update_progress(
                        f"フレーム抽出中... ({extracted_count}フレーム)",
                        min(30, int(progress)),
                        "frame_extraction"
                    )
            
            frame_count += 1
        
        cap.release()
        logger.info(f"Extracted {len(frames)} frames from video")
        return frames
    
    async def _detect_skeleton(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """手の骨格を検出"""
        if self.skeleton_detector is None:
            self.skeleton_detector = HandSkeletonDetector()
        
        skeleton_data = []
        total_frames = len(frames)
        
        for i, frame_data in enumerate(frames):
            # 骨格検出
            detection_result = self.skeleton_detector.detect_from_frame(frame_data["image"])
            detection_result["frame_number"] = frame_data["frame_number"]
            detection_result["timestamp"] = frame_data["timestamp"]
            skeleton_data.append(detection_result)
            
            # 進捗更新
            if i % 5 == 0:
                progress = 40 + (i / total_frames) * 20
                await self._update_progress(
                    f"骨格検出中... ({i}/{total_frames})",
                    int(progress),
                    "skeleton_detection"
                )
        
        logger.info(f"Detected skeleton in {len([d for d in skeleton_data if d['hands']])} frames")
        return skeleton_data
    
    def _mock_instrument_detection(self, frame_count: int) -> List[Dict[str, Any]]:
        """器具検出のモック（将来YOLO実装）"""
        instrument_data = []
        
        for i in range(frame_count):
            # ダミーデータ生成
            instrument_data.append({
                "frame_number": i,
                "instruments": [
                    {
                        "type": "forceps",
                        "confidence": 0.95,
                        "bbox": [100, 100, 200, 200],
                        "position": {"x": 150, "y": 150}
                    }
                ]
            })
        
        return instrument_data
    
    async def _analyze_motion(
        self, 
        skeleton_data: List[Dict[str, Any]], 
        instrument_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """モーション解析"""
        analysis = {
            "smoothness": 0,
            "speed": 0,
            "accuracy": 0,
            "efficiency": 0,
            "motion_patterns": [],
            "key_frames": []
        }
        
        if skeleton_data:
            # スムーズネス計算
            analysis["smoothness"] = self._calculate_smoothness(skeleton_data)
            
            # スピード計算
            analysis["speed"] = self._calculate_speed(skeleton_data)
            
            # キーフレーム検出
            analysis["key_frames"] = self._detect_key_frames(skeleton_data)
        
        if instrument_data:
            # 精度計算（器具の動きから）
            analysis["accuracy"] = 85  # ダミー値
            
            # 効率計算
            analysis["efficiency"] = 90  # ダミー値
        
        return analysis
    
    def _calculate_smoothness(self, skeleton_data: List[Dict[str, Any]]) -> float:
        """動きのスムーズネスを計算"""
        if len(skeleton_data) < 2:
            return 0
        
        # 手首の位置変化から計算
        velocities = []
        for i in range(1, len(skeleton_data)):
            if skeleton_data[i]["hands"] and skeleton_data[i-1]["hands"]:
                curr = skeleton_data[i]["hands"][0]["landmarks"][0]  # 手首
                prev = skeleton_data[i-1]["hands"][0]["landmarks"][0]
                
                dx = curr["x"] - prev["x"]
                dy = curr["y"] - prev["y"]
                velocity = np.sqrt(dx**2 + dy**2)
                velocities.append(velocity)
        
        if velocities:
            # 速度の変動係数から計算
            std = np.std(velocities)
            mean = np.mean(velocities)
            if mean > 0:
                cv = std / mean
                smoothness = max(0, min(100, 100 * (1 - cv)))
                return smoothness
        
        return 75  # デフォルト値
    
    def _calculate_speed(self, skeleton_data: List[Dict[str, Any]]) -> float:
        """動作速度を計算"""
        if len(skeleton_data) < 2:
            return 0
        
        total_distance = 0
        valid_frames = 0
        
        for i in range(1, len(skeleton_data)):
            if skeleton_data[i]["hands"] and skeleton_data[i-1]["hands"]:
                curr = skeleton_data[i]["hands"][0]["landmarks"][0]  # 手首
                prev = skeleton_data[i-1]["hands"][0]["landmarks"][0]
                
                dx = curr["x"] - prev["x"]
                dy = curr["y"] - prev["y"]
                distance = np.sqrt(dx**2 + dy**2)
                total_distance += distance
                valid_frames += 1
        
        if valid_frames > 0:
            avg_distance = total_distance / valid_frames
            # 距離を0-100のスコアに変換
            speed_score = min(100, avg_distance * 1000)
            return speed_score
        
        return 50  # デフォルト値
    
    def _detect_key_frames(self, skeleton_data: List[Dict[str, Any]]) -> List[int]:
        """重要なフレームを検出"""
        key_frames = []
        
        for i, data in enumerate(skeleton_data):
            if data.get("hands"):
                # 指の曲がりが大きいフレームを検出
                finger_angles = data["hands"][0].get("finger_angles", {})
                if finger_angles:
                    avg_angle = np.mean(list(finger_angles.values()))
                    if avg_angle > 45:  # 閾値
                        key_frames.append(i)
        
        return key_frames[:10]  # 最大10フレーム
    
    def _calculate_scores(self, motion_analysis: Dict[str, Any]) -> Dict[str, float]:
        """総合スコアを計算"""
        scores = {
            "smoothness": motion_analysis["smoothness"],
            "speed": motion_analysis["speed"],
            "accuracy": motion_analysis["accuracy"],
            "efficiency": motion_analysis["efficiency"],
            "overall": 0
        }
        
        # 総合スコア計算
        weights = {
            "smoothness": 0.25,
            "speed": 0.20,
            "accuracy": 0.30,
            "efficiency": 0.25
        }
        
        overall = sum(scores[key] * weights[key] for key in weights)
        scores["overall"] = overall
        
        return scores
    
    async def _save_results(
        self,
        video_id: str,
        analysis_id: str,
        video_info: Dict[str, Any],
        skeleton_data: List[Dict[str, Any]],
        instrument_data: List[Dict[str, Any]],
        motion_analysis: Dict[str, Any],
        scores: Dict[str, float]
    ):
        """解析結果をデータベースに保存"""
        db = SessionLocal()
        try:
            # 既存のレコードを更新または新規作成
            result = db.query(AnalysisResult).filter(
                AnalysisResult.id == analysis_id
            ).first()
            
            if not result:
                result = AnalysisResult(
                    id=analysis_id,
                    video_id=video_id,
                    created_at=datetime.utcnow()
                )
                db.add(result)
            
            # 結果を更新（JSONはdictのまま保存、Enumは型で保存）
            result.status = AnalysisStatus.COMPLETED
            result.skeleton_data = skeleton_data
            result.instrument_data = instrument_data
            result.motion_analysis = motion_analysis
            result.scores = scores
            result.completed_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Analysis results saved for {analysis_id}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save results: {e}")
            raise
        finally:
            db.close()
    
    async def _update_progress(
        self,
        message: str,
        progress: int,
        step_status: str
    ):
        """進捗状況をWebSocket経由で送信"""
        self.current_progress = progress
        
        update_data = {
            "type": "progress",
            "analysis_id": self.analysis_id,
            "progress": progress,
            "message": message,
            "step_status": step_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # WebSocket経由で送信
        await manager.broadcast(json.dumps(update_data))
        
        # ログ出力
        logger.info(f"Progress: {progress}% - {message}")
