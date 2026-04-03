# 実験版実装計画書：SAM2 Video API統合による器具トラッキング精度向上

**作成日**: 2025-10-11
**バージョン**: v1.0
**目的**: 器具トラッキング精度向上のための実験的実装

---

## 📋 目次

1. [実装概要](#1-実装概要)
2. [現状分析と課題](#2-現状分析と課題)
3. [改善戦略](#3-改善戦略)
4. [技術アーキテクチャ](#4-技術アーキテクチャ)
5. [実装詳細](#5-実装詳細)
6. [テスト計画](#6-テスト計画)
7. [成功判定基準](#7-成功判定基準)
8. [ロールバック計画](#8-ロールバック計画)

---

## 1. 実装概要

### 1.1 目的
- **主目的**: 手術器具のトラッキング精度を向上させる
- **副目的**: オクルージョン（遮蔽）耐性を強化する
- **制約**: フロントエンドは基本的に変更しない（バックエンドのみ改善）

### 1.2 実装範囲

| コンポーネント | 変更有無 | 変更内容 |
|---------------|---------|---------|
| **フロントエンド** | ❌ なし | 既存UIのまま |
| **API仕様** | ❌ なし | エンドポイント・レスポンス形式維持 |
| **SAM2トラッカー** | ✅ あり | Video APIへの切り替え |
| **解析サービス** | ✅ あり | 新トラッカーの統合 |
| **データベース** | ❌ なし | スキーマ変更なし |

### 1.3 期待効果

```
【現状の問題】
├─ フレーム単位処理 → 時間的コンテキストなし
├─ オクルージョン弱い → 遮蔽後の復帰失敗
└─ ID切り替わり → 同一器具が別IDとして検出

【改善後】
├─ ビデオ全体処理 → 時間的一貫性確保
├─ オクルージョン強い → メモリバンクで復帰
└─ ID安定化 → 一貫したオブジェクトID
```

---

## 2. 現状分析と課題

### 2.1 現行実装の問題点

#### 問題1: フレーム単位の独立処理

**現状コード（`backend_experimental/app/ai_engine/processors/sam2_tracker.py`）:**
```python
# 各フレームを個別に処理
for frame_idx, frame in enumerate(frames):
    # 前後のフレーム情報を使わない
    result = self.predictor.predict(frame, points, labels)
    results.append(result)
```

**問題点:**
- ✗ 各フレームが独立 → 時間的一貫性なし
- ✗ 前フレームのマスクを活用できない
- ✗ オクルージョン発生時に追跡ロスト

**データ:**
```
フレーム100: 器具検出 ✓ (obj_id=1)
フレーム101: 手に遮蔽 ✗ (検出失敗)
フレーム102: 器具再出現 ✓ (obj_id=2) ← 新しいIDとして誤検出
```

#### 問題2: オクルージョン耐性の欠如

**現象:**
```
1. 器具が手で一時的に隠れる
2. 検出が途切れる
3. 再出現時に別の器具として認識
4. トラッキングIDが変わる
5. 軌跡が分断される
```

**影響:**
- メトリクス計算が不正確（軌跡が途切れる）
- 動作解析の信頼性低下
- ユーザー体験の悪化

#### 問題3: メモリ効率の非最適性

**現状:**
```python
# 全フレームをメモリに保持
frames = await self._extract_frames(video_path)  # 1000フレーム × 1920×1080 × 3
# → 約6GB メモリ消費
```

---

## 3. 改善戦略

### 3.1 SAM2 Video API の活用

#### 3.1.1 Video API の特徴

**sam2_tracerからの学習:**
```python
from sam2.build_sam import build_sam2_video_predictor

# ビデオ全体をコンテキストとして処理
predictor = build_sam2_video_predictor(config, checkpoint, device)
inference_state = predictor.init_state(video_path=frames_dir)

# 初期フレームで対象を指定
predictor.add_new_points_or_box(
    inference_state=inference_state,
    frame_idx=0,  # 最初のフレームのみ
    obj_id=0,
    points=points,
    labels=labels
)

# 全フレームに自動伝播
for out_frame_idx, out_obj_ids, out_mask_logits in \
        predictor.propagate_in_video(inference_state):
    # フレーム間の時間的関係を考慮した追跡結果
    video_segments[out_frame_idx] = process_masks(out_mask_logits)
```

**主要な利点:**

| 機能 | 説明 | 効果 |
|-----|------|-----|
| **Memory Bank** | 過去フレームのマスク履歴を保持 | オクルージョン後の復帰 |
| **Temporal Context** | フレーム間の時間的関係を学習 | ID安定化 |
| **Propagation** | 初期マスクを全フレームに伝播 | 手動指定は最初だけ |
| **Multi-Object** | 複数器具を同時追跡 | 効率的な並列処理 |

#### 3.1.2 アーキテクチャ比較

```
【現行】フレーム単位処理
Frame 0 → SAM2 → Mask 0
Frame 1 → SAM2 → Mask 1  (独立)
Frame 2 → SAM2 → Mask 2  (独立)
Frame 3 → SAM2 → Mask 3  (独立)
  ↑ 各フレームが独立、前後関係なし

【改善後】ビデオ全体処理
Frame 0: ユーザー指定
  ↓ SAM2 Video API (Memory Bank)
Frame 0-999: 自動伝播
  - Frame間の一貫性保持
  - オクルージョン補間
  - ID安定化
```

### 3.2 実装アプローチ

#### アプローチA: 完全置き換え（推奨）

**方針:**
- 既存の `SAM2Tracker` を SAM2 Video API ベースに書き換え
- インターフェースは維持（API互換性確保）

**利点:**
- ✅ シンプルな実装
- ✅ コード重複なし
- ✅ 保守性高い

#### アプローチB: ハイブリッド（フォールバック対応）

**方針:**
- Video API を優先使用
- エラー時にフレーム単位処理にフォールバック

**利点:**
- ✅ 安定性最優先
- ✅ エラー時の保険

**実装:**
```python
class SAM2Tracker:
    async def track_video(self, frames, instruments):
        try:
            # Video API（新実装）
            return await self._track_with_video_api(frames, instruments)
        except Exception as e:
            logger.warning(f"Video API failed: {e}, falling back to frame-by-frame")
            # フレーム単位処理（既存実装）
            return await self._track_frame_by_frame(frames, instruments)
```

**推奨**: **アプローチA（完全置き換え）**
- 実験版なので思い切った変更が可能
- 問題があれば安定版に切り戻せば良い

---

## 4. 技術アーキテクチャ

### 4.1 システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                    フロントエンド (変更なし)                    │
│  ・動画アップロード                                             │
│  ・解析開始リクエスト                                           │
│  ・WebSocketで進捗受信                                         │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼────────────────────────────────────────┐
│              FastAPI Backend (backend_experimental/)         │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │   AnalysisServiceV2 (軽微な変更)                      │  │
│  │   - トラッカー初期化ロジック更新                        │  │
│  │   - WebSocket通知メッセージ追加                        │  │
│  └──────────────────┬──────────────────────────────────┘  │
│                     │                                        │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │   SAM2TrackerVideo (新実装) ★                        │  │
│  │                                                       │  │
│  │   [主要メソッド]                                       │  │
│  │   ・initialize_from_frames()                          │  │
│  │     - inference state作成                             │  │
│  │     - 器具プロンプト登録                              │  │
│  │                                                       │  │
│  │   ・propagate_in_video()                              │  │
│  │     - 全フレームに追跡を伝播                          │  │
│  │     - Memory Bankで時間的一貫性確保                   │  │
│  │                                                       │  │
│  │   ・extract_trajectories()                            │  │
│  │     - 軌跡データの抽出                                │  │
│  │     - フロントエンド互換形式に変換                     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │   SAM2 Video Predictor (sam2ライブラリ)               │  │
│  │   - Memory Bank機構                                   │  │
│  │   - Temporal Attention                                │  │
│  │   - Multi-object tracking                             │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 データフロー

```
1. ユーザーが動画アップロード + 解析開始
   ↓
2. AnalysisServiceV2.analyze_video()
   ├─ フレーム抽出 (既存)
   ├─ 骨格検出 (既存)
   └─ 器具追跡 ★ 新実装
   ↓
3. SAM2TrackerVideo.initialize_from_frames()
   ├─ フレームリストからinference state作成
   ├─ Frame 0で器具プロンプト登録
   │  (ポイント/ボックス/マスク)
   └─ Memory Bank初期化
   ↓
4. SAM2TrackerVideo.propagate_in_video()
   ├─ SAM2が全フレームを自動追跡
   ├─ 時間的コンテキストを考慮
   ├─ オクルージョン補間
   └─ 一貫したobj_idを維持
   ↓
5. SAM2TrackerVideo.extract_trajectories()
   ├─ 各obj_idの軌跡を抽出
   ├─ フレーム番号と座標のマッピング
   └─ 既存のデータ形式に変換
   ↓
6. AnalysisServiceV2が結果を保存
   ├─ データベースに保存
   └─ WebSocketで完了通知
   ↓
7. フロントエンドが結果を表示
   (変更なし、既存UIで表示)
```

### 4.3 データ構造設計

#### 4.3.1 入力データ（変更なし）

```python
# フロントエンドからのリクエスト
{
    "video_id": "uuid",
    "instruments": [
        {
            "id": 0,
            "name": "forceps",
            "selection": {
                "type": "point",  # or "box", "mask"
                "data": [[x, y]]  # 座標データ
            },
            "color": "#00FF00"
        }
    ]
}
```

#### 4.3.2 内部データ構造（新設計）

```python
# SAM2 inference state
{
    "video_path": "frames_dir/",
    "frame_count": 1000,
    "obj_ids": [0, 1, 2],  # 追跡中の器具ID
    "memory_bank": {
        # SAM2内部で管理
        "feature_maps": [...],
        "mask_history": [...]
    }
}

# 追跡結果（Video API出力）
{
    "frame_idx": 100,
    "obj_ids": [0, 1, 2],
    "mask_logits": [
        np.ndarray,  # obj_id=0のマスク
        np.ndarray,  # obj_id=1のマスク
        np.ndarray   # obj_id=2のマスク
    ]
}
```

#### 4.3.3 出力データ（変更なし）

```python
# フロントエンドへのレスポンス（互換性維持）
{
    "analysis_id": "uuid",
    "status": "completed",
    "results": {
        "instrument_data": [
            {
                "instrument_id": 0,
                "name": "forceps",
                "trajectory": [
                    {
                        "frame_index": 0,
                        "center": [x, y],
                        "bbox": [x1, y1, x2, y2],
                        "confidence": 0.95
                    },
                    ...
                ]
            }
        ],
        "skeleton_data": [...],  # 既存のまま
        "metrics": {...}         # 既存のまま
    }
}
```

---

## 5. 実装詳細

### 5.1 新規ファイル構成

```
backend_experimental/
└── app/
    └── ai_engine/
        └── processors/
            ├── sam2_tracker_video.py        ★ 新規作成
            ├── sam2_tracker.py              (既存、参考用に残す)
            └── skeleton_detector.py         (変更なし)
```

### 5.2 コア実装：SAM2TrackerVideo

#### 5.2.1 クラス設計

```python
"""
backend_experimental/app/ai_engine/processors/sam2_tracker_video.py

SAM2 Video API を活用した器具トラッキング実装
"""

import cv2
import numpy as np
import torch
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

from sam2.build_sam import build_sam2_video_predictor

logger = logging.getLogger(__name__)


class SAM2TrackerVideo:
    """
    SAM2 Video API を使った器具トラッキング

    特徴:
    - ビデオ全体の時間的コンテキストを考慮
    - Memory Bankでオクルージョン耐性
    - 一貫したオブジェクトID
    - 複数器具の同時追跡
    """

    def __init__(
        self,
        model_type: str = "small",
        checkpoint_path: Optional[str] = None,
        device: str = "cpu"
    ):
        """
        初期化

        Args:
            model_type: "tiny", "small", "base_plus", "large"
            checkpoint_path: モデルファイルパス
            device: "cpu" or "cuda"
        """
        self.model_type = model_type
        self.device = device
        self.predictor = None
        self.inference_state = None

        # GPU検出
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, using CPU")
            self.device = "cpu"

        # モデルロード
        self._load_model(checkpoint_path)

    def _load_model(self, checkpoint_path: Optional[str]):
        """SAM2 Video Predictor をロード"""
        if checkpoint_path is None:
            # デフォルトパス
            model_files = {
                "tiny": "sam2.1_hiera_tiny.pt",
                "small": "sam2.1_hiera_small.pt",
                "base_plus": "sam2.1_hiera_base_plus.pt",
                "large": "sam2.1_hiera_large.pt"
            }
            checkpoint_path = Path(model_files[self.model_type])
            if not checkpoint_path.exists():
                checkpoint_path = Path("backend") / checkpoint_path

        config_files = {
            "tiny": "configs/sam2.1/sam2.1_hiera_t.yaml",
            "small": "configs/sam2.1/sam2.1_hiera_s.yaml",
            "base_plus": "configs/sam2.1/sam2.1_hiera_b+.yaml",
            "large": "configs/sam2.1/sam2.1_hiera_l.yaml"
        }
        config_path = config_files[self.model_type]

        logger.info(f"Loading SAM2 Video Predictor: {self.model_type}")

        self.predictor = build_sam2_video_predictor(
            config_path,
            str(checkpoint_path),
            device=self.device
        )

        logger.info("SAM2 Video Predictor loaded successfully")

    async def track_video(
        self,
        frames: List[np.ndarray],
        instruments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ビデオ全体で器具を追跡

        Args:
            frames: フレームリスト
            instruments: 器具情報
                [
                    {
                        "id": 0,
                        "name": "forceps",
                        "selection": {
                            "type": "point" | "box" | "mask",
                            "data": [...coordinates...]
                        }
                    }
                ]

        Returns:
            追跡結果
                {
                    "instruments": [
                        {
                            "instrument_id": 0,
                            "name": "forceps",
                            "trajectory": [
                                {
                                    "frame_index": 0,
                                    "center": [x, y],
                                    "bbox": [x1, y1, x2, y2],
                                    "confidence": 0.95,
                                    "mask": np.ndarray
                                },
                                ...
                            ]
                        }
                    ]
                }
        """
        logger.info(f"Starting video tracking: {len(frames)} frames, {len(instruments)} instruments")

        # 1. Inference state初期化
        self._initialize_state(frames)

        # 2. 初期フレーム（Frame 0）で器具を登録
        self._register_instruments(instruments)

        # 3. 全フレームに追跡を伝播
        video_segments = self._propagate_tracking()

        # 4. 軌跡データを抽出
        trajectories = self._extract_trajectories(video_segments, instruments)

        logger.info("Video tracking completed")

        return {"instruments": trajectories}

    def _initialize_state(self, frames: List[np.ndarray]):
        """Inference stateを初期化"""
        logger.info("Initializing inference state...")

        with torch.inference_mode():
            # フレームリストからstateを作成
            # SAM2はフレームディレクトリまたはフレームリストを受け入れる
            self.inference_state = self.predictor.init_state(
                video_path=frames,
                async_loading_frames=False
            )

        logger.info(f"Inference state initialized with {len(frames)} frames")

    def _register_instruments(self, instruments: List[Dict[str, Any]]):
        """初期フレームで器具を登録"""
        logger.info(f"Registering {len(instruments)} instruments...")

        with torch.inference_mode():
            for inst in instruments:
                obj_id = inst["id"]
                selection = inst.get("selection", {})
                sel_type = selection.get("type")
                sel_data = selection.get("data")

                if sel_type == "point":
                    # ポイントプロンプト
                    points = np.array(sel_data, dtype=np.float32)
                    labels = np.ones(len(points), dtype=np.int32)

                    self.predictor.add_new_points_or_box(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        points=points,
                        labels=labels
                    )
                    logger.info(f"Registered instrument {obj_id} with {len(points)} points")

                elif sel_type == "box":
                    # ボックスプロンプト
                    box = np.array(sel_data, dtype=np.float32)

                    self.predictor.add_new_points_or_box(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        box=box
                    )
                    logger.info(f"Registered instrument {obj_id} with box")

                elif sel_type == "mask":
                    # マスクプロンプト（最も正確）
                    mask = np.array(sel_data, dtype=np.uint8)

                    self.predictor.add_new_mask(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        mask=mask
                    )
                    logger.info(f"Registered instrument {obj_id} with mask")

                else:
                    logger.warning(f"Unknown selection type: {sel_type}")

        logger.info("All instruments registered")

    def _propagate_tracking(self) -> Dict[int, Dict[int, np.ndarray]]:
        """全フレームに追跡を伝播"""
        logger.info("Propagating tracking across video...")

        video_segments = {}
        frame_count = 0

        with torch.inference_mode():
            # SAM2が全フレームを自動追跡
            for out_frame_idx, out_obj_ids, out_mask_logits in \
                    self.predictor.propagate_in_video(self.inference_state):

                # マスクをバイナリ化
                masks = {
                    obj_id: (out_mask_logits[i] > 0.0).cpu().numpy()
                    for i, obj_id in enumerate(out_obj_ids)
                }

                video_segments[out_frame_idx] = masks
                frame_count += 1

                # 進捗ログ（100フレームごと）
                if frame_count % 100 == 0:
                    logger.info(f"Processed {frame_count} frames")

        logger.info(f"Tracking propagated to {frame_count} frames")
        return video_segments

    def _extract_trajectories(
        self,
        video_segments: Dict[int, Dict[int, np.ndarray]],
        instruments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """軌跡データを抽出"""
        logger.info("Extracting trajectories...")

        trajectories = []

        for inst in instruments:
            obj_id = inst["id"]
            trajectory = []

            for frame_idx in sorted(video_segments.keys()):
                masks = video_segments[frame_idx]

                if obj_id not in masks:
                    # この器具が検出されなかったフレーム
                    continue

                mask = masks[obj_id]

                # マスクから情報を抽出
                if mask.sum() == 0:
                    # 空のマスク
                    continue

                # 重心計算
                y_coords, x_coords = np.where(mask)
                center_x = float(np.mean(x_coords))
                center_y = float(np.mean(y_coords))

                # バウンディングボックス
                x_min, x_max = float(x_coords.min()), float(x_coords.max())
                y_min, y_max = float(y_coords.min()), float(y_coords.max())

                # 信頼度（マスクの面積から推定）
                area = mask.sum()
                confidence = min(1.0, area / (mask.shape[0] * mask.shape[1]))

                trajectory.append({
                    "frame_index": int(frame_idx),
                    "center": [center_x, center_y],
                    "bbox": [x_min, y_min, x_max, y_max],
                    "confidence": float(confidence),
                    "mask": mask  # 必要に応じて保存
                })

            trajectories.append({
                "instrument_id": obj_id,
                "name": inst.get("name", f"instrument_{obj_id}"),
                "trajectory": trajectory
            })

            logger.info(f"Extracted trajectory for {inst['name']}: {len(trajectory)} frames")

        return trajectories
```

### 5.3 統合：AnalysisServiceV2の修正

```python
# backend_experimental/app/services/analysis_service_v2.py

from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo

class AnalysisServiceV2:

    async def _run_detection(
        self,
        frames: List[np.ndarray],
        video_type: str,
        video_id: str,
        instruments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """検出処理（器具追跡を新実装に変更）"""

        detection_results = {
            "skeleton_data": [],
            "instrument_data": []
        }

        # 1. 骨格検出（既存のまま）
        if video_type in ["external", "external_no_instruments", "external_with_instruments"]:
            detector = HandSkeletonDetector(...)
            for frame in frames:
                result = detector.detect_from_frame(frame)
                detection_results["skeleton_data"].append(result)

        # 2. 器具追跡（新実装）★
        if video_type in ["internal", "external_with_instruments"] and instruments:
            logger.info("[EXPERIMENTAL] Using SAM2 Video API for instrument tracking")

            # SAM2 Video Tracker初期化
            tracker = SAM2TrackerVideo(
                model_type="small",  # or from config
                device="cpu"         # or "cuda" if available
            )

            # ビデオ全体を追跡
            tracking_result = await tracker.track_video(frames, instruments)

            detection_results["instrument_data"] = tracking_result["instruments"]

            logger.info(f"Tracked {len(tracking_result['instruments'])} instruments")

        return detection_results
```

---

## 6. テスト計画

### 6.1 ユニットテスト

```python
# backend_experimental/tests/test_sam2_tracker_video.py

import pytest
import numpy as np
from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo


class TestSAM2TrackerVideo:

    @pytest.fixture
    def tracker(self):
        return SAM2TrackerVideo(model_type="tiny", device="cpu")

    @pytest.fixture
    def sample_frames(self):
        # 10フレームのダミーデータ
        return [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(10)]

    @pytest.fixture
    def sample_instruments(self):
        return [
            {
                "id": 0,
                "name": "forceps",
                "selection": {
                    "type": "point",
                    "data": [[320, 240]]  # 中央付近
                }
            }
        ]

    @pytest.mark.asyncio
    async def test_initialization(self, tracker):
        """初期化が正常に完了するか"""
        assert tracker.predictor is not None
        assert tracker.model_type == "tiny"

    @pytest.mark.asyncio
    async def test_track_video(self, tracker, sample_frames, sample_instruments):
        """ビデオ追跡が動作するか"""
        result = await tracker.track_video(sample_frames, sample_instruments)

        assert "instruments" in result
        assert len(result["instruments"]) == 1
        assert result["instruments"][0]["instrument_id"] == 0
        assert len(result["instruments"][0]["trajectory"]) > 0

    @pytest.mark.asyncio
    async def test_trajectory_format(self, tracker, sample_frames, sample_instruments):
        """軌跡データが正しい形式か"""
        result = await tracker.track_video(sample_frames, sample_instruments)

        trajectory = result["instruments"][0]["trajectory"]
        first_point = trajectory[0]

        assert "frame_index" in first_point
        assert "center" in first_point
        assert "bbox" in first_point
        assert "confidence" in first_point
        assert isinstance(first_point["center"], list)
        assert len(first_point["center"]) == 2
        assert 0.0 <= first_point["confidence"] <= 1.0
```

### 6.2 統合テスト

```python
# backend_experimental/tests/test_analysis_integration.py

import pytest
from app.services.analysis_service_v2 import AnalysisServiceV2
from app.models import SessionLocal, Video, AnalysisResult


@pytest.mark.asyncio
async def test_full_analysis_with_sam2_video():
    """実際の動画で完全な解析フローをテスト"""

    # テスト動画をアップロード
    service = AnalysisServiceV2()

    # 解析実行
    result = await service.analyze_video(
        video_id="test_video_id",
        analysis_id="test_analysis_id",
        instruments=[
            {
                "id": 0,
                "name": "test_instrument",
                "selection": {
                    "type": "point",
                    "data": [[100, 100]]
                }
            }
        ]
    )

    # 結果検証
    assert result["status"] == "success"
    assert "detection_results" in result
    assert "instrument_data" in result["detection_results"]

    # 軌跡が生成されているか
    instruments = result["detection_results"]["instrument_data"]
    assert len(instruments) > 0
    assert len(instruments[0]["trajectory"]) > 0
```

### 6.3 パフォーマンステスト

```python
# scripts/benchmark_sam2_video.py

import time
import numpy as np
from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo


async def benchmark():
    """パフォーマンス測定"""

    # テストデータ
    frames = [np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(100)]
    instruments = [{"id": 0, "name": "test", "selection": {"type": "point", "data": [[640, 360]]}}]

    tracker = SAM2TrackerVideo(model_type="small", device="cpu")

    # 測定開始
    start = time.time()
    result = await tracker.track_video(frames, instruments)
    elapsed = time.time() - start

    print(f"Processing time: {elapsed:.2f}s")
    print(f"Frames per second: {len(frames) / elapsed:.2f}")
    print(f"Trajectory points: {len(result['instruments'][0]['trajectory'])}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(benchmark())
```

---

## 7. 成功判定基準

### 7.1 定量的指標

| 指標 | 目標値 | 測定方法 |
|-----|--------|----------|
| **トラッキング精度** | > 85% | 手動アノテーションとの一致率 |
| **ID安定性** | > 95% | 同一器具が同一IDで追跡される割合 |
| **オクルージョン復帰** | > 80% | 遮蔽後の再検出成功率 |
| **処理時間** | < 2倍 | 安定版との比較 |
| **メモリ使用量** | < 1.5倍 | 安定版との比較 |

### 7.2 定性的評価

```markdown
## 評価チェックリスト

### 精度
- [ ] 器具が正しく追跡されている
- [ ] 遮蔽後も追跡が継続している
- [ ] IDが途中で変わらない
- [ ] 軌跡が滑らかである

### 安定性
- [ ] エラーが発生しない
- [ ] 全フレームで処理が完了する
- [ ] メモリエラーが発生しない

### ユーザー体験
- [ ] 処理時間が許容範囲内
- [ ] 結果の可視化が正常
- [ ] フロントエンドで問題なく表示
```

### 7.3 比較テスト

```bash
# 同じ動画で両バージョンをテスト

# 安定版
curl -X POST http://localhost:8000/api/v1/analysis/{video_id}/analyze

# 実験版
curl -X POST http://localhost:8001/api/v1/analysis/{video_id}/analyze

# 結果を比較
python scripts/compare_versions.py --stable-id xxx --experimental-id yyy
```

---

## 8. ロールバック計画

### 8.1 即座の切り戻し（10秒以内）

```bash
# フロントエンドの接続先を安定版に戻す
cd frontend
copy /Y .env.local.stable .env.local

# ブラウザをリロード
```

### 8.2 問題発生時の対応フロー

```
1. 問題検知
   ├─ エラーログ確認
   ├─ メモリ使用量確認
   └─ 処理時間確認

2. 緊急度判定
   ├─ [高] システムダウン → 即座に切り戻し
   ├─ [中] 精度低下 → データ収集後に判断
   └─ [低] 処理時間増 → 許容範囲内か確認

3. 切り戻し実行
   ├─ フロントエンド設定変更
   ├─ 安定版への接続確認
   └─ ユーザーへの通知

4. 原因調査
   ├─ ログ分析
   ├─ デバッグ実行
   └─ 修正計画立案
```

### 8.3 データ保全

```python
# 実験版で生成したデータは別DBに保存
# aimotion_experimental.db

# 安定版に戻しても既存データは影響なし
# aimotion.db（安定版のデータ）
```

---

## 9. 実装スケジュール

### フェーズ1: 環境構築（1日）

- [ ] backend_experimental/ ディレクトリ作成
- [ ] 設定ファイル修正（ポート、DB）
- [ ] 起動スクリプト作成
- [ ] フロントエンド切り替えツール作成

### フェーズ2: コア実装（2-3日）

- [ ] SAM2TrackerVideo実装
  - [ ] 初期化処理
  - [ ] inference state作成
  - [ ] 器具登録
  - [ ] 伝播処理
  - [ ] 軌跡抽出
- [ ] AnalysisServiceV2統合
- [ ] ユニットテスト作成

### フェーズ3: テスト（1-2日）

- [ ] ユニットテスト実行
- [ ] 統合テスト実行
- [ ] パフォーマンステスト
- [ ] 実際の手術動画でテスト

### フェーズ4: 評価（1日）

- [ ] 精度測定
- [ ] 処理時間測定
- [ ] メモリ使用量測定
- [ ] 成功判定基準との照合

### フェーズ5: 本番投入判断（1日）

- [ ] 評価結果のレビュー
- [ ] Go/No-Go判断
- [ ] 本番投入 or ロールバック

**合計: 5-8日**

---

## 10. リスク管理

### 10.1 技術的リスク

| リスク | 影響度 | 発生確率 | 対策 |
|-------|--------|---------|------|
| SAM2ライブラリの互換性問題 | 高 | 低 | 事前にバージョン確認、フォールバック実装 |
| メモリ不足 | 高 | 中 | フレーム数制限、バッチ処理 |
| 処理時間超過 | 中 | 中 | タイムアウト設定、非同期処理 |
| GPU/CPU性能差 | 中 | 低 | デバイス自動検出、最適化 |

### 10.2 運用リスク

| リスク | 影響度 | 発生確率 | 対策 |
|-------|--------|---------|------|
| 安定版への切り戻し失敗 | 高 | 極低 | 手順書整備、定期的な切り戻しテスト |
| データ不整合 | 中 | 低 | 別DBで管理、バックアップ |
| ユーザー混乱 | 低 | 中 | 環境バッジ表示、ドキュメント整備 |

---

## 11. 付録

### 11.1 参考資料

- [SAM2 公式リポジトリ](https://github.com/facebookresearch/sam2)
- [SAM2 論文](https://ai.meta.com/research/publications/sam-2-segment-anything-in-images-and-videos/)
- sam2_tracer実装（参考コード）

### 11.2 用語集

| 用語 | 説明 |
|-----|------|
| **Video API** | SAM2のビデオ追跡用API（`build_sam2_video_predictor`） |
| **inference state** | ビデオ全体のコンテキストを保持する状態オブジェクト |
| **Memory Bank** | 過去フレームのマスク情報を保持する機構 |
| **Propagation** | 初期マスクを全フレームに伝播させる処理 |
| **オクルージョン** | 器具が手などで一時的に隠れる現象 |

---

**更新履歴:**
- 2025-10-11: 初版作成
