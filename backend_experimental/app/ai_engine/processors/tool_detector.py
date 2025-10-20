"""
手術器具検出モジュール

YOLOv8を使用して手術器具を検出する
検出精度に応じて複数のモデルサイズを選択可能
"""

import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from enum import Enum
import random

logger = logging.getLogger(__name__)


class YOLOModel(Enum):
    """YOLOモデルのサイズ定義"""
    NANO = "yolov8n"      # 最速・最軽量 (精度低)
    SMALL = "yolov8s"     # 軽量 (精度中低)
    MEDIUM = "yolov8m"    # 中間 (精度中)
    LARGE = "yolov8l"     # 大型 (精度高)
    XLARGE = "yolov8x"    # 最大・最高精度 (処理速度遅)


class SurgicalTool(Enum):
    """手術器具の種類"""
    FORCEPS = "forceps"                # 鉗子
    SCISSORS = "scissors"              # ハサミ
    NEEDLE_HOLDER = "needle_holder"    # 持針器
    SCALPEL = "scalpel"               # メス
    RETRACTOR = "retractor"            # 開創器
    SUCTION = "suction"                # 吸引器
    ELECTROCAUTERY = "electrocautery"  # 電気メス
    CLIP_APPLIER = "clip_applier"      # クリップ鉗子
    GRASPER = "grasper"                # 把持鉗子
    DISSECTOR = "dissector"            # 剥離子


class ToolDetector:
    """手術器具検出クラス"""
    
    def __init__(self,
                 model_size: YOLOModel = YOLOModel.NANO,
                 confidence_threshold: float = 0.5,
                 nms_threshold: float = 0.45,
                 use_gpu: bool = False,
                 force_mock: bool = False):
        """
        初期化

        Args:
            model_size: 使用するYOLOモデルのサイズ
            confidence_threshold: 検出の最小信頼度
            nms_threshold: Non-Maximum Suppressionの閾値
            use_gpu: GPU使用フラグ
            force_mock: 強制的にモックモードを使用
        """
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.use_gpu = use_gpu
        self.model = None

        if force_mock:
            self.is_mock = True
            self.mock_detection_probability = 0.8
            logger.info(f"ToolDetector initialized in MOCK mode (forced)")
        else:
            # 実際のYOLOモデルをロード
            try:
                self.model = self._load_model()
                self.is_mock = False
                logger.info(f"ToolDetector initialized with {model_size.value} model (Real YOLO)")
            except Exception as e:
                logger.warning(f"Failed to load YOLO model, falling back to mock mode: {e}")
                self.is_mock = True
                self.mock_detection_probability = 0.8
    
    def _load_model(self):
        """
        YOLOモデルをロード

        Returns:
            YOLO model instance

        Raises:
            Exception: モデルロードに失敗した場合
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            raise Exception("ultralytics package not installed")

        from pathlib import Path

        # モデルファイルを探索
        model_filename = f"{self.model_size.value}.pt"
        possible_paths = [
            Path(model_filename),  # カレントディレクトリ
            Path(f"backend_experimental/{model_filename}"),  # プロジェクトルートから
            Path(__file__).parent.parent.parent.parent / model_filename  # 絶対パス
        ]

        model_path = None
        for path in possible_paths:
            if path.exists():
                model_path = path
                logger.info(f"Found YOLO model at: {model_path}")
                break

        if not model_path:
            raise Exception(f"YOLO model not found: {model_filename}")

        # モデルロード
        model = YOLO(str(model_path))
        logger.info(f"Successfully loaded {self.model_size.value} YOLO model")
        return model
    
    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        フレームから手術器具を検出
        
        Args:
            frame: 入力画像フレーム (BGR)
        
        Returns:
            検出結果の辞書
        """
        if self.is_mock:
            return self._mock_detection(frame)
        else:
            return self._real_detection(frame)
    
    def _real_detection(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        実際のYOLO検出

        Args:
            frame: 入力画像フレーム

        Returns:
            検出結果
        """
        if self.model is None:
            raise RuntimeError("YOLO model not loaded")

        height, width = frame.shape[:2]

        # YOLO推論実行
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)

        # 手術器具クラスマッピング（COCOクラスから）
        coco_to_surgical = {
            43: "knife",  # knife → scalpel
            76: "scissors",  # scissors → surgical scissors
            # 他のクラスも器具として扱う可能性
            45: "bowl",  # bowl → surgical bowl
            47: "cup",  # cup → medicine cup
        }

        detection_result = {
            "instruments": [],
            "frame_shape": (height, width),
            "model_info": {
                "model_size": self.model_size.value,
                "confidence_threshold": self.confidence_threshold,
                "is_mock": False
            }
        }

        # 検出結果を解析
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # クラスID、信頼度、座標を取得
                cls_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                # 器具として認識可能なクラスのみ
                tool_type = coco_to_surgical.get(cls_id, f"object_{cls_id}")

                # 中心座標計算
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                instrument_data = {
                    "id": len(detection_result["instruments"]),
                    "type": tool_type,
                    "confidence": confidence,
                    "bbox": {
                        "x_min": float(x1),
                        "y_min": float(y1),
                        "x_max": float(x2),
                        "y_max": float(y2)
                    },
                    "center": {
                        "x": float(center_x),
                        "y": float(center_y)
                    },
                    "orientation": 0.0,  # YOLOでは向きは取れない
                    "area": float((x2 - x1) * (y2 - y1)),
                    "aspect_ratio": float((x2 - x1) / (y2 - y1 + 1e-6))
                }

                detection_result["instruments"].append(instrument_data)

        logger.info(f"Detected {len(detection_result['instruments'])} instruments")
        return detection_result
    
    def _mock_detection(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        モック検出（開発・テスト用）
        
        Args:
            frame: 入力画像フレーム
        
        Returns:
            ダミーの検出結果
        """
        height, width = frame.shape[:2]
        
        detection_result = {
            "instruments": [],
            "frame_shape": (height, width),
            "model_info": {
                "model_size": self.model_size.value,
                "confidence_threshold": self.confidence_threshold,
                "is_mock": True
            }
        }
        
        # ランダムに器具を検出（シミュレーション）
        if random.random() < self.mock_detection_probability:
            num_instruments = random.randint(1, 3)
            
            for i in range(num_instruments):
                # ランダムな器具タイプを選択
                tool_type = random.choice(list(SurgicalTool))
                
                # ランダムな位置とサイズを生成
                center_x = random.randint(width // 4, 3 * width // 4)
                center_y = random.randint(height // 4, 3 * height // 4)
                box_width = random.randint(50, min(200, width // 3))
                box_height = random.randint(30, min(150, height // 3))
                
                x_min = max(0, center_x - box_width // 2)
                y_min = max(0, center_y - box_height // 2)
                x_max = min(width, center_x + box_width // 2)
                y_max = min(height, center_y + box_height // 2)
                
                # 信頼度をランダムに生成
                confidence = random.uniform(self.confidence_threshold, 0.95)
                
                # 器具の向きを計算（簡易版）
                orientation = random.uniform(0, 360)
                
                instrument_data = {
                    "id": i,
                    "type": tool_type.value,
                    "confidence": float(confidence),
                    "bbox": {
                        "x_min": float(x_min),
                        "y_min": float(y_min),
                        "x_max": float(x_max),
                        "y_max": float(y_max)
                    },
                    "center": {
                        "x": float(center_x),
                        "y": float(center_y)
                    },
                    "orientation": float(orientation),
                    "area": float((x_max - x_min) * (y_max - y_min)),
                    "aspect_ratio": float((x_max - x_min) / (y_max - y_min + 1e-6))
                }
                
                detection_result["instruments"].append(instrument_data)
        
        return detection_result
    
    def upgrade_model(self, target_accuracy: float = 0.9) -> YOLOModel:
        """
        目標精度に基づいてモデルをアップグレード
        
        Args:
            target_accuracy: 目標検出精度
        
        Returns:
            推奨されるモデルサイズ
        """
        # 精度とモデルサイズのマッピング（推定値）
        accuracy_map = {
            YOLOModel.NANO: 0.65,
            YOLOModel.SMALL: 0.75,
            YOLOModel.MEDIUM: 0.83,
            YOLOModel.LARGE: 0.88,
            YOLOModel.XLARGE: 0.92
        }
        
        recommended_model = YOLOModel.MEDIUM
        
        for model, accuracy in accuracy_map.items():
            if accuracy >= target_accuracy:
                recommended_model = model
                break
            recommended_model = model
        
        if recommended_model != self.model_size:
            logger.info(f"Upgrading model from {self.model_size.value} to {recommended_model.value}")
            self.model_size = recommended_model
            # 実際の実装では、ここでモデルを再ロード
            # self.model = self._load_model()
        
        return recommended_model
    
    def calculate_motion_metrics(self, 
                                detections_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        検出結果のシーケンスから動作メトリクスを計算
        
        Args:
            detections_sequence: 時系列の検出結果リスト
        
        Returns:
            動作メトリクス
        """
        metrics = {
            "tool_usage_frequency": {},
            "average_confidence": 0,
            "motion_smoothness": 0,
            "tool_switches": 0,
            "dominant_tool": None,
            "precision_score": 0
        }
        
        if not detections_sequence:
            return metrics
        
        # 器具使用頻度の計算
        tool_counts = {}
        total_confidence = 0
        confidence_count = 0
        prev_tools = set()
        
        for detection in detections_sequence:
            current_tools = set()
            for instrument in detection.get("instruments", []):
                tool_type = instrument["type"]
                tool_counts[tool_type] = tool_counts.get(tool_type, 0) + 1
                current_tools.add(tool_type)
                total_confidence += instrument["confidence"]
                confidence_count += 1
            
            # 器具切り替え回数の計算
            if prev_tools and prev_tools != current_tools:
                metrics["tool_switches"] += 1
            prev_tools = current_tools
        
        # メトリクスの集計
        if tool_counts:
            total_detections = sum(tool_counts.values())
            metrics["tool_usage_frequency"] = {
                tool: count / total_detections 
                for tool, count in tool_counts.items()
            }
            metrics["dominant_tool"] = max(tool_counts, key=tool_counts.get)
        
        if confidence_count > 0:
            metrics["average_confidence"] = total_confidence / confidence_count
        
        # スムーズネスの計算（位置変化の分散から）
        metrics["motion_smoothness"] = self._calculate_smoothness(detections_sequence)
        
        # 精度スコア（信頼度とスムーズネスから計算）
        metrics["precision_score"] = (
            metrics["average_confidence"] * 0.6 + 
            metrics["motion_smoothness"] * 0.4
        ) * 100
        
        return metrics
    
    def _calculate_smoothness(self, detections_sequence: List[Dict[str, Any]]) -> float:
        """
        動きのスムーズネスを計算
        
        Args:
            detections_sequence: 時系列の検出結果
        
        Returns:
            スムーズネススコア（0-1）
        """
        if len(detections_sequence) < 2:
            return 0.5
        
        position_changes = []
        
        for i in range(1, len(detections_sequence)):
            prev_instruments = {
                inst["id"]: inst["center"] 
                for inst in detections_sequence[i-1].get("instruments", [])
            }
            curr_instruments = {
                inst["id"]: inst["center"] 
                for inst in detections_sequence[i].get("instruments", [])
            }
            
            for inst_id, curr_pos in curr_instruments.items():
                if inst_id in prev_instruments:
                    prev_pos = prev_instruments[inst_id]
                    distance = np.sqrt(
                        (curr_pos["x"] - prev_pos["x"])**2 + 
                        (curr_pos["y"] - prev_pos["y"])**2
                    )
                    position_changes.append(distance)
        
        if position_changes:
            # 変化の分散が小さいほどスムーズ
            variance = np.var(position_changes)
            # 正規化（0-1の範囲に）
            smoothness = 1 / (1 + variance / 100)
            return float(smoothness)
        
        return 0.5
    
    def draw_detections(self, 
                       frame: np.ndarray, 
                       detection_result: Dict[str, Any]) -> np.ndarray:
        """
        検出結果を画像に描画
        
        Args:
            frame: 入力画像
            detection_result: 検出結果
        
        Returns:
            描画された画像
        """
        annotated_frame = frame.copy()
        
        # カラーマップ（器具タイプごとに色を変える）
        color_map = {
            "forceps": (0, 255, 0),        # 緑
            "scissors": (255, 0, 0),       # 青
            "needle_holder": (0, 0, 255),  # 赤
            "scalpel": (255, 255, 0),      # シアン
            "retractor": (255, 0, 255),    # マゼンタ
            "suction": (0, 255, 255),      # イエロー
            "electrocautery": (128, 255, 128),
            "clip_applier": (255, 128, 128),
            "grasper": (128, 128, 255),
            "dissector": (255, 255, 128)
        }
        
        for instrument in detection_result.get("instruments", []):
            bbox = instrument["bbox"]
            tool_type = instrument["type"]
            confidence = instrument["confidence"]
            
            # 色を取得
            color = color_map.get(tool_type, (0, 255, 0))
            
            # バウンディングボックスを描画
            x_min = int(bbox["x_min"])
            y_min = int(bbox["y_min"])
            x_max = int(bbox["x_max"])
            y_max = int(bbox["y_max"])
            
            cv2.rectangle(annotated_frame, (x_min, y_min), (x_max, y_max), color, 2)
            
            # ラベルを描画
            label = f"{tool_type} ({confidence:.2f})"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # ラベル背景
            cv2.rectangle(annotated_frame,
                         (x_min, y_min - label_size[1] - 4),
                         (x_min + label_size[0], y_min),
                         color, -1)
            
            # ラベルテキスト
            cv2.putText(annotated_frame, label,
                       (x_min, y_min - 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # 中心点を描画
            center_x = int(instrument["center"]["x"])
            center_y = int(instrument["center"]["y"])
            cv2.circle(annotated_frame, (center_x, center_y), 3, color, -1)
        
        # モデル情報を表示
        if detection_result.get("model_info", {}).get("is_mock"):
            cv2.putText(annotated_frame, "MOCK MODE",
                       (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return annotated_frame