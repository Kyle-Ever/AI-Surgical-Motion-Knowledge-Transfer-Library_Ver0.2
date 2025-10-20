# AI手技モーションライブラリ 基本設計書

## 1. システム構成

### 1.1 アーキテクチャ概要

```
┌──────────────────────────────────────────────────────────┐
│                     クライアント層                           │
│                   React (Next.js)                          │
│                    Tailwind CSS                            │
└────────────────────────┬─────────────────────────────────┘
                         │ REST API (JSON)
                         │ WebSocket (進捗通知)
┌────────────────────────┴─────────────────────────────────┐
│                      API層                                 │
│                  FastAPI (Python)                          │
│                    Pydantic                                │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────────┐
│                   ビジネスロジック層                        │
│         ┌──────────────┐  ┌──────────────┐            │
│         │  動画処理     │  │  AI処理      │            │
│         │  (OpenCV)     │  │ (MediaPipe)  │            │
│         └──────────────┘  │  (YOLO)      │            │
│                           └──────────────┘            │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────────┐
│                    データ層                                │
│         ┌──────────────┐  ┌──────────────┐            │
│         │  PostgreSQL   │  │ ファイル     │            │
│         │  (メタデータ) │  │ ストレージ   │            │
│         └──────────────┘  └──────────────┘            │
└──────────────────────────────────────────────────────────┘
```

### 1.2 技術スタック

| レイヤー | 技術 | 用途 |
|---------|------|------|
| フロントエンド | React 18 + Next.js 14 | UIフレームワーク |
| | Tailwind CSS | スタイリング |
| | Chart.js | グラフ描画 |
| | Axios | HTTP通信 |
| バックエンド | FastAPI | WebAPIフレームワーク |
| | Uvicorn | ASGIサーバー |
| | Pydantic | データバリデーション |
| | python-multipart | ファイルアップロード |
| AI/ML | MediaPipe | 骨格検出 |
| | YOLOv8 | 物体検出 |
| | OpenCV | 動画処理 |
| | NumPy/Pandas | データ処理 |
| データベース | PostgreSQL | 本番環境 |
| | SQLite | 開発環境 |
| | SQLAlchemy | ORM |

## 2. データベース設計

### 2.1 ER図

```mermaid
erDiagram
    videos ||--o{ analysis_results : has
    videos ||--o{ instruments : has
    technique_library ||--|| analysis_results : references
    comparison_results }o--|| technique_library : uses
    comparison_results }o--|| analysis_results : compares

    videos {
        uuid id PK
        string filename
        string original_filename
        string video_type
        string surgery_name
        date surgery_date
        string surgeon_name
        text memo
        datetime created_at
        datetime updated_at
    }

    analysis_results {
        uuid id PK
        uuid video_id FK
        json coordinate_data
        json velocity_data
        json angle_data
        float avg_velocity
        float total_distance
        integer total_frames
        string status
        datetime created_at
    }

    instruments {
        uuid id PK
        uuid video_id FK
        string name
        json annotation_data
        json model_data
        datetime created_at
    }

    technique_library {
        uuid id PK
        uuid analysis_result_id FK
        string technique_name
        string category
        text description
        boolean is_reference
        datetime created_at
    }

    comparison_results {
        uuid id PK
        uuid library_id FK
        uuid student_analysis_id FK
        float score
        json comparison_data
        text ai_feedback
        datetime created_at
    }
```

### 2.2 テーブル定義

#### videos（動画情報）
| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| id | UUID | PK | 主キー |
| filename | VARCHAR(255) | NOT NULL | システム内ファイル名 |
| original_filename | VARCHAR(255) | NOT NULL | 元のファイル名 |
| video_type | VARCHAR(50) | NOT NULL | internal/external |
| surgery_name | VARCHAR(255) | | 手術名 |
| surgery_date | DATE | | 手術日 |
| surgeon_name | VARCHAR(255) | | 執刀医名 |
| memo | TEXT | | メモ |
| created_at | TIMESTAMP | NOT NULL | 作成日時 |
| updated_at | TIMESTAMP | NOT NULL | 更新日時 |

#### analysis_results（解析結果）
| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| id | UUID | PK | 主キー |
| video_id | UUID | FK | 動画ID |
| coordinate_data | JSON | | 座標データ |
| velocity_data | JSON | | 速度データ |
| angle_data | JSON | | 角度データ |
| avg_velocity | FLOAT | | 平均速度 |
| total_distance | FLOAT | | 総移動距離 |
| total_frames | INTEGER | | 総フレーム数 |
| status | VARCHAR(50) | NOT NULL | processing/completed/failed |
| created_at | TIMESTAMP | NOT NULL | 作成日時 |

## 3. API設計

### 3.1 エンドポイント一覧

| メソッド | パス | 説明 | 優先度 |
|---------|------|------|--------|
| POST | /api/videos/upload | 動画アップロード | 高 |
| POST | /api/videos/{id}/analyze | 解析開始 | 高 |
| GET | /api/videos/{id}/status | 解析状況確認 | 高 |
| GET | /api/analysis/{id} | 解析結果取得 | 高 |
| GET | /api/analysis/{id}/export | データエクスポート | 高 |
| POST | /api/library | ライブラリ登録 | 中 |
| GET | /api/library | ライブラリ一覧 | 中 |
| POST | /api/comparison | 比較実行 | 低 |
| GET | /api/comparison/{id} | 比較結果取得 | 低 |

### 3.2 API仕様詳細

#### POST /api/videos/upload
**リクエスト**
```json
Content-Type: multipart/form-data

{
  "file": <binary>,
  "video_type": "internal|external",
  "surgery_name": "腹腔鏡手術",
  "surgery_date": "2025-01-04",
  "surgeon_name": "山田医師",
  "memo": "練習用"
}
```

**レスポンス**
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "video_20250104_123456.mp4",
  "message": "Upload successful"
}
```

#### POST /api/videos/{id}/analyze
**リクエスト**
```json
{
  "instruments": [
    {
      "frame_number": 100,
      "bbox": {
        "x": 100,
        "y": 200,
        "width": 50,
        "height": 30
      }
    }
  ],
  "sampling_rate": 5
}
```

**レスポンス**
```json
{
  "analysis_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "processing",
  "estimated_time": 600
}
```

#### WebSocket /ws/analysis/{analysis_id}
**進捗通知メッセージ**
```json
{
  "type": "progress",
  "step": "skeleton_detection",
  "progress": 45,
  "message": "骨格検出処理中..."
}
```

## 4. ディレクトリ構造

```
ai-motion-library/
├── frontend/                    # フロントエンド
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   ├── components/         # Reactコンポーネント
│   │   ├── hooks/             # カスタムフック
│   │   ├── lib/               # ユーティリティ
│   │   └── styles/            # スタイルシート
│   ├── public/                # 静的ファイル
│   └── package.json
│
├── backend/                    # バックエンド
│   ├── app/
│   │   ├── api/               # APIエンドポイント
│   │   │   ├── routers/       # ルーター定義
│   │   │   └── dependencies/  # 依存性注入
│   │   ├── core/              # コア機能
│   │   │   ├── config.py      # 設定
│   │   │   └── security.py    # セキュリティ
│   │   ├── models/            # データモデル
│   │   ├── schemas/           # Pydanticスキーマ
│   │   ├── services/          # ビジネスロジック
│   │   └── utils/             # ユーティリティ
│   ├── main.py               # エントリーポイント
│   └── requirements.txt
│
├── ai_engine/                 # AI処理エンジン
│   ├── processors/
│   │   ├── video_processor.py    # 動画処理
│   │   ├── skeleton_detector.py  # 骨格検出
│   │   └── instrument_detector.py # 器具検出
│   ├── models/               # AIモデル
│   │   ├── yolov8n.pt       # YOLO重み
│   │   └── mediapipe/       # MediaPipeモデル
│   └── utils/
│
├── database/                  # データベース
│   ├── migrations/           # マイグレーション
│   └── seeds/               # シードデータ
│
├── data/                     # データ保存
│   ├── uploads/             # アップロード動画
│   ├── temp/                # 一時ファイル
│   └── exports/             # エクスポート
│
├── docker-compose.yml        # Docker構成
├── .env.example             # 環境変数例
└── README.md                # プロジェクト説明
```

## 5. 処理フロー

### 5.1 動画解析処理フロー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant B as バックエンド
    participant AI as AI処理エンジン
    participant DB as データベース

    U->>F: 動画アップロード
    F->>B: POST /api/videos/upload
    B->>DB: 動画情報保存
    B-->>F: video_id返却
    
    alt 体内カメラの場合
        F->>U: アノテーション画面表示
        U->>F: 器具をアノテーション
    end
    
    F->>B: POST /api/videos/{id}/analyze
    B->>AI: 解析開始
    B-->>F: analysis_id返却
    
    F->>B: WebSocket接続
    
    loop 解析中
        AI->>B: 進捗更新
        B->>F: 進捗通知
        F->>U: プログレスバー更新
    end
    
    AI->>DB: 解析結果保存
    AI->>B: 解析完了
    B->>F: 完了通知
    F->>B: GET /api/analysis/{id}
    B->>DB: 結果取得
    B-->>F: 解析結果
    F->>U: ダッシュボード表示
```

### 5.2 AI処理パイプライン

```python
# 処理パイプラインの概要
class VideoAnalysisPipeline:
    def process(self, video_path, video_type, instruments=None):
        # 1. 動画読み込み
        video = self.load_video(video_path)
        
        # 2. フレーム抽出（5fps）
        frames = self.extract_frames(video, fps=5)
        
        # 3. 器具検出（必要な場合）
        if video_type == "internal" and instruments:
            instrument_tracker = self.train_instrument_detector(instruments)
            instrument_tracks = self.detect_instruments(frames, instrument_tracker)
        
        # 4. 骨格検出（外部カメラの場合）
        if video_type == "external":
            skeleton_data = self.detect_skeleton(frames)
        
        # 5. データ生成
        analysis_data = self.generate_analysis_data(
            frames, 
            instrument_tracks if video_type == "internal" else None,
            skeleton_data if video_type == "external" else None
        )
        
        # 6. 結果保存
        self.save_results(analysis_data)
        
        return analysis_data
```

## 6. データフォーマット

### 6.1 座標データ形式（JSON）

```json
{
  "frames": [
    {
      "frame_number": 0,
      "timestamp": 0.0,
      "skeleton": {
        "left_hand": {
          "landmarks": [
            {"x": 0.5, "y": 0.3, "z": 0.1, "visibility": 0.99}
          ],
          "angles": {
            "wrist": 45.2,
            "thumb": 30.1
          }
        },
        "right_hand": {
          "landmarks": [...]
        }
      },
      "instruments": [
        {
          "id": "instrument_1",
          "bbox": {"x": 100, "y": 200, "w": 50, "h": 30},
          "center": {"x": 125, "y": 215},
          "confidence": 0.95
        }
      ]
    }
  ],
  "metadata": {
    "total_frames": 1800,
    "fps": 5,
    "duration": 360
  }
}
```

### 6.2 エクスポートCSV形式

```csv
timestamp,left_hand_x,left_hand_y,left_hand_velocity,right_hand_x,right_hand_y,right_hand_velocity,instrument_x,instrument_y,instrument_angle
0.0,0.5,0.3,0.0,0.6,0.4,0.0,125,215,0
0.2,0.51,0.31,5.0,0.61,0.39,5.0,130,218,2
...
```

## 7. エラー処理

### 7.1 エラーコード体系

| コード | 種別 | 説明 |
|--------|------|------|
| 4001 | ValidationError | 入力データ不正 |
| 4002 | FileFormatError | ファイル形式エラー |
| 4003 | FileSizeError | ファイルサイズ超過 |
| 5001 | ProcessingError | 解析処理エラー |
| 5002 | DetectionError | 検出失敗 |
| 5003 | DatabaseError | DB接続エラー |

### 7.2 エラーレスポンス形式

```json
{
  "error": {
    "code": 4002,
    "message": "サポートされていないファイル形式です",
    "detail": "MP4形式のファイルをアップロードしてください",
    "timestamp": "2025-01-04T12:34:56Z"
  }
}
```

## 8. 非機能要件

### 8.1 パフォーマンス要件

| 項目 | 目標値 | 備考 |
|------|--------|------|
| API応答時間 | < 1秒 | 通常のCRUD操作 |
| 動画アップロード | < 30秒 | 100MBファイル |
| 解析処理時間 | < 10分 | 10分動画 |
| 同時接続数 | 10ユーザー | MVP要件 |
| 1日の処理数 | 50動画 | MVP要件 |

### 8.2 セキュリティ要件

- **認証**: MVP段階では実装しない（Phase2でJWT実装予定）
- **通信**: HTTP（開発環境）、HTTPS（本番環境・将来）
- **ファイルアクセス**: 直接URLアクセス可（MVP段階）
- **入力検証**: Pydanticによる型チェック・バリデーション
- **SQLインジェクション対策**: SQLAlchemyのORM使用

### 8.3 ログ設計

```python
# ログ設定
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/app.log',
            'formatter': 'default'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file', 'console']
    }
}
```

## 9. 開発・デプロイ

### 9.1 開発環境セットアップ

```bash
# バックエンド
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload

# フロントエンド
cd frontend
npm install
npm run dev
```

### 9.2 環境変数（.env）

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/aimotion_db
DATABASE_URL_DEV=sqlite:///./dev.db

# API
API_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Storage
UPLOAD_DIR=./data/uploads
TEMP_DIR=./data/temp
MAX_UPLOAD_SIZE=2147483648  # 2GB

# AI Models
YOLO_MODEL_PATH=./ai_engine/models/yolov8n.pt

# OpenAI (Phase2)
OPENAI_API_KEY=your-api-key
```

### 9.3 Docker構成（オプション）

```yaml
# docker-compose.yml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
  
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    depends_on:
      - postgres
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: aimotion_db
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 10. テスト戦略

### 10.1 テスト種別

| 種別 | 対象 | ツール |
|------|------|--------|
| 単体テスト | API、サービス層 | pytest |
| 統合テスト | API全体 | pytest + TestClient |
| E2Eテスト | 画面操作 | Playwright |
| 負荷テスト | API性能 | Locust |

### 10.2 テストデータ

- サンプル動画: 1分、5分、10分の3種類
- テスト用アノテーションデータ
- 期待される解析結果のゴールデンデータ

## 11. 今後の拡張予定

### Phase 2
- ユーザー認証機能（JWT）
- OpenAI API連携
- リアルタイム解析機能
- 複数器具の同時追跡

### Phase 3
- クラウドストレージ（AWS S3）
- マイクロサービス化
- Kubernetes対応
- 多言語対応