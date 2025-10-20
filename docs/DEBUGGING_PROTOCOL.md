# 🔍 デバッグプロトコル - 原因調査の必須確認事項

## 📋 全トラブル・問題調査時の必須3項目

トラブルや問題の原因を調査する際、**必ず以下の3点を確認・報告すること**：

### 1️⃣ 修正による他の部分への影響はないか？

**確認項目:**
- [ ] 修正対象の変数・関数が他のどこで使用されているか
- [ ] データフローの上流・下流への影響
- [ ] 同じパターンが他の場所にもないか
- [ ] APIの戻り値や引数の変更が他のコードに影響しないか
- [ ] 他の開発者が依存している可能性はないか

**調査方法:**
```bash
# 変数・関数の使用箇所を検索
grep -rn "variable_name" backend_experimental/app/

# データフロー確認
# 1. 修正箇所で何が返される/保存されるか
# 2. その値がどこで使われるか
# 3. その先でどう処理されるか

# 同じパターンの検索
grep -rn "similar_pattern" backend_experimental/app/
```

**記載例:**
```markdown
## 影響範囲分析

### 修正箇所
- ファイル: `sam2_tracker_video.py`
- 行: 367-368
- 変数: `video_segments`, `frame_count`

### 使用箇所
1. **_extract_trajectories() (389行目)**
   - `video_segments`を受け取り、全フレームを走査
   - ✅ 影響: より多くのフレームが処理される（意図通り）

2. **ログ出力 (384行目)**
   - `frame_count`を表示
   - ✅ 影響: 正しいフレーム数が表示される

### 結論
✅ **修正による悪影響なし**
- 全ての使用箇所で、より多くのデータが正しく処理される
- データ形式やAPIは変更なし
```

---

### 2️⃣ なぜこういう作りになっているのか？

**確認項目:**
- [ ] コードコメントや設計ドキュメントの確認
- [ ] Git履歴から実装意図を推測
- [ ] 過去のPRやissueの確認
- [ ] 類似コードとの比較
- [ ] フレームワーク・ライブラリの制約

**調査方法:**
```bash
# Git履歴確認
git log --oneline --all -- path/to/file.py
git show <commit_hash>
git blame path/to/file.py

# コメント確認
grep -rn "TODO\|FIXME\|NOTE\|WARNING" path/to/file.py

# 類似コード検索
grep -rn "similar_pattern" backend_experimental/app/
```

**記載例:**
```markdown
## 実装背景調査

### 現在のコード（問題あり）
```python
if out_frame_idx == 0:
    # デバッグログ
    video_segments[out_frame_idx] = masks  # ← なぜif内？
    frame_count += 1
```

### 推測される経緯
1. **初期実装**: 全フレームで保存していた（正しい）
2. **デバッグ追加**: frame 0でのみデバッグログを出力
3. **リファクタリング**: デバッグログと保存処理を同じif内に配置
4. **バグ混入**: 保存処理もif内に入ってしまった

### 証拠
- Git履歴なし（backend_experimentalは管理外）
- コメントに「デバッグ」と記載（360行目）
- 進捗ログもif内にある（371行目）→ 同時に追加された可能性

### 正しい設計
```python
# デバッグログ: frame 0のみ
if out_frame_idx == 0:
    logger.info("[DEBUG] Frame 0 mask keys: ...")

# データ保存: 全フレーム（if外）
video_segments[out_frame_idx] = masks
frame_count += 1
```

### 教訓
❌ **デバッグコードとビジネスロジックを同じスコープに置かない**
✅ **データ保存は条件分岐の外で行う**
```

---

### 3️⃣ この部分にも問題を起こしていそうな場所はないのか？

**確認項目:**
- [ ] 同じパターンのコードが他にもないか
- [ ] 同じ開発者が書いた他のコード
- [ ] 類似のデータ構造を扱うコード
- [ ] 同じライブラリを使用している箇所
- [ ] エラーハンドリングの漏れ

**調査方法:**
```bash
# パターン検索
grep -rn "if.*== 0:" backend_experimental/ | grep -v test

# インデントの深いコードを探す
grep -rn "^                        " backend_experimental/app/ | wc -l

# 空チェック漏れを探す
grep -rn "\.sum()\|len(.*)" backend_experimental/ | grep -v "if.*> 0"

# 例外処理の確認
grep -rn "try:" backend_experimental/app/ -A10 | grep -L "except"
```

**記載例:**
```markdown
## 類似問題の徹底検証

### ✅ 検証1: 同じファイル内の他のループ
```bash
grep -n "for.*in" sam2_tracker_video.py
```

**結果:**
- 296行目: `for out_frame_idx, out_obj_ids, out_mask_logits in ...` ← **今回の問題**
- 306行目: `for i, obj_id in enumerate(out_obj_ids):` ← ✅ 問題なし
- 364行目: `for obj_id in masks:` ← ✅ デバッグログのみ、問題なし
- 406行目: `for frame_idx in sorted(video_segments.keys()):` ← ✅ 問題なし

**結論:** 他のループには同様の問題なし

---

### ✅ 検証2: frame_count変数の他の使用箇所

**使用箇所:**
1. 287行目: `frame_count = 0` - 初期化
2. 338行目: `if frame_count % 100 == 0:` - ログ出力の条件
3. 368行目: `frame_count += 1` ← **問題箇所（if内）**
4. 374行目: ログ出力
5. 381行目: ログ出力
6. 384行目: ログ出力

**問題発見:**
338行目の`frame_count % 100 == 0`は、現状では**frame_count=0のときのみ**実行される！

```python
if frame_count % 100 == 0:  # ← frame_count=0のときのみTrue
    logger.debug(...)
```

このログは100フレームごとに出力されるべきだが、実際にはframe 0でしか出力されない。

**追加修正が必要:**
```python
# processed_framesを使用すべき
if processed_frames % 100 == 0:
    logger.debug(...)
```

---

### ✅ 検証3: video_segmentsの使用パターン

**辞書への値の代入箇所:**
- 367行目: `video_segments[out_frame_idx] = masks` ← **唯一の代入**

**辞書の読み取り箇所:**
- 396行目: `len(video_segments.keys())`
- 406行目: `for frame_idx in sorted(video_segments.keys()):`
- 407行目: `masks = video_segments[frame_idx]`

**問題:**
代入が1箇所しかないため、他の箇所で問題が隠れている可能性は低い。
ただし、**期待するデータ量と実際のデータ量が違う**ことで他の処理に影響。

---

### ✅ 検証4: 同様のデバッグログパターン

```bash
grep -rn "if.*frame.*== 0:" backend_experimental/app/
```

**結果:**
- sam2_tracker_video.py:301 - ✅ ログのみ、問題なし
- sam2_tracker_video.py:361 - ❌ **今回の問題箇所**
- analysis_service_v2.py:523 - ✅ ログのみ、問題なし

**結論:** 他のファイルには同様の問題なし

---

### 🔴 発見された追加問題

#### 問題1: frame_countの誤用（338行目）
```python
if frame_count % 100 == 0:  # ← 常にframe_count=0
```

**修正:**
```python
if processed_frames % 100 == 0:
```

#### 問題2: 進捗ログの位置（371-372行目）
```python
if processed_frames % 100 == 0:
    logger.warning(...)  # ← これもif (frame_idx == 0)の中！
```

**現状の動作:**
- frame 0でのみログ出力
- 100, 200, 300フレーム目ではログが出ない

**修正:**
if文の外に移動

---

### 📊 修正箇所まとめ

| 行 | 現在の位置 | 正しい位置 | 理由 |
|----|----------|----------|------|
| 367 | if内 | if外 | 全フレームで保存すべき |
| 368 | if内 | if外 | 全フレームでカウントすべき |
| 371-372 | if内 | if外 | 100フレームごとにログ出力すべき |
| 338 | frame_count | processed_frames | frame_countは常に0または1 |
```

---

## 📝 調査レポートテンプレート

```markdown
# 🐛 [問題名]

## 📊 問題の概要
- **発生日時**: YYYY-MM-DD HH:MM
- **影響範囲**: [ファイル名、関数名]
- **症状**: [具体的な問題]

---

## 1️⃣ 修正による他の部分への影響

### 修正箇所
- ファイル:
- 行番号:
- 変数/関数:

### 影響範囲分析
[使用箇所のリストと影響の評価]

### 結論
- ✅ 影響なし / ⚠️ 注意が必要 / ❌ 重大な影響

---

## 2️⃣ なぜこういう作りになっているのか？

### コード分析
[現在のコードの構造]

### 実装背景の推測
[Git履歴、コメント、類似コードから推測]

### 正しい設計
[本来あるべき実装]

### 教訓
[今後に活かすべきポイント]

---

## 3️⃣ 類似問題の徹底検証

### 検証1: [検証項目名]
- **調査コマンド**: `...`
- **結果**:
- **問題**: あり / なし

### 検証2: [検証項目名]
...

### 発見された追加問題
[問題のリスト]

### 修正箇所まとめ
[表形式で整理]

---

## ✅ 修正計画
1. [ ] [修正内容]
2. [ ] [テスト方法]
3. [ ] [検証手順]

---

## 📚 関連ドキュメント
- [PRD/設計書]
- [過去のissue]
- [関連するPOST_MORTEM]
```

---

## 🔧 ツール・コマンド集

### Git調査
```bash
# 特定ファイルの履歴
git log --oneline -- path/to/file.py

# 特定行の変更履歴
git blame path/to/file.py -L 100,200

# 特定コミットの詳細
git show <commit_hash>

# 削除されたファイルを探す
git log --all --full-history -- "**/deleted_file.py"
```

### コード検索
```bash
# パターン検索
grep -rn "pattern" backend_experimental/app/

# 正規表現検索
grep -rn "if.*== 0:" backend_experimental/

# 特定の深さのインデント
grep -rn "^                        " backend_experimental/

# 関数定義の検索
grep -rn "def function_name" backend_experimental/

# クラス定義の検索
grep -rn "class ClassName" backend_experimental/
```

### データフロー追跡
```bash
# 変数の定義と使用
grep -rn "variable_name" backend_experimental/ | sort

# 関数の呼び出し元
grep -rn "function_name(" backend_experimental/

# インポート元の確認
grep -rn "from.*import.*ClassName" backend_experimental/
```

### 潜在的問題の検出
```bash
# 空チェック漏れ
grep -rn "\.sum()\|len(" backend_experimental/ | grep -v "if.*> 0"

# 例外処理漏れ
grep -rn "try:" backend_experimental/ -A10 | grep -L "except"

# ハードコードされた値
grep -rn "[0-9]\{3,\}" backend_experimental/ | grep -v "test\|#"

# TODO/FIXMEコメント
grep -rn "TODO\|FIXME\|HACK\|XXX" backend_experimental/
```

---

## 🎯 重要な原則

### デバッグの3原則
1. **問題を孤立させない**: 似た問題が他にもないか必ず確認
2. **履歴を学ぶ**: なぜそうなったかを理解しないと再発する
3. **影響を見極める**: 修正が新しい問題を生まないか検証

### レポートの3要素
1. **原因**: 何が問題か（技術的詳細）
2. **背景**: なぜそうなったか（コンテキスト）
3. **影響**: 他に何が影響するか（波及効果）

### 修正の3段階
1. **直接修正**: 問題箇所そのもの
2. **類似修正**: 同じパターンの箇所
3. **予防修正**: 将来同じ問題を防ぐための改善

---

## 📖 実例: SAM2器具検出バグ

詳細は [POST_MORTEM_SAM2_INSTRUMENT_DETECTION.md](POST_MORTEM_SAM2_INSTRUMENT_DETECTION.md) を参照
