# MindMotionAI リファクタリング計画 v2

> **更新日**: 2026-04-03
> **更新理由**: リスク評価エージェントによる分析結果を反映。Phase 1の事前修正追加、Phase 6をHIGH→3ステップに分割、Phase 7にURL維持制約を追加。

## Context
33GBのプロジェクトが肥大化。容量の99.95%はバイナリ/生成物だが、ソースコード自体にも約45,000行のデッドコード・重複がある。deprecatedな`backend/`(13GB)、66個の散らかったスクリプト、1000行超の巨大ファイルが主要問題。このリファクタリングでコードベースを約半分に削減し、保守性を大幅に向上させる。

## リスク評価サマリー

| Phase | 内容 | リスク | 主要リスク要因 |
|-------|------|--------|---------------|
| 1 | backend/削除 | 🟢 LOW | SAMモデルパス参照4箇所 → 事前修正で解消 |
| 2 | スクリプト39個削除 | 🟢 LOW | 本番コードからの参照ゼロ |
| 3 | テスト配置整理 | 🟢 LOW | ファイル移動のみ |
| 4 | バックアップ削除 | 🟢 LOW | 問題なし |
| 5 | CLAUDE.mdスリム化 | 🟡 LOW-MED | ドキュメント整合性 |
| 6a | SAMTrackerUnifiedにメソッド追加 | 🟡 MEDIUM | API非互換の解消作業 |
| 6b | モックモード対応追加 | 🟡 MEDIUM | SAM未インストール環境への対応 |
| 6c | sam_tracker.py除去 | 🟢 LOW | 6a/6b完了後は安全 |
| 7 | videos.py分割 | 🟢 LOW | URLプレフィックス維持が条件 |

---

## Phase 1: `backend/` ディレクトリの全削除
**リスク: 🟢 LOW | 削減: ~25,500行 / 123ファイル**

### 根拠
- CLAUDE.mdで「Legacy backend (Port 8000) is deprecated」と明記済み
- backend/app/ は backend_experimental/app/ の**古いバージョン**（機能が少ない）
- 唯一の固有ファイル `openapi.json` はFastAPIから再生成可能
- Pythonインポート依存: ゼロ（`from backend.` / `import backend.` は全コードで不在）
- ランタイムデータ（DB、アップロード動画）: 存在しない

### ⚠️ 事前修正（削除前に必須）

**SAMモデルのフォールバックパス修正（3箇所）:**

| ファイル | 行 | 修正内容 |
|---------|-----|---------|
| `backend_experimental/app/ai_engine/processors/sam_tracker_unified.py` | 119 | `Path("backend/sam_vit_h_4b8939.pth")` → `Path("backend_experimental/sam_vit_h_4b8939.pth")` |
| `backend_experimental/app/ai_engine/processors/sam_tracker_unified.py` | 123 | `Path("backend/sam_b.pt")` → `Path("backend_experimental/sam_b.pt")` |
| `backend_experimental/app/ai_engine/processors/sam_tracker.py` | 64 | `Path("backend/sam_b.pt")` → `Path("backend_experimental/sam_b.pt")` |

**テストファイルのパス修正（2箇所）:**

| ファイル | 行 | 修正内容 |
|---------|-----|---------|
| `frontend/tests/e2e-v2-upload.spec.ts` | 20 | `../../backend/data/uploads/` → `../../backend_experimental/data/uploads/` |
| `frontend/tests/experimental-sam2-test.spec.ts` | 7 | 同上 |

**エラーメッセージ修正（低優先、同時修正推奨）:**

| ファイル | 行 | 内容 |
|---------|-----|------|
| `sam_tracker_unified.py` | 138 | `"run backend/download_sam_vit_h.py"` → `"run backend_experimental/download_sam_vit_h.py"` |
| `test_sam2_integration.py` | 198 | `"Set USE_SAM2=true in backend/.env"` → `"...in backend_experimental/.env"` |

### 作業
- [ ] 上記の事前修正を適用（5ファイル7箇所）
- [ ] `backend/` ディレクトリを完全削除
- [ ] `.gitignore` から `backend/` 固有エントリを削除（L11-14, L17, L37-40, L48, L54, L58-60 → 計14行）
- [ ] `kill_all_servers.bat` L13-14, `kill_all_processes.bat` L31-35 の `backend/.server.lock` 参照を削除
- [ ] `verify_fix.py` L19 の `backend/aimotion.db` フォールバックを削除

### 検証
```bash
cd backend_experimental && ./venv311/Scripts/python.exe -c "from app.main import app; print('OK')"
grep -r "backend/" .gitignore  # backend/ 参照がないこと
grep -rn "Path(\"backend/" backend_experimental/app/  # フォールバックパスが修正済みであること
```

### コミット
`chore: remove deprecated legacy backend/ directory (-25,500 lines)`

---

## Phase 2: ルートスクリプトの整理（backend_experimental/直下）
**リスク: 🟢 LOW | 削減: ~12,000行 / 39ファイル削除**

### リスク評価結果
- 本番コード（`app/`）からのインポート: **ゼロ**
- バッチファイルからの参照: **ゼロ**
- テストファイルからの参照: **ゼロ**
- KEEPスクリプト14個からの依存: **ゼロ**
- 39ファイル全てが自己完結型のワンショットスクリプト

### 削除対象（39ファイル）

**generate_*.py（実験用、全24ファイル）:**
generate_bare_hands_detection.py, generate_detection_video.py, generate_enhanced_detection_video.py, generate_enhanced_detection_video_96percent.py, generate_front_angle_final.py, generate_front_angle_no_face.py, generate_grip_instrument_detection.py, generate_instrument_detection_sam.py, generate_instrument_detection_simple.py, generate_instrument_landmark_tracking.py, generate_instrument_motion_tracking.py, generate_optical_flow_tracking.py, generate_practical_instrument_tracking.py, generate_precise_instrument_tracking.py, generate_sam_instrument_tracking.py, generate_sample_metrics.py, generate_shape_recognition_tracking.py, generate_surgical_hands_only.py, generate_true_instrument_tracking.py, generate_ultra_enhanced_detection_video.py, generate_white_glove_balanced.py, generate_white_glove_detection.py, generate_white_glove_filtered.py, improve_continuous_detection.py

**ハードコードUUID（7ファイル）:**
check_5cb40515.py, check_8b90f115.py, check_ae5a56e2_full.py, check_analysis_8715.py, check_analysis_frames.py, check_inst_structure.py, verify_phase1_bbox.py

**ワンオフ調査（8ファイル）:**
analyze_detection_gaps.py, analyze_status_impact.py, analyze_white_glove_misdetection.py, investigate_comparison.py, find_all_status_usages.py, trigger_new_analysis.py, update_analysis_instruments.py, upload_test_video.py

### その他の削除
- `_analysis_service_dump.txt`（デバッグダンプ）
- `POST_MORTEM_INSTRUMENT_COMPRESSION.md`（docs/に移動済みなら削除）
- `LEGACY_CLEANUP_PLAN.md`（今回の計画で代替）

### 残すもの（14ファイル）
check_analyses.py, check_comparison.py, check_cuda.py, check_gaze_data.py, check_library_api.py, check_missing_videos.py, add_gaze_data_column.py, download_sam2_large.py, download_sam_vit_h.py, register_video.py, create_both_hands_video.py, create_reference_model.py, optimize_glove_detection.py, pose_guided_hand_detection.py

### 検証
```bash
cd backend_experimental && ./venv311/Scripts/python.exe -c "from app.main import app; print('OK')"
```

### コミット
`chore: remove 39 one-off scripts from backend_experimental/ root (-12,000 lines)`

---

## Phase 3: テストファイルの適切な配置 + ルートファイル整理
**リスク: 🟢 LOW | 移動: 17ファイル、削除: 5ファイル**

### backend_experimental/ → tests/ への移動（13ファイル）
| 移動元 | 移動先 |
|--------|--------|
| test_code_loaded.py | tests/unit/ |
| test_contour_fix.py | tests/unit/ |
| test_delete_analysis.py | tests/integration/ |
| test_mask_initialization.py | tests/unit/ |
| test_reference_model.py | tests/integration/ |
| test_sam2_basic.py | tests/unit/ |
| test_sam2_integration.py | tests/integration/ |
| test_sam_gpu.py | tests/unit/ |
| test_sqlalchemy_enum.py | tests/unit/ |
| verify_compression_fix.py | tests/integration/ |
| verify_instruments_fix.py | tests/integration/ |
| verify_reference_videos.py | tests/integration/ |
| verify_rotated_bbox.py | tests/integration/ |

### プロジェクトルート → 移動/削除
| ファイル | アクション |
|---------|-----------|
| test_auto_detection.py | → backend_experimental/tests/integration/ |
| test_detection_comparison.py | → backend_experimental/tests/integration/ |
| test_experimental_e2e.py | → backend_experimental/tests/integration/ |
| check_new_analysis.py | → backend_experimental/tests/integration/ |
| test_rotated_bbox_mcp.js | 削除（MCP関連の一時テスト） |
| check_bdeb0ac2.py | 削除（ハードコードUUID） |
| copy_to_experimental.py | 削除（ワンオフ移行スクリプト） |

### frontend/ → テストへ移動
| ファイル | アクション |
|---------|-----------|
| test_sam_integration.html | → frontend/tests/ |
| test-skeleton.html | → frontend/tests/ |

### 検証
```bash
cd backend_experimental && ./venv311/Scripts/python.exe -m pytest tests/ --collect-only
```

### コミット
`refactor: organize test files into proper test directories`

---

## Phase 4: バックアップ・スナップショットファイルの削除
**リスク: 🟢 LOW | 削減: ~900行**

### 削除対象
- `frontend/components/GazeDashboardClient.custom.tsx`（GazeDashboardClient.tsxと完全同一）
- `docs/code_snapshots/`（Gitで履歴管理されている）
- `frontend/switch_backend.bat`（backend/削除後は不要）

### 検証
```bash
ls frontend/components/GazeDashboardClient.tsx  # 本体が存在すること
```

### コミット
`chore: remove backup files and code snapshots`

---

## Phase 5: CLAUDE.md のスリム化
**リスク: 🟡 LOW-MEDIUM | 変更: CLAUDE.md 838行 → ~120行**

### 方針
- CLAUDE.mdは**クイックリファレンス**に特化（起動方法、ディレクトリ構造、重要ルール）
- 詳細情報は `docs/` 配下に分散
- CLAUDE.mdから `See docs/xxx.md` でリンク

### 新CLAUDE.md 構成（約120行）
```
# Project: MindMotionAI - 手技モーション可視化AI
## Language: 日本語
## Architecture（10行）
## Directory Structure（15行）
## Quick Start（10行）
## Testing（10行）
## Key Rules（15行）- Fail Fast, Python 3.11, CORS等
## Critical Files（10行）
## Debugging Protocol（10行）→ 詳細は docs/DEBUGGING_PROTOCOL.md
## See Also → docs/ へのリンク集
```

### 移動先
| 内容 | 移動先 |
|------|--------|
| 詳細な環境構築手順 | docs/06_development/06_development_setup.md（既存） |
| デバッグプロトコル | docs/DEBUGGING_PROTOCOL.md（既存） |
| データパイプライン品質保証 | docs/07_quality/data_pipeline_quality.md（新規） |
| POST MORTEM教訓 | docs/post_mortems/（既存ディレクトリに集約） |
| Git/コミット規約 | docs/06_development/git_guidelines.md（新規） |

### claudedocs/ の整理
- 17ファイル/4,019行 → 有用なものだけ docs/ に統合、残りは削除

### 検証
- Claude Codeの新セッションでCLAUDE.mdが読み込まれ、プロジェクト理解に十分な情報があるか確認

### コミット
`docs: slim down CLAUDE.md from 838 to ~120 lines, consolidate documentation`

---

## Phase 6a: SAMTrackerUnified に不足メソッドを追加 ★コード変更あり
**リスク: 🟡 MEDIUM | 変更: sam_tracker_unified.py に ~70行追加**

### 背景（リスク評価で発見されたAPI非互換）

| # | 問題 | 深刻度 | 詳細 |
|---|------|--------|------|
| 1 | `visualize_result()` が SAMTrackerUnified に存在しない | **CRITICAL** | videos.py の2箇所で使用中。未実装のまま切り替えるとランタイムエラー |
| 2 | `use_mock=True` パラメータが存在しない | **CRITICAL** | SAM未インストール環境で完全停止 |
| 3 | デフォルト model_type/device の違い | **MEDIUM** | vit_b→vit_h, cpu→cuda |

### 作業
1. `sam_tracker.py` の `visualize_result()` メソッド（約65行）を `sam_tracker_unified.py` に移植
   - 元のメソッドのロジック: マスクオーバーレイ + バウンディングボックス描画 + アルファブレンド
2. テストで `visualize_result()` が正常に動作することを確認

### 対象ファイル
- `backend_experimental/app/ai_engine/processors/sam_tracker_unified.py` — メソッド追加

### 検証
```bash
cd backend_experimental && ./venv311/Scripts/python.exe -c "
from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
assert hasattr(SAMTrackerUnified, 'visualize_result'), 'visualize_result not found'
print('OK: visualize_result exists')
"
```

### コミット
`feat: add visualize_result() to SAMTrackerUnified for API compatibility`

---

## Phase 6b: SAMTrackerUnified にモックモード対応を追加 ★コード変更あり
**リスク: 🟡 MEDIUM | 変更: sam_tracker_unified.py に ~30行追加**

### 作業
1. `SAMTrackerUnified.__init__()` に `use_mock=False` パラメータを追加
2. SAMライブラリ未インストール時の graceful degradation を実装
   - モックモード時: ダミーの segmentation 結果を返す
   - 本番時: 従来通り RuntimeError
3. `get_sam_tracker()` ファクトリの `use_mock=True` 呼び出しとの互換性を確保

### 対象ファイル
- `backend_experimental/app/ai_engine/processors/sam_tracker_unified.py` — __init__ 修正 + モックロジック追加

### 検証
```bash
cd backend_experimental && ./venv311/Scripts/python.exe -c "
from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
tracker = SAMTrackerUnified(use_mock=True)
print('OK: mock mode works')
"
```

### コミット
`feat: add mock mode to SAMTrackerUnified for graceful degradation`

---

## Phase 6c: sam_tracker.py（レガシー）の除去 ★コード変更あり
**リスク: 🟢 LOW（6a/6b完了が前提）| 削減: ~1,177行**

### 前提条件
- ✅ Phase 6a 完了（visualize_result 追加済み）
- ✅ Phase 6b 完了（モックモード対応済み）

### 作業
1. `videos.py` のimportを変更:
   ```python
   # Before
   from app.ai_engine.processors.sam_tracker import SAMTracker
   # After
   from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified as SAMTracker
   ```
2. `get_sam_tracker()` ファクトリのインスタンス生成パラメータを調整:
   - `model_type` → SAMTrackerUnifiedのデフォルト（vit_h）に合わせるか、明示的に指定
   - `device` → 環境に応じたフォールバック（cuda → cpu）
3. `tests/unit/test_gaze_analyzer.py` L518 のインポートも更新
4. `sam_tracker.py` を削除

### 対象ファイル
- `backend_experimental/app/api/routes/videos.py` — import変更 + ファクトリ関数更新
- `backend_experimental/tests/unit/test_gaze_analyzer.py` — import更新
- `backend_experimental/app/ai_engine/processors/sam_tracker.py` — **削除**

### 検証（必須）
```bash
# インポート確認
cd backend_experimental && ./venv311/Scripts/python.exe -c "from app.main import app; print('OK')"

# 旧importが残っていないこと
grep -rn "from app.ai_engine.processors.sam_tracker import" backend_experimental/

# ユニットテスト
./venv311/Scripts/python.exe -m pytest tests/ -v

# E2Eテスト（フロントエンドから器具検出が動作するか）
cd frontend && npx playwright test --grep "instrument"
```

### コミット
`refactor: replace legacy SAMTracker with SAMTrackerUnified in videos.py (-1,177 lines)`

---

## Phase 7: videos.py の分割 ★コード変更あり
**リスク: 🟢 LOW | 変更: 976行 → 3ファイルに分割**

### ⚠️ 重要制約: URLプレフィックスを変更しないこと

**リスク評価で判明**: フロントエンド5箇所が現在のURL構造 `/api/v1/videos/{video_id}/...` に依存

| ファイル | 箇所 | URL |
|---------|------|-----|
| `frontend/components/InstrumentSelector.tsx` | L120 | `/videos/${videoId}/detect-instruments-sam2` |
| `frontend/components/InstrumentSelector.tsx` | L288 | `/videos/${videoId}/segment-from-detection` |
| `frontend/components/InstrumentSelector.tsx` | L414 | `/videos/${videoId}/segment` |
| `frontend/components/InstrumentSelector.tsx` | L491 | `/videos/${videoId}/instruments` |
| `frontend/app/upload/page.tsx` | L184 | `/videos/${videoId}/instruments` |

**→ segmentation.py も `prefix="/api/v1/videos"` で登録する。URLは一切変更しない。**

### エンドポイント分類（13個）
**videos.py に残す（Video CRUD、6個）:**
- `POST /upload`, `GET /{video_id}`, `GET /`, `GET /stream/{video_id}`, `GET /{video_id}/stream`, `GET /{video_id}/thumbnail`

**segmentation.py に移動（器具関連、7個）:**
- `POST /{video_id}/segment`, `POST /{video_id}/instruments`, `GET /{video_id}/instruments`, `POST /{video_id}/detect-instruments`, `POST /{video_id}/segment-from-detection`, `POST /{video_id}/detect-instruments-sam2`

### 共有状態の分析（リスク評価で確認済み）
- `_sam_tracker` グローバル + `get_sam_tracker()` → segmentation.py に完全移動可能
- `_tool_detector` グローバル + `get_tool_detector()` → segmentation.py に完全移動可能
- `_sam2_auto_generator` + `get_sam2_auto_generator()` → segmentation.py に完全移動可能
- `_translate_tool_name()` → segmentation.py に完全移動可能
- `fix_encoding()` → videos.py に残留（video CRUD専用）
- **衝突リスク: ゼロ**

### 分割後の構成
```
backend_experimental/app/api/routes/
├── videos.py              ← Video CRUD (~350行)
├── segmentation.py        ← 器具検出/セグメンテーション (~400行)
└── instrument_tracking.py ← 既存（変更なし）
```

### 作業
1. `segmentation.py` を新規作成、器具関連の7エンドポイント + ヘルパー関数を移動
2. `main.py` L12 のimportに `segmentation` を追加
3. `main.py` にルーター登録を追加:
   ```python
   app.include_router(segmentation.router, prefix=f"{settings.API_V1_STR}/videos", tags=["segmentation"])
   ```
4. videos.py から移動済みコードを削除

### 対象ファイル
- `backend_experimental/app/api/routes/videos.py` — 器具関連コード削除
- `backend_experimental/app/api/routes/segmentation.py` — **新規作成**
- `backend_experimental/app/main.py` L12 — import追加 + ルーター登録追加

### 検証（必須）
```bash
# 全テスト実行
cd backend_experimental && ./venv311/Scripts/python.exe -m pytest tests/ -v

# API起動 + 全エンドポイント確認
./venv311/Scripts/python.exe -c "from app.main import app; print('OK')"
curl http://localhost:8001/docs  # Swagger UIで全エンドポイント表示確認

# E2Eテスト（フロントエンドのURL依存が壊れていないこと）
cd frontend && npx playwright test
```

### コミット
`refactor: split videos.py into video CRUD and segmentation modules`

---

## 実行順序とタイムライン

```
Day 1:  Phase 1 (backend/削除 + 事前修正5ファイル) + Phase 2 (スクリプト39個削除)
Day 2:  Phase 3 (テスト配置) + Phase 4 (バックアップ削除)
Day 3:  Phase 5 (CLAUDE.mdスリム化)
Day 4:  Phase 6a (SAMTrackerUnifiedにvisualize_result追加)
        Phase 6b (モックモード対応追加)
        Phase 6c (videos.py切り替え + sam_tracker.py削除)
Day 5:  Phase 7 (videos.py分割 ※URLプレフィックス維持必須)
```

## 全体のインパクト

| 指標 | Before | After | 削減 |
|------|--------|-------|------|
| ソースコード行数 | ~103,000 | ~58,000 | **-45,000行 (44%)** |
| ファイル数 | ~545 | ~370 | **-175ファイル (32%)** |
| Git管理対象容量 | ~15MB | ~9MB | **-6MB (40%)** |
| 1000行超ファイル | 6個 | 3個 | **-3個** |

## 今回のスコープ外（将来のPhase）
- analysis_service_v2.py の分割（1504行 → 要テスト構築後）
- GazeDashboardClient.tsx の分割（879行 → フロントエンド専用セッション推奨）
- 型アノテーション強化
- API命名規則統一
- ドキュメント内の `backend/` → `backend_experimental/` 参照更新（Phase 1で動作に影響ある箇所は修正済み）
