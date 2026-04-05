# PDCA Plan: quality-improvement

## 1. 概要

| 項目 | 内容 |
|------|------|
| 機能名 | コード品質最適化 (Phase 2) |
| 作成日 | 2026-04-05 |
| 目標スコア | Backend 75+ / Frontend 70+ (現在: 62 / 52) |
| スコープ | セキュリティ修正、アーキテクチャ改善、型安全性向上、コンポーネント分割 |

## 2. 現状分析サマリー

### リファクタリング Phase 1 の成果
- デッドコード削除（約3920行削減）
- bare except 修正（5/6箇所）
- 型定義・ユーティリティ統合
- God Object 部分分割（1571→1261行）
- console.log 70%削減

### 残存する課題カテゴリ

| カテゴリ | Backend | Frontend | リスク |
|----------|---------|----------|--------|
| **セキュリティ** | エラー情報漏洩、CORS ハードコード | — | 高 |
| **バグ** | bare except 1箇所 | URL二重パスバグ | 高 |
| **アーキテクチャ** | God Object残存、ルーター層汚染 | 巨大コンポーネント4つ | 中 |
| **一貫性** | — | fetch/axios混在、API_BASE_URL未統一 | 中 |
| **型安全性** | Dict[str, Any]多用 | any型80箇所 | 中 |
| **重複** | _get_video_info重複 | 計算ロジック重複、WebSocketフック重複 | 低 |

## 3. 改善計画（6ワークパッケージ）

### WP-1: Critical バグ・セキュリティ修正
**リスク: 低 | インパクト: 高 | 工数: 小**

| # | タスク | ファイル | 詳細 |
|---|--------|---------|------|
| 1.1 | エラーレスポンスの情報漏洩修正 | `app/core/error_handler.py:124` | DEBUG=False時に `exception`, `type` をレスポンスから除外 |
| 1.2 | CORS設定を環境変数化 | `app/main.py:110-118` | ハードコード → `settings.BACKEND_CORS_ORIGINS` を使用 |
| 1.3 | bare except 最後の1箇所修正 | `app/ai_engine/processors/sam_tracker_unified.py:175` | `except Exception:` に変更 |
| 1.4 | URL二重パスバグ修正 | `frontend/app/annotation/page.tsx:222` | `/api/v1/` 二重化を修正 |
| 1.5 | except Exception: pass にログ追加 | `app/api/routes/analysis.py:279,291` | 最低限 `logger.warning()` |

**リスク回避策**: 各修正は1-5行の変更。テスト実行で退行確認。

---

### WP-2: Frontend API呼び出し統一
**リスク: 低 | インパクト: 高 | 工数: 中**

#### 目的
`fetch()` 直書き20箇所 + `process.env.NEXT_PUBLIC_API_URL` ハードコード15箇所を
`lib/api.ts` の `api` インスタンス（axios）経由に統一。

#### 対象ファイルと変更数

| ファイル | fetch箇所 | env直書き | 対応方針 |
|---------|----------|----------|---------|
| `DashboardClient.tsx` | 6 | 6 | `api.get()` に置換 |
| `InstrumentSelector.tsx` | 5 | 5 | `api.post()` に置換 |
| `history/page.tsx` | 3 | 1 | `getCompletedAnalyses()` 等を使用 |
| `library/page.tsx` | 1 | 0 | `api.delete()` に置換 |
| `scoring/page.tsx` | 1 | 1 | `api.get()` に置換 |
| `DualVideoPlayer.tsx` | 2 | 0 | 既にAPI_BASE_URL使用、fetchのみ置換 |
| `annotation/page.tsx` | 3 | 3 | `api.post()` + URL修正 |
| `scoring/comparison/[id]/page.tsx` | 2 | 2 | `api.get()` に置換 |
| その他 | 2-3 | 0 | 個別対応 |

#### 変換パターン
```typescript
// Before:
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
const res = await fetch(`${apiUrl}/videos/${id}`)
const data = await res.json()

// After:
import { api } from '@/lib/api'
const { data } = await api.get(`/videos/${id}`)
```

**リスク回避策**:
- fetch → axios で Response 構造が変わる（`res.json()` → `res.data`）ため、各呼び出しの返り値使用箇所を全て確認
- ファイル単位で変更 → TypeScript ビルドチェック → Playwright テスト のサイクルで進行
- video streaming URL（`<video src=...>`）は fetch 置換不要（ブラウザ直接アクセス）

#### WebSocketフック統合
| 対応 | 詳細 |
|------|------|
| `useApi.ts` 内の `useWebSocket` (139-207行) | 削除 |
| `hooks/useWebSocket.ts` (Heartbeat付き完全版) | 正規版として維持 |
| `AnalysisClient.tsx` のimport先変更 | `useApi` → `useWebSocket` |

---

### WP-3: Backend God Object 追加分割
**リスク: 中 | インパクト: 高 | 工数: 中**

#### 目標
`analysis_service_v2.py` を 1261行 → 約300行 のオーケストレーターに縮小。

#### 分割設計

```
analysis_service_v2.py (1261行)
    │
    ├── detection_pipeline.py (新規 ~400行)
    │   ├── class DetectionStrategy (ABC)
    │   ├── class SkeletonOnlyStrategy    ← EXTERNAL_NO_INSTRUMENTS
    │   ├── class SAM1Strategy            ← USE_SAM2=false
    │   ├── class SAM2Strategy            ← USE_SAM2=true, VIDEO_API=false
    │   └── class SAM2VideoStrategy       ← USE_SAM2=true, VIDEO_API=true
    │
    ├── result_formatter.py (新規 ~200行)
    │   ├── format_skeleton_data()
    │   ├── format_instrument_data()
    │   ├── compress_instrument_data()
    │   └── convert_video_api_result()
    │
    └── analysis_service_v2.py (縮小 ~300行)
        └── class AnalysisServiceV2  ← オーケストレーターのみ
```

#### Strategy パターンの設計

```python
class DetectionStrategy(ABC):
    @abstractmethod
    async def detect(self, frames, video_info, extraction_result) -> DetectionResult:
        ...

class DetectionResult:
    skeleton_data: List[Dict]
    instrument_data: List[Dict]
    tracking_stats: Dict
    warnings: List[str]
```

**VideoType → Strategy マッピング**:
| VideoType | Strategy | 処理内容 |
|-----------|----------|---------|
| EXTERNAL_NO_INSTRUMENTS | SkeletonOnlyStrategy | MediaPipe骨格のみ |
| INTERNAL | SAM2VideoStrategy / SAM2Strategy / SAM1Strategy | YOLOv8 + SAMトラッキング |
| EXTERNAL_WITH_INSTRUMENTS | 同上 | 同上 |
| EYE_GAZE | — (GazeAnalysisService) | 既に分離済み |

#### ステートフル問題の解消

```python
# Before: インスタンス変数に状態を保持（レースコンディション）
class AnalysisServiceV2:
    def __init__(self):
        self.warnings = []
        self.tracking_stats = {}
        self.extraction_result = None

# After: リクエストスコープのコンテキスト
@dataclass
class AnalysisContext:
    warnings: List[str] = field(default_factory=list)
    tracking_stats: Dict = field(default_factory=dict)
    extraction_result: Optional[ExtractionResult] = None
    detectors: Dict = field(default_factory=dict)
```

**リスク回避策**:
1. `result_formatter.py` を先に抽出（純粋関数、リスクゼロ）
2. `detection_pipeline.py` は段階的に:
   - まず1つのStrategyを作り、INTERNAL用SAM2Videoで検証
   - 動作確認後、残りのStrategyを追加
3. 各ステップでバックエンドテスト（68 passed維持）確認
4. オーケストレーターのメソッドはデリゲートパターンで段階移行

---

### WP-4: Frontend コンポーネント分割
**リスク: 中 | インパクト: 中 | 工数: 大**

#### 対象（600行超の4コンポーネント）

| コンポーネント | 行数 | 分割方針 |
|---------------|------|---------|
| `upload/page.tsx` | 611 | 4ステップ → 4サブコンポーネント |
| `DashboardClient.tsx` | 600 | APIロジック抽出 + メトリクス表示分離 |
| `VideoPlayer.tsx` | 673 | 描画ロジック（skeleton/instrument）を utils に分離 |
| `InstrumentSelector.tsx` | 648 | 検出/セグメンテーション/プレビューを3分割 |

#### upload/page.tsx 分割設計

```
upload/page.tsx (611行)
    │
    ├── components/upload/StepVideoType.tsx   ← ステップ1: 動画タイプ選択
    ├── components/upload/StepFileUpload.tsx  ← ステップ2: ファイルアップロード
    ├── components/upload/StepInstruments.tsx ← ステップ3: 器具選択
    ├── components/upload/StepMetadata.tsx    ← ステップ4: メタデータ入力
    └── upload/page.tsx (縮小 ~100行)        ← ステップ管理のみ
```

#### DashboardClient.tsx 分割設計

```
DashboardClient.tsx (600行)
    │
    ├── hooks/useDashboardData.ts        ← API呼び出し + 状態管理
    ├── components/dashboard/MetricsOverview.tsx  ← 6指標表示
    └── DashboardClient.tsx (縮小 ~200行) ← レイアウト + 子コンポーネント配置
```

#### MotionAnalysisPanel 計算ロジック抽出

```typescript
// lib/motion-metrics.ts (新規)
export function calculateVelocityMetrics(positions: Position[]): VelocityResult
export function calculateSmoothnessScore(velocities: number[]): number
export function calculatePathEfficiency(positions: Position[]): number
```

3つの計算関数（`calculateRealtimeMetrics`, `calculateInstrumentRealtimeMetrics`, `calculateWasteRealtimeMetrics`）が80%重複 → 共通関数に統合。

**リスク回避策**:
- コンポーネント分割は props のインターフェースを明確に定義してから分離
- 1コンポーネントずつ分割 → Playwright テストで画面表示確認
- GazeDashboardClient.tsx は **PROTECTED のため絶対に触らない**

---

### WP-5: 型安全性向上
**リスク: 低 | インパクト: 中 | 工数: 中**

#### Frontend: any 型排除（80箇所 → 目標30箇所以下）

**優先度A — useState<any> 15箇所**:
```typescript
// Before:
const [analysisData, setAnalysisData] = useState<any>(null)

// After:
import type { AnalysisResult } from '@/types/analysis'
const [analysisData, setAnalysisData] = useState<AnalysisResult | null>(null)
```

| ファイル | any useState 数 | 対応 |
|---------|----------------|------|
| `DashboardClient.tsx` | 5 | AnalysisResult, VideoInfo, SixMetrics 型適用 |
| `upload/page.tsx` | 3 | Video, UploadState 型定義 |
| `library/page.tsx` | 2 | LibraryItem 型定義 |
| `scoring/page.tsx` | 2 | ComparisonResult 型適用 |
| その他 | 3 | 個別対応 |

**優先度B — types/analysis.ts の `| any` 除去**:
```typescript
// Before:
skeleton_data?: SkeletonData[] | any

// After:
skeleton_data?: SkeletonData[]
```

**優先度C — 関数パラメータの any**:
- `(item: any)` → 具体的な型
- `catch(err: any)` → `catch(err: unknown)` + 型ガード

#### Backend: Dict[str, Any] → dataclass 化

```python
# Before:
async def _calculate_metrics(self, detection_results: Dict) -> Dict:

# After:
@dataclass
class DetectionResult:
    skeleton_data: List[SkeletonFrame]
    instrument_data: List[InstrumentFrame]
    video_info: VideoInfo

@dataclass
class MetricsResult:
    velocity: VelocityMetrics
    trajectory: TrajectoryMetrics
    stability: StabilityMetrics
```

**リスク回避策**: 型変更は段階的に。まず`types/analysis.ts`の`| any`除去 → ビルドエラーを確認 → 型が合わない箇所を個別修正。

---

### WP-6: ルーター層クリーンアップ
**リスク: 中 | インパクト: 中 | 工数: 小**

| タスク | 詳細 |
|--------|------|
| `sync_process_video_analysis` をサービス層に移動 | `analysis.py:394-496` のビジネスロジックを `analysis_service_v2.py` に移動 |
| `processing_tasks` 未使用変数削除 | `analysis.py:24` |
| segmentation.py のグローバル状態解消 | モジュールレベルのAIモデル変数を FastAPI Depends に移行 |
| `_get_video_info` 重複解消 | `analysis_service_v2.py` と `gaze_analysis_service.py` の共通メソッドをユーティリティに抽出 |

## 4. 実行順序と依存関係

```
WP-1 (Critical修正)        ← 最優先、他に依存なし
  │
  ├── WP-2 (API統一)       ← WP-1後（URL修正含むため）
  │     │
  │     └── WP-5 (型安全性) ← WP-2後（API型が確定してから）
  │
  ├── WP-3 (God Object)    ← WP-1後、WP-2と並行可能
  │     │
  │     └── WP-6 (ルーター) ← WP-3後（サービス構造確定後）
  │
  └── WP-4 (コンポーネント) ← WP-2後（API統一後に分割）
```

## 5. 品質目標

| 指標 | 現在 | 目標 | 計測方法 |
|------|------|------|---------|
| Backend スコア | 62 | 75+ | code-analyzer |
| Frontend スコア | 52 | 70+ | code-analyzer |
| any 型残存 | 80箇所 | 30以下 | grep count |
| API_BASE_URL 未使用 | 15箇所 | 0 | grep count |
| fetch 直書き | 20箇所 | 0 | grep count |
| 600行超コンポーネント | 4つ | 0 | wc -l |
| analysis_service_v2.py | 1261行 | 300行 | wc -l |
| except Exception: pass | 6箇所 | 0 | grep count |
| テスト退行 | 0 | 0 | pytest + playwright |

## 6. リスク管理

| リスク | 発生確率 | 影響度 | 回避策 |
|--------|---------|--------|--------|
| コンポーネント分割でUI崩れ | 中 | 高 | Playwright E2Eテストで画面確認、1コンポーネントずつ |
| Strategy パターン導入で既存解析が壊れる | 中 | 高 | 段階的移行、デリゲートパターンで旧コード残存 |
| fetch→axios変換でレスポンス構造不一致 | 低 | 中 | `res.json()` → `res.data` の全箇所確認 |
| 型定義変更でビルドエラー多発 | 低 | 低 | `| any` を段階的に除去、tsconfig strict は変更しない |
| GazeDashboardClient に誤って触れる | 低 | 高 | PROTECTED ルール厳守、git diff で確認 |

## 7. 完了基準

- [ ] WP-1: Critical 5件全て修正、テスト退行なし
- [ ] WP-2: fetch直書き 0、API_BASE_URL未使用 0
- [ ] WP-3: analysis_service_v2.py 300行以下
- [ ] WP-4: 600行超コンポーネント 0
- [ ] WP-5: any型 30箇所以下
- [ ] WP-6: sync_process_video_analysis サービス層移動
- [ ] 全体: Backend 75+ / Frontend 70+ 達成
