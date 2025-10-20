"""動画解析パイプライン - 各処理モジュールを統合"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import logging
import numpy as np

from .frame_extractor import FrameExtractor
from .skeleton_detector import SkeletonDetector
from .tool_detector import ToolDetector

logger = logging.getLogger(__name__)


class VideoAnalyzer:
    """動画解析のメインパイプライン"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        """
        Args:
            progress_callback: 進捗報告用のコールバック関数
        """
        self.progress_callback = progress_callback
        self.skeleton_detector = SkeletonDetector()
        self.tool_detector = ToolDetector()
        
    async def analyze(
        self, 
        video_path: str,
        video_type: str,
        output_dir: Optional[str] = None,
        sampling_rate: int = 5
    ) -> Dict[str, Any]:
        """
        動画を解析してデータを生成
        
        Args:
            video_path: 動画ファイルパス
            video_type: 動画タイプ（internal/external）
            output_dir: 出力ディレクトリ
            sampling_rate: サンプリングレート
            
        Returns:
            解析結果の辞書
        """
        results = {
            "video_path": video_path,
            "video_type": video_type,
            "frames": [],
            "skeleton_data": [],
            "tool_data": [],
            "scores": {},
            "metadata": {}
        }
        
        try:
            # フレーム抽出器を初期化
            with FrameExtractor(video_path, sampling_rate) as extractor:
                # メタデータを保存
                results["metadata"] = extractor.get_metadata()
                total_frames_to_process = results["metadata"]["total_frames"] // results["metadata"]["frame_interval"]
                
                # 進捗報告
                await self._report_progress(0, "動画読み込み中")
                
                processed_frames = 0
                
                # フレームごとに処理
                for frame_number, timestamp, frame in extractor.extract_frames():
                    # 骨格検出（外部カメラの場合のみ）
                    skeleton_results = None
                    if video_type == "external":
                        skeleton_results = await self._detect_skeleton(frame)
                        if skeleton_results:
                            results["skeleton_data"].append({
                                "frame_number": frame_number,
                                "timestamp": timestamp,
                                "landmarks": skeleton_results
                            })
                    
                    # 器具検出
                    tool_results = await self._detect_tools(frame)
                    if tool_results:
                        results["tool_data"].append({
                            "frame_number": frame_number,
                            "timestamp": timestamp,
                            "detections": [
                                {
                                    "bbox": det.bbox,
                                    "confidence": det.confidence,
                                    "class_name": det.class_name,
                                    "track_id": det.track_id
                                }
                                for det in tool_results
                            ]
                        })
                    
                    # フレーム情報を保存
                    results["frames"].append({
                        "frame_number": frame_number,
                        "timestamp": timestamp,
                        "has_skeleton": skeleton_results is not None,
                        "tool_count": len(tool_results) if tool_results else 0
                    })
                    
                    # 進捗更新
                    processed_frames += 1
                    progress = int((processed_frames / total_frames_to_process) * 100)
                    
                    if processed_frames % 10 == 0:  # 10フレームごとに進捗報告
                        step = self._get_current_step(progress)
                        await self._report_progress(progress, step)
                    
                    # CPUを他のタスクに譲る
                    await asyncio.sleep(0)
                
                # スコア計算
                results["scores"] = await self._calculate_scores(results)
                
                # 結果をファイルに保存
                if output_dir:
                    await self._save_results(results, output_dir)
                
                # 完了報告
                await self._report_progress(100, "解析完了")
                
                # サマリー情報を追加
                results["summary"] = {
                    "total_frames_processed": processed_frames,
                    "skeleton_frames": len(results["skeleton_data"]),
                    "tool_detections": sum(len(f["detections"]) for f in results["tool_data"]),
                    "analysis_complete": True
                }
                
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            results["error"] = str(e)
            results["summary"] = {"analysis_complete": False, "error": str(e)}
            
        return results
    
    async def _detect_skeleton(self, frame: np.ndarray) -> Optional[Dict]:
        """骨格検出を実行"""
        try:
            landmarks = self.skeleton_detector.detect(frame)
            if landmarks:
                return self._landmarks_to_dict(landmarks)
        except Exception as e:
            logger.warning(f"Skeleton detection failed: {e}")
        return None
    
    async def _detect_tools(self, frame: np.ndarray) -> list:
        """器具検出を実行"""
        try:
            return self.tool_detector.detect_and_track(frame)
        except Exception as e:
            logger.warning(f"Tool detection failed: {e}")
            return []
    
    def _landmarks_to_dict(self, landmarks) -> Dict:
        """MediaPipeランドマークを辞書に変換"""
        result = {}
        if landmarks and hasattr(landmarks, 'landmark'):
            for idx, landmark in enumerate(landmarks.landmark):
                result[f"point_{idx}"] = {
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z if hasattr(landmark, 'z') else 0,
                    "visibility": landmark.visibility if hasattr(landmark, 'visibility') else 1.0
                }
        return result
    
    async def _calculate_scores(self, results: Dict) -> Dict[str, float]:
        """解析結果からスコアを計算"""
        scores = {
            "overall": 0.0,
            "smoothness": 0.0,
            "speed": 0.0,
            "accuracy": 0.0,
            "consistency": 0.0
        }
        
        try:
            # 骨格データからスムーズネスを計算
            if results["skeleton_data"]:
                positions = []
                for data in results["skeleton_data"]:
                    if "point_9" in data["landmarks"]:  # 手首の位置
                        positions.append([
                            data["landmarks"]["point_9"]["x"],
                            data["landmarks"]["point_9"]["y"]
                        ])
                
                if len(positions) > 1:
                    positions = np.array(positions)
                    # 速度を計算
                    velocities = np.diff(positions, axis=0)
                    speeds = np.linalg.norm(velocities, axis=1)
                    
                    scores["speed"] = float(np.mean(speeds) * 100)  # 正規化
                    scores["smoothness"] = float(100 - np.std(speeds) * 50)  # 変動が少ないほど高スコア
            
            # 器具検出の一貫性
            if results["tool_data"]:
                detection_counts = [len(f["detections"]) for f in results["tool_data"]]
                if detection_counts:
                    avg_detections = np.mean(detection_counts)
                    std_detections = np.std(detection_counts)
                    scores["consistency"] = float(100 - min(std_detections * 20, 100))
                    scores["accuracy"] = float(min(avg_detections * 30, 100))
            
            # 総合スコア
            scores["overall"] = float(np.mean([
                scores["smoothness"],
                scores["speed"],
                scores["accuracy"],
                scores["consistency"]
            ]))
            
        except Exception as e:
            logger.error(f"Score calculation failed: {e}")
        
        # スコアを0-100の範囲にクリップ
        for key in scores:
            scores[key] = max(0.0, min(100.0, scores[key]))
        
        return scores
    
    async def _save_results(self, results: Dict, output_dir: str):
        """結果をファイルに保存"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # JSONファイルとして保存
        json_path = output_path / "analysis_results.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            # NumPy配列などをシリアライズ可能に変換
            serializable_results = self._make_serializable(results)
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to {json_path}")
    
    def _make_serializable(self, obj):
        """オブジェクトをJSON シリアライズ可能に変換"""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._make_serializable(item) for item in obj)
        else:
            return obj
    
    def _get_current_step(self, progress: int) -> str:
        """現在の処理ステップを取得"""
        if progress < 25:
            return "動画読み込み中"
        elif progress < 50:
            return "骨格検出処理中"
        elif progress < 75:
            return "器具追跡処理中"
        else:
            return "データ生成中"
    
    async def _report_progress(self, progress: int, step: str):
        """進捗を報告"""
        if self.progress_callback:
            await self.progress_callback(progress, step)
        logger.info(f"Progress: {progress}% - {step}")