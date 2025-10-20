"""
統合動画解析モジュール

動画から手の骨格と手術器具を検出し、
総合的な手術動作解析を行う
"""

import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from pathlib import Path
import asyncio
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .skeleton_detector import HandSkeletonDetector
from .tool_detector import ToolDetector, YOLOModel

logger = logging.getLogger(__name__)


class VideoAnalyzer:
    """統合動画解析クラス"""
    
    def __init__(self, 
                 enable_skeleton: bool = True,
                 enable_tools: bool = True,
                 yolo_model_size: YOLOModel = YOLOModel.MEDIUM,
                 output_fps: int = 5,
                 save_visualizations: bool = False):
        """
        初期化
        
        Args:
            enable_skeleton: 骨格検出を有効化
            enable_tools: 器具検出を有効化
            yolo_model_size: YOLOモデルサイズ
            output_fps: 出力フレームレート
            save_visualizations: 可視化結果を保存
        """
        self.enable_skeleton = enable_skeleton
        self.enable_tools = enable_tools
        self.output_fps = output_fps
        self.save_visualizations = save_visualizations
        
        # 検出器の初期化
        self.skeleton_detector = None
        self.tool_detector = None
        
        if enable_skeleton:
            self.skeleton_detector = HandSkeletonDetector(
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            logger.info("Skeleton detector initialized")
        
        if enable_tools:
            self.tool_detector = ToolDetector(
                model_size=yolo_model_size,
                confidence_threshold=0.5
            )
            logger.info(f"Tool detector initialized with {yolo_model_size.value}")
        
        # スレッドプール（並列処理用）
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # 解析結果の保存用
        self.analysis_results = {
            "metadata": {},
            "frames": [],
            "summary": {},
            "metrics": {}
        }
    
    async def analyze_video(self, 
                          video_path: str,
                          video_type: str = "external",
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        動画を解析
        
        Args:
            video_path: 動画ファイルパス
            video_type: 動画タイプ ("internal" or "external")
            progress_callback: 進捗コールバック関数
        
        Returns:
            解析結果
        """
        logger.info(f"Starting video analysis: {video_path}")
        
        # 動画情報の取得
        video_info = self._get_video_info(video_path)
        self.analysis_results["metadata"] = {
            "video_path": video_path,
            "video_type": video_type,
            "video_info": video_info,
            "analysis_date": datetime.utcnow().isoformat(),
            "settings": {
                "skeleton_enabled": self.enable_skeleton,
                "tools_enabled": self.enable_tools,
                "output_fps": self.output_fps
            }
        }
        
        # フレーム抽出と解析
        frames_data = await self._extract_and_analyze_frames(
            video_path, 
            video_type,
            progress_callback
        )
        self.analysis_results["frames"] = frames_data
        
        # メトリクスの計算
        metrics = self._calculate_comprehensive_metrics(frames_data, video_type)
        self.analysis_results["metrics"] = metrics
        
        # サマリーの生成
        summary = self._generate_summary(frames_data, metrics, video_type)
        self.analysis_results["summary"] = summary
        
        logger.info("Video analysis completed")
        
        return self.analysis_results
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """動画情報を取得"""
        cap = cv2.VideoCapture(video_path)
        
        info = {
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "duration": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)),
            "codec": int(cap.get(cv2.CAP_PROP_FOURCC))
        }
        
        cap.release()
        return info
    
    async def _extract_and_analyze_frames(self, 
                                         video_path: str,
                                         video_type: str,
                                         progress_callback: Optional[Callable]) -> List[Dict[str, Any]]:
        """
        フレームを抽出して解析
        
        Args:
            video_path: 動画パス
            video_type: 動画タイプ
            progress_callback: 進捗コールバック
        
        Returns:
            フレーム解析結果のリスト
        """
        cap = cv2.VideoCapture(video_path)
        
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(original_fps / self.output_fps)
        
        frames_data = []
        frame_count = 0
        analyzed_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 指定FPSでサンプリング
            if frame_count % frame_interval == 0:
                # フレーム解析
                frame_result = await self._analyze_frame(
                    frame, 
                    frame_count,
                    frame_count / original_fps,
                    video_type
                )
                
                frames_data.append(frame_result)
                analyzed_count += 1
                
                # 進捗通知
                if progress_callback:
                    progress = int((analyzed_count / (total_frames / frame_interval)) * 100)
                    await progress_callback(progress, f"Analyzing frame {analyzed_count}")
                
                # 可視化の保存（オプション）
                if self.save_visualizations:
                    self._save_visualization(frame, frame_result, analyzed_count)
            
            frame_count += 1
        
        cap.release()
        
        logger.info(f"Analyzed {len(frames_data)} frames")
        return frames_data
    
    async def _analyze_frame(self, 
                           frame: np.ndarray,
                           frame_number: int,
                           timestamp: float,
                           video_type: str) -> Dict[str, Any]:
        """
        単一フレームを解析
        
        Args:
            frame: 画像フレーム
            frame_number: フレーム番号
            timestamp: タイムスタンプ
            video_type: 動画タイプ
        
        Returns:
            フレーム解析結果
        """
        result = {
            "frame_number": frame_number,
            "timestamp": timestamp,
            "detections": {}
        }
        
        # 並列処理で検出を実行
        tasks = []
        
        if self.enable_skeleton and video_type == "external":
            # 外部カメラの場合は骨格検出
            loop = asyncio.get_event_loop()
            skeleton_future = loop.run_in_executor(
                self.executor,
                self.skeleton_detector.detect_from_frame,
                frame
            )
            tasks.append(("skeleton", skeleton_future))
        
        if self.enable_tools and video_type == "internal":
            # 内部カメラの場合は器具検出
            loop = asyncio.get_event_loop()
            tools_future = loop.run_in_executor(
                self.executor,
                self.tool_detector.detect_from_frame,
                frame
            )
            tasks.append(("tools", tools_future))
        
        # 検出結果を収集
        for detection_type, future in tasks:
            detection_result = await future
            result["detections"][detection_type] = detection_result
        
        # フレーム単位のスコア計算
        result["frame_score"] = self._calculate_frame_score(result["detections"])
        
        return result
    
    def _calculate_frame_score(self, detections: Dict[str, Any]) -> Dict[str, float]:
        """
        フレーム単位のスコアを計算
        
        Args:
            detections: 検出結果
        
        Returns:
            フレームスコア
        """
        score = {
            "confidence": 0,
            "detection_quality": 0,
            "motion_stability": 0
        }
        
        confidence_scores = []
        
        # 骨格検出の信頼度
        if "skeleton" in detections:
            for hand in detections["skeleton"].get("hands", []):
                confidence_scores.append(hand.get("confidence", 0))
                
                # 手の開き具合から安定性を評価
                openness = hand.get("hand_openness", 50)
                score["motion_stability"] += (100 - abs(openness - 50)) / 100
        
        # 器具検出の信頼度
        if "tools" in detections:
            for tool in detections["tools"].get("instruments", []):
                confidence_scores.append(tool.get("confidence", 0))
        
        # スコアの集計
        if confidence_scores:
            score["confidence"] = float(np.mean(confidence_scores))
            score["detection_quality"] = float(len(confidence_scores) > 0)
        
        return score
    
    def _calculate_comprehensive_metrics(self, 
                                        frames_data: List[Dict[str, Any]],
                                        video_type: str) -> Dict[str, Any]:
        """
        総合的なメトリクスを計算
        
        Args:
            frames_data: フレーム解析結果
            video_type: 動画タイプ
        
        Returns:
            メトリクス
        """
        metrics = {
            "overall_scores": {},
            "temporal_metrics": {},
            "detection_statistics": {},
            "quality_assessment": {}
        }
        
        if video_type == "external":
            # 外部カメラ：手の動作メトリクス
            metrics["hand_metrics"] = self._calculate_hand_metrics(frames_data)
            metrics["overall_scores"]["smoothness"] = metrics["hand_metrics"].get("smoothness", 0)
            metrics["overall_scores"]["precision"] = metrics["hand_metrics"].get("precision", 0)
            
        elif video_type == "internal":
            # 内部カメラ：器具操作メトリクス
            tool_detections = [
                f["detections"].get("tools", {}) 
                for f in frames_data 
                if "tools" in f["detections"]
            ]
            
            if tool_detections and self.tool_detector:
                metrics["tool_metrics"] = self.tool_detector.calculate_motion_metrics(tool_detections)
                metrics["overall_scores"]["tool_handling"] = metrics["tool_metrics"].get("precision_score", 0)
                metrics["overall_scores"]["efficiency"] = 100 - metrics["tool_metrics"].get("tool_switches", 0) * 2
        
        # 検出統計
        total_frames = len(frames_data)
        detected_frames = sum(1 for f in frames_data if f["detections"])
        
        metrics["detection_statistics"] = {
            "total_frames": total_frames,
            "detected_frames": detected_frames,
            "detection_rate": detected_frames / total_frames if total_frames > 0 else 0,
            "average_confidence": self._calculate_average_confidence(frames_data)
        }
        
        # 品質評価
        metrics["quality_assessment"] = self._assess_video_quality(frames_data)
        
        # 総合スコア
        if metrics["overall_scores"]:
            metrics["overall_scores"]["total"] = float(
                np.mean(list(metrics["overall_scores"].values()))
            )
        
        return metrics
    
    def _calculate_hand_metrics(self, frames_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        手の動作メトリクスを計算
        
        Args:
            frames_data: フレーム解析結果
        
        Returns:
            手の動作メトリクス
        """
        metrics = {
            "smoothness": 0,
            "precision": 0,
            "consistency": 0,
            "finger_coordination": 0
        }
        
        # 手の位置データを抽出
        hand_positions = []
        finger_angles_sequence = []
        
        for frame in frames_data:
            skeleton_data = frame["detections"].get("skeleton", {})
            for hand in skeleton_data.get("hands", []):
                hand_positions.append(hand.get("palm_center"))
                finger_angles_sequence.append(hand.get("finger_angles", {}))
        
        if len(hand_positions) > 1:
            # スムーズネスの計算（位置変化の分散）
            position_changes = []
            for i in range(1, len(hand_positions)):
                if hand_positions[i] and hand_positions[i-1]:
                    dx = hand_positions[i]["x"] - hand_positions[i-1]["x"]
                    dy = hand_positions[i]["y"] - hand_positions[i-1]["y"]
                    change = np.sqrt(dx**2 + dy**2)
                    position_changes.append(change)
            
            if position_changes:
                variance = np.var(position_changes)
                metrics["smoothness"] = float(100 / (1 + variance))
        
        if finger_angles_sequence:
            # 指の協調性（角度の一貫性）
            all_angles = []
            for angles in finger_angles_sequence:
                if angles:
                    all_angles.append(list(angles.values()))
            
            if all_angles:
                angles_array = np.array(all_angles)
                # 各指の角度の標準偏差
                finger_stds = np.std(angles_array, axis=0)
                metrics["finger_coordination"] = float(100 - np.mean(finger_stds))
        
        # 精度（信頼度ベース）
        confidence_scores = []
        for frame in frames_data:
            skeleton_data = frame["detections"].get("skeleton", {})
            for hand in skeleton_data.get("hands", []):
                confidence_scores.append(hand.get("confidence", 0))
        
        if confidence_scores:
            metrics["precision"] = float(np.mean(confidence_scores) * 100)
        
        # 一貫性（検出率）
        detected_frames = sum(
            1 for f in frames_data 
            if f["detections"].get("skeleton", {}).get("hands")
        )
        metrics["consistency"] = (detected_frames / len(frames_data)) * 100 if frames_data else 0
        
        return metrics
    
    def _calculate_average_confidence(self, frames_data: List[Dict[str, Any]]) -> float:
        """平均信頼度を計算"""
        all_confidences = []
        
        for frame in frames_data:
            if "frame_score" in frame:
                all_confidences.append(frame["frame_score"].get("confidence", 0))
        
        return float(np.mean(all_confidences)) if all_confidences else 0
    
    def _assess_video_quality(self, frames_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        動画品質を評価
        
        Args:
            frames_data: フレーム解析結果
        
        Returns:
            品質評価
        """
        quality = {
            "detection_consistency": 0,
            "confidence_stability": 0,
            "coverage": 0,
            "overall_quality": "unknown"
        }
        
        if not frames_data:
            return quality
        
        # 検出の一貫性
        detection_counts = []
        confidence_values = []
        
        for frame in frames_data:
            count = 0
            for detection_type, data in frame["detections"].items():
                if detection_type == "skeleton" and data.get("hands"):
                    count += len(data["hands"])
                elif detection_type == "tools" and data.get("instruments"):
                    count += len(data["instruments"])
            detection_counts.append(count)
            
            if "frame_score" in frame:
                confidence_values.append(frame["frame_score"].get("confidence", 0))
        
        # 一貫性スコア
        if detection_counts:
            quality["detection_consistency"] = float(
                100 * (1 - np.std(detection_counts) / (np.mean(detection_counts) + 1e-6))
            )
        
        # 信頼度の安定性
        if confidence_values:
            quality["confidence_stability"] = float(
                100 * (1 - np.std(confidence_values) / (np.mean(confidence_values) + 1e-6))
            )
        
        # カバレッジ（検出されたフレームの割合）
        detected_frames = sum(1 for c in detection_counts if c > 0)
        quality["coverage"] = (detected_frames / len(frames_data)) * 100
        
        # 総合品質評価
        avg_quality = np.mean([
            quality["detection_consistency"],
            quality["confidence_stability"],
            quality["coverage"]
        ])
        
        if avg_quality >= 80:
            quality["overall_quality"] = "excellent"
        elif avg_quality >= 60:
            quality["overall_quality"] = "good"
        elif avg_quality >= 40:
            quality["overall_quality"] = "fair"
        else:
            quality["overall_quality"] = "poor"
        
        return quality
    
    def _generate_summary(self, 
                         frames_data: List[Dict[str, Any]],
                         metrics: Dict[str, Any],
                         video_type: str) -> Dict[str, Any]:
        """
        解析結果のサマリーを生成
        
        Args:
            frames_data: フレーム解析結果
            metrics: メトリクス
            video_type: 動画タイプ
        
        Returns:
            サマリー
        """
        summary = {
            "video_type": video_type,
            "total_frames_analyzed": len(frames_data),
            "key_findings": [],
            "recommendations": [],
            "performance_grade": "N/A"
        }
        
        # 主要な発見事項
        if video_type == "external" and "hand_metrics" in metrics:
            hand_metrics = metrics["hand_metrics"]
            
            if hand_metrics["smoothness"] > 70:
                summary["key_findings"].append("手の動きが非常にスムーズです")
            elif hand_metrics["smoothness"] < 40:
                summary["key_findings"].append("手の動きに改善の余地があります")
            
            if hand_metrics["finger_coordination"] > 80:
                summary["key_findings"].append("優れた指の協調性を示しています")
            
            if hand_metrics["consistency"] < 60:
                summary["key_findings"].append("検出の一貫性が低い可能性があります")
        
        elif video_type == "internal" and "tool_metrics" in metrics:
            tool_metrics = metrics["tool_metrics"]
            
            if tool_metrics.get("tool_switches", 0) > 10:
                summary["key_findings"].append("器具の切り替えが多く見られます")
            
            if tool_metrics.get("precision_score", 0) > 80:
                summary["key_findings"].append("高い精度で器具を操作しています")
            
            dominant_tool = tool_metrics.get("dominant_tool")
            if dominant_tool:
                summary["key_findings"].append(f"主に{dominant_tool}を使用しています")
        
        # 推奨事項
        overall_score = metrics.get("overall_scores", {}).get("total", 0)
        
        if overall_score < 50:
            summary["recommendations"].append("基本的な技術の練習を推奨します")
        elif overall_score < 70:
            summary["recommendations"].append("より滑らかな動作を心がけましょう")
        else:
            summary["recommendations"].append("優れた技術レベルです。この調子を維持してください")
        
        # 品質評価に基づく推奨
        quality = metrics.get("quality_assessment", {})
        if quality.get("overall_quality") == "poor":
            summary["recommendations"].append("動画の品質または照明を改善することを推奨します")
        
        # パフォーマンスグレード
        if overall_score >= 90:
            summary["performance_grade"] = "A+"
        elif overall_score >= 80:
            summary["performance_grade"] = "A"
        elif overall_score >= 70:
            summary["performance_grade"] = "B"
        elif overall_score >= 60:
            summary["performance_grade"] = "C"
        elif overall_score >= 50:
            summary["performance_grade"] = "D"
        else:
            summary["performance_grade"] = "F"
        
        return summary
    
    def _save_visualization(self, 
                           frame: np.ndarray,
                           frame_result: Dict[str, Any],
                           frame_index: int):
        """
        可視化結果を保存
        
        Args:
            frame: 元フレーム
            frame_result: 解析結果
            frame_index: フレームインデックス
        """
        annotated_frame = frame.copy()
        
        # 骨格の描画
        if "skeleton" in frame_result["detections"] and self.skeleton_detector:
            annotated_frame = self.skeleton_detector.draw_landmarks(
                annotated_frame,
                frame_result["detections"]["skeleton"]
            )
        
        # 器具の描画
        if "tools" in frame_result["detections"] and self.tool_detector:
            annotated_frame = self.tool_detector.draw_detections(
                annotated_frame,
                frame_result["detections"]["tools"]
            )
        
        # スコア情報を描画
        if "frame_score" in frame_result:
            score_text = f"Score: {frame_result['frame_score']['confidence']:.2f}"
            cv2.putText(annotated_frame, score_text,
                       (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 保存（実装時はパスを適切に設定）
        # output_path = f"output/frame_{frame_index:04d}.jpg"
        # cv2.imwrite(output_path, annotated_frame)
    
    def export_results(self, output_path: str, format: str = "json"):
        """
        解析結果をエクスポート
        
        Args:
            output_path: 出力パス
            format: 出力形式 ("json" or "csv")
        """
        output_path = Path(output_path)
        
        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.analysis_results, f, indent=2, ensure_ascii=False)
            logger.info(f"Results exported to {output_path}")
        
        elif format == "csv":
            # CSV形式でのエクスポート（簡易版）
            import csv
            
            csv_path = output_path.with_suffix(".csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                
                # ヘッダー
                writer.writerow([
                    "Frame", "Timestamp", "Detection Type", 
                    "Confidence", "Score"
                ])
                
                # データ
                for frame in self.analysis_results.get("frames", []):
                    frame_num = frame["frame_number"]
                    timestamp = frame["timestamp"]
                    
                    for det_type, det_data in frame["detections"].items():
                        if det_type == "skeleton":
                            for hand in det_data.get("hands", []):
                                writer.writerow([
                                    frame_num, timestamp, "hand",
                                    hand.get("confidence", 0),
                                    frame.get("frame_score", {}).get("confidence", 0)
                                ])
                        elif det_type == "tools":
                            for tool in det_data.get("instruments", []):
                                writer.writerow([
                                    frame_num, timestamp, tool["type"],
                                    tool.get("confidence", 0),
                                    frame.get("frame_score", {}).get("confidence", 0)
                                ])
            
            logger.info(f"CSV exported to {csv_path}")
    
    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)