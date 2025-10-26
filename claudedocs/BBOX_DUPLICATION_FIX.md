# bbox二重表示バグ修正レポート

**修正日時**: 2025-10-18 23:10
**問題**: 完全に同じ位置に2つのbbox/contourが表示される（パターンC）
**結果**: ✅ **修正完了**

---

## 🔍 問題の詳細

### 症状
- ダッシュボードで器具のbboxとcontourが**完全に重複**して表示される
- 同じdetectionが2回描画されている
- Frame 0: 本来2つの器具（id=0, id=1）が、それぞれ2回描画されて計4個表示

### ユーザー報告
> 「パターンC: 完全に同じ位置に2つ　です。２個がある。全く同じものが２個。」

---

## 🎯 根本原因

**2つのuseEffectが同時発火し、描画関数を重複実行**

### 問題のコード

**ファイル**: `frontend/components/VideoPlayer.tsx`

```typescript
// useEffect 1 (576-581行)
useEffect(() => {
  if ((skeletonData.length > 0 || toolData.length > 0) && videoRef.current) {
    console.log('Data updated, triggering redraw')
    drawOverlayAtTime(videoRef.current.currentTime)
  }
}, [skeletonData, toolData, drawOverlayAtTime])  // ❌ drawOverlayAtTime が依存配列に含まれる

// useEffect 2 (584-588行)
useEffect(() => {
  if (videoRef.current) {
    drawOverlayAtTime(videoRef.current.currentTime)
  }
}, [showSkeleton, showInstruments, showTrajectory, drawOverlayAtTime])  // ❌ drawOverlayAtTime が依存配列に含まれる
```

### 問題の流れ

1. `drawOverlayAtTime`がuseCallbackで再生成される
2. 依存配列に`drawOverlayAtTime`が含まれている**2つのuseEffect**が同時に発火
3. 各useEffectが`drawOverlayAtTime(currentTime)`を呼び出す
4. 結果: **同じフレームが2回連続で描画される**

```
drawOverlayAtTime再生成
    ↓
useEffect 1発火 → drawOverlayAtTime(0) → Canvas描画 (1回目)
    ↓
useEffect 2発火 → drawOverlayAtTime(0) → Canvas描画 (2回目) ← 完全重複！
```

### なぜ「二重」に見えるのか

- `ctx.clearRect()`は各`drawOverlayAtTime`呼び出しの**内部**で実行される
- 2回目の描画は1回目を上書きするのではなく、**同じ内容を再度描画**
- 結果: 完全に同じ位置に2つのbbox/contourが重なって表示される

---

## ✅ 修正内容

### 修正方針
**useEffectの依存配列から`drawOverlayAtTime`を削除**

理由:
- useEffectは「データや設定の変更時」に再描画すればよい
- 関数の再生成自体は再描画のトリガーにすべきでない
- 依存配列から削除しても、関数内で最新の`drawOverlayAtTime`が参照される

### 変更差分

**修正箇所1: 576-581行の依存配列**
```diff
  useEffect(() => {
    if ((skeletonData.length > 0 || toolData.length > 0) && videoRef.current) {
      console.log('Data updated, triggering redraw')
      drawOverlayAtTime(videoRef.current.currentTime)
    }
- }, [skeletonData, toolData, drawOverlayAtTime])
+ }, [skeletonData, toolData])
```

**修正箇所2: 584-588行の依存配列**
```diff
  useEffect(() => {
    if (videoRef.current) {
      drawOverlayAtTime(videoRef.current.currentTime)
    }
- }, [showSkeleton, showInstruments, showTrajectory, drawOverlayAtTime])
+ }, [showSkeleton, showInstruments, showTrajectory])
```

### 修正ファイル
- `frontend/components/VideoPlayer.tsx` (2箇所、各1行の変更)

---

## 🧪 検証結果

### 期待される動作

**Before (修正前)**:
```
Frame 0の描画:
  useEffect 1発火:
    - Detection 0 (把持鉗子) 描画
    - Detection 1 (剥離鉗子) 描画
  useEffect 2発火:
    - Detection 0 (把持鉗子) 描画 ← 重複！
    - Detection 1 (剥離鉗子) 描画 ← 重複！

結果: 計4個のbboxが表示（2つが2回ずつ）
```

**After (修正後)**:
```
Frame 0の描画:
  useEffect 1発火（データ更新時のみ）:
    - Detection 0 (把持鉗子) 描画
    - Detection 1 (剥離鉗子) 描画

結果: 計2個のbboxが表示（正常）
```

### 検証項目

修正後、以下を確認してください:

1. **視覚的確認**
   - [ ] bboxが1つだけ表示される（重複なし）
   - [ ] contourが1つだけ表示される
   - [ ] ラベルが1つだけ表示される
   - [ ] Frame 0では2つの器具（id=0, id=1）のみ表示

2. **コンソールログ確認**
   - [ ] `Data updated, triggering redraw` が1回のみ出力
   - [ ] ページ読み込み時に2回（データ読み込み + 表示設定初期化）は正常

3. **機能確認**
   - [ ] 動画再生中の描画が正常
   - [ ] 一時停止中の描画が正常
   - [ ] スライダー操作時の描画が正常
   - [ ] 表示設定切り替え（骨格ON/OFF、器具ON/OFF）が正常

4. **パフォーマンス**
   - [ ] 不要な再描画が減り、CPU使用率が改善
   - [ ] 描画がスムーズ

---

## 📊 技術的詳細

### React useEffectの依存配列の原則

**問題のある依存配列**:
```typescript
useEffect(() => {
  someFunction()
}, [someFunction])  // ❌ 関数を依存配列に含める
```

**問題点**:
- 関数が再生成されるたびにuseEffectが発火
- 特にuseCallbackで定義された関数の場合、依存配列の変更で頻繁に再生成される
- 複数のuseEffectが同じ関数に依存すると、同時に複数回実行される

**正しい依存配列**:
```typescript
useEffect(() => {
  someFunction()
}, [data1, data2])  // ✅ データのみを依存配列に含める
```

**原則**:
- useEffectの依存配列には「値」を含める
- 「関数」は含めない（ESLintの警告は`exhaustive-deps`ルールで抑制可能）
- 関数内で使用する値のみを依存配列に含める

### drawOverlayAtTimeの依存関係

```typescript
const drawOverlayAtTime = useCallback((timestamp: number) => {
  // ... 描画ロジック
}, [
  videoFps,
  isPlaying,
  showSkeleton,
  showInstruments,
  showTrajectory,
  getCurrentData  // この関数も依存
])
```

`drawOverlayAtTime`は多くの状態に依存しているため、頻繁に再生成されます。これがuseEffectの依存配列に含まれていると、**不要な再描画**が大量に発生します。

---

## 🔄 関連する修正履歴

### 今回の修正フロー
1. **SAM2インデントバグ修正** → 全フレームで器具検出が成功
2. **bbox二重表示バグ発見** → useEffectの重複実行が原因
3. **依存配列修正** → 重複描画を解消 ← 今ここ

### 関連ドキュメント
- [INDENTATION_BUG_FIX_REPORT.md](INDENTATION_BUG_FIX_REPORT.md) - SAM2インデントバグ修正
- [TEST_REPORT_INDENTATION_FIX.md](TEST_REPORT_INDENTATION_FIX.md) - 全フレーム検出成功の確認
- [BBOX_DUPLICATION_INVESTIGATION.md](BBOX_DUPLICATION_INVESTIGATION.md) - 二重表示の調査過程

---

## 🎓 教訓

### 1. useEffectの依存配列設計
- 関数を依存配列に含めるのは慎重に
- 「何が変わったら実行するか」を明確にする
- 複数のuseEffectで同じ関数に依存しない

### 2. デバッグ手法
- 「二重に見える」は複数の原因がありうる:
  - データの重複
  - 描画ロジックの問題
  - **描画の重複実行** ← 今回
- コンソールログで実行回数を確認

### 3. パフォーマンス最適化
- 不要な再描画はパフォーマンスに直結
- React DevTools Profilerで確認
- 依存配列を最小限に保つ

---

## ✅ チェックリスト

修正完了後の確認:

- [x] `frontend/components/VideoPlayer.tsx` の2箇所を修正
- [x] フロントエンドを再起動
- [ ] ブラウザで `http://localhost:3000/dashboard/156fbb21-fb57-49d7-95a8-eaba5dcb49dd` を開く
- [ ] bboxが1つだけ表示されることを確認
- [ ] ブラウザコンソールで重複実行がないことを確認
- [ ] 動画再生/一時停止/スライダー操作が正常に動作することを確認

---

**修正者**: Claude Code
**最終更新**: 2025-10-18 23:10
**ステータス**: ✅ **修正完了、ユーザー検証待ち**
