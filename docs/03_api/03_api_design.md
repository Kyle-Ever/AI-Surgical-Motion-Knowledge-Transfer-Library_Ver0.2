# API設計書 - AI Surgical Motion Knowledge Transfer Library

## 目次
1. [設計原則](#設計原則)
2. [エンドポイント命名規則](#エンドポイント命名規則)
3. [リクエスト/レスポンス形式](#リクエストレスポンス形式)
4. [エラーハンドリング](#エラーハンドリング)
5. [API一覧](#api一覧)
6. [WebSocket API](#websocket-api)
7. [認証・認可](#認証認可)

## 設計原則

### RESTful API設計の原則
1. **リソース中心**: URLはリソースを表現、HTTPメソッドで操作を表現
2. **ステートレス**: 各リクエストは独立して処理可能
3. **統一インターフェース**: 一貫した命名規則とレスポンス形式
4. **階層的キャッシング**: 適切なHTTPキャッシュヘッダーの使用

## エンドポイント命名規則

### URL構造
```
/api/v{version}/{resource}/{id?}/{action?}
```

### 命名規則
- **リソース名**: 複数形の名詞 (`/videos`, `/analyses`)
- **kebab-case**: 複数単語の場合 (`/instrument-tracking`)
- **階層表現**: 親子関係 (`/videos/{id}/analyses`)
- **動詞の使用**: 特殊操作のみ (`/videos/{id}/analyze`)

### HTTPメソッドの使い分け
| メソッド | 用途 | 例 |
|---------|------|-----|
| GET | リソース取得 | `GET /api/v1/videos` |
| POST | リソース作成/アクション実行 | `POST /api/v1/videos/upload` |
| PUT | リソース全体更新 | `PUT /api/v1/videos/{id}` |
| PATCH | リソース部分更新 | `PATCH /api/v1/videos/{id}` |
| DELETE | リソース削除 | `DELETE /api/v1/videos/{id}` |

## リクエスト/レスポンス形式

### 成功レスポンスの統一形式
```json
{
  "success": true,
  "data": {
    // リソースデータ
  },
  "meta": {
    "timestamp": "2024-09-27T10:00:00Z",
    "version": "1.0"
  }
}
```

### ページネーションレスポンス
```json
{
  "success": true,
  "data": [...],
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 20,
    "total_pages": 5
  }
}
```

### エラーレスポンスの統一形式
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーの説明",
    "details": {
      // 詳細情報（オプション）
    }
  },
  "meta": {
    "timestamp": "2024-09-27T10:00:00Z",
    "request_id": "uuid-here"
  }
}
```

## エラーハンドリング

### HTTPステータスコード
| コード | 意味 | 使用場面 |
|--------|------|----------|
| 200 | OK | 正常なGET、PUT、PATCH |
| 201 | Created | リソース作成成功（POST） |
| 204 | No Content | 削除成功（DELETE） |
| 400 | Bad Request | バリデーションエラー |
| 401 | Unauthorized | 認証が必要 |
| 403 | Forbidden | 権限不足 |
| 404 | Not Found | リソースが存在しない |
| 409 | Conflict | リソースの競合 |
| 413 | Payload Too Large | ファイルサイズ超過 |
| 422 | Unprocessable Entity | ビジネスロジックエラー |
| 500 | Internal Server Error | サーバーエラー |
| 503 | Service Unavailable | サービス一時停止 |

### エラーコード体系
```
{カテゴリ}_{詳細}_{タイプ}

例:
- VIDEO_NOT_FOUND
- VIDEO_UPLOAD_SIZE_EXCEEDED
- ANALYSIS_ALREADY_IN_PROGRESS
- AUTH_TOKEN_EXPIRED
```

## API一覧

### 1. Videos API

#### 動画一覧取得
```http
GET /api/v1/videos
```
**Query Parameters:**
- `page`: ページ番号（デフォルト: 1）
- `per_page`: 1ページあたりの件数（デフォルト: 20）
- `status`: フィルタリング（pending/processing/completed/failed）
- `sort`: ソート順（created_at/-created_at）

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "filename": "video_123.mp4",
      "original_filename": "surgery_demo.mp4",
      "file_size": 1048576,
      "duration": 300,
      "fps": 30,
      "width": 1920,
      "height": 1080,
      "status": "completed",
      "created_at": "2024-09-27T10:00:00Z",
      "updated_at": "2024-09-27T10:05:00Z"
    }
  ],
  "meta": {
    "total": 50,
    "page": 1,
    "per_page": 20,
    "total_pages": 3
  }
}
```

#### 動画アップロード
```http
POST /api/v1/videos/upload
Content-Type: multipart/form-data
```
**Request Body:**
- `file`: 動画ファイル（必須、最大2GB、.mp4のみ）

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "video_id": 123,
    "filename": "video_123.mp4",
    "status": "pending",
    "message": "動画のアップロードが完了しました"
  }
}
```

#### 動画詳細取得
```http
GET /api/v1/videos/{video_id}
```

#### 動画削除
```http
DELETE /api/v1/videos/{video_id}
```

### 2. Analysis API

#### 分析開始
```http
POST /api/v1/analysis/{video_id}/analyze
```
**Request Body:**
```json
{
  "detection_type": "external",  // external/internal/hybrid
  "analysis_type": "full"  // full/quick
}
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "analysis_id": 456,
    "video_id": 123,
    "status": "started",
    "websocket_url": "ws://localhost:8000/ws/analysis/456"
  }
}
```

#### 分析ステータス取得
```http
GET /api/v1/analysis/{analysis_id}/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "analysis_id": 456,
    "status": "processing",
    "progress": 65,
    "current_step": "skeleton_detection",
    "estimated_time_remaining": 30
  }
}
```

#### 分析結果取得
```http
GET /api/v1/analysis/{analysis_id}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "analysis_id": 456,
    "video_id": 123,
    "detection_type": "external",
    "status": "completed",
    "metrics_data": {
      "speed": 85.5,
      "smoothness": 92.3,
      "stability": 88.7,
      "efficiency": 90.2
    },
    "feedback": {
      "strengths": ["良い手の位置", "スムーズな動き"],
      "weaknesses": ["速度が少し遅い"],
      "suggestions": ["手首の角度を改善"]
    }
  }
}
```

### 3. Scoring API

#### 比較分析実行
```http
POST /api/v1/scoring/compare
```
**Request Body:**
```json
{
  "learner_video_id": 123,
  "reference_video_id": 456
}
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "comparison_id": 789,
    "status": "processing"
  }
}
```

#### 比較結果取得
```http
GET /api/v1/scoring/comparison/{comparison_id}
```

### 4. Library API

#### リファレンス動画一覧
```http
GET /api/v1/library/references
```
**Query Parameters:**
- `category`: カテゴリでフィルタ
- `level`: レベルでフィルタ（beginner/intermediate/expert）

### 5. Instrument Tracking API

#### 器具追跡開始
```http
POST /api/v1/instrument-tracking/{video_id}/track
```
**Request Body:**
```json
{
  "instruments": ["forceps", "scissors", "needle_holder"],
  "tracking_mode": "real_time"  // real_time/batch
}
```

## WebSocket API

### 分析進捗の監視
```
ws://localhost:8000/ws/analysis/{analysis_id}
```

#### 接続
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/analysis/456');
```

#### メッセージ形式
```json
// サーバーから送信されるメッセージ
{
  "type": "progress",  // progress/status/completed/error
  "data": {
    "step": "skeleton_detection",
    "progress": 50,
    "message": "骨格検出を実行中..."
  }
}
```

#### イベントタイプ
| タイプ | 説明 | データ |
|--------|------|--------|
| connection | 接続成功 | `{message: "Connected"}` |
| progress | 進捗更新 | `{step, progress, message}` |
| status | ステータス変更 | `{status, message}` |
| completed | 分析完了 | `{analysis_id, results}` |
| error | エラー発生 | `{error_code, message}` |

## 認証・認可

### 現在の状態
- **認証なし**（プロトタイプ版）

### 将来の実装計画
```yaml
認証方式:
  タイプ: "JWT (JSON Web Token)"
  発行者: "OAuth2.0プロバイダー"

ヘッダー形式:
  Authorization: "Bearer {token}"

トークン構造:
  header:
    alg: "HS256"
    typ: "JWT"
  payload:
    user_id: 123
    email: "user@example.com"
    roles: ["user", "admin"]
    exp: 1234567890

エンドポイント保護:
  公開:
    - GET /api/v1/health
    - POST /api/v1/auth/login
  認証必須:
    - すべての動画操作
    - 分析実行
    - 比較実行
```

## レート制限

### 現在の設定
```yaml
グローバル:
  なし（プロトタイプ版）

将来の実装:
  通常ユーザー:
    - 100リクエスト/分
    - 10動画アップロード/日
    - 50分析実行/日

  プレミアムユーザー:
    - 500リクエスト/分
    - 100動画アップロード/日
    - 無制限の分析実行
```

## CORSポリシー

### 開発環境
```python
allow_origins = ["*"]  # すべて許可
allow_methods = ["*"]
allow_headers = ["*"]
```

### 本番環境
```python
allow_origins = [
    "https://example.com",
    "https://app.example.com"
]
allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allow_headers = ["Content-Type", "Authorization"]
allow_credentials = True
```

## バージョニング

### URL形式
```
/api/v1/...  # 現在
/api/v2/...  # 将来
```

### 廃止ポリシー
1. 新バージョンリリース
2. 6ヶ月の移行期間
3. 廃止3ヶ月前に通知
4. 旧バージョン廃止

### バージョン間の互換性
- 後方互換性を可能な限り維持
- Breaking changeは新バージョンで実装
- Deprecation warningをレスポンスヘッダーに含める

---
*最終更新: 2024年9月27日*
*このドキュメントはClaude Codeとの協働開発を前提に作成されています*