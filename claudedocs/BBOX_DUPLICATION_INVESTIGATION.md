# bbox二重表示問題 - 調査レポート

**報告日時**: 2025-10-18 22:50
**解析ID**: 156fbb21-fb57-49d7-95a8-eaba5dcb49dd
**症状**: ダッシュボードでbboxが二重で表示される

---

## 🔍 調査結果

### 1. データ構造の検証

**Frame 0のdetection**:
```
Total detections: 2

Detection 0:
  id: 0
  name: 把持鉗子
  bbox: [758.0, 211.0, 791.0, 457.0]
  contour_points: 13
  confidence: 1.0

Detection 1:
  id: 1
  name: 剥離鉗子
  bbox: [644.0, 447.0, 810.0, 511.0]
  contour_points: 19
  confidence: 0.8142570281124498
```

**結論**: ✅ **データに重複なし**
- 各フレームに複数のdetectionがあるのは正常
- 各detectionは1つのbbox、1つのcontourを持つ
- idが異なる別々の器具

---

### 2. 描画ロジックの分析

**ファイル**: `frontend/components/VideoPlayer.tsx`

#### 器具描画コード (270-343行)

```typescript
if (showInstruments && tools?.detections) {
  tools.detections.forEach((detection) => {
    const [x1, y1, x2, y2] = detection.bbox

    // ✅ 分岐: contourがあればcontour描画、なければbbox描画
    if (detection.contour && detection.contour.length > 2) {
      // 1. 塗りつぶし (279-292行)
      ctx.fillStyle = 'rgba(147, 51, 234, 0.35)'  // 半透明
      ctx.fill()

      // 2. 輪郭線 (294-297行)
      ctx.strokeStyle = color
      ctx.lineWidth = 2.5
      ctx.stroke()
    } else {
      // フォールバック: bboxを矩形で描画 (304-327行)
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
    }

    // 3. ラベル（常に描画） (330-343行)
    ctx.fillText(label, x1 + 4, y1 - 6)
  })
}
```

**結論**: ✅ **ロジックは正しい**
- contourがある場合: 塗りつぶし + 輪郭線
- contourがない場合: bbox矩形
- if-elseで排他的に描画（両方は描画されない）

---

### 3. 「二重」に見える可能性のある原因

#### 原因A: 塗りつぶしと輪郭線の組み合わせ
**現在の描画**:
- 塗りつぶし: `rgba(147, 51, 234, 0.35)` (紫、35%透明)
- 輪郭線: `#9333EA` (濃い紫、lineWidth=2.5)

**視覚的効果**:
```
┌─────────────┐
│░░░░░░░░░░░░░│  ← 半透明塗りつぶし
│░░░contour░░░│
│░░░░░░░░░░░░░│
└─────────────┘
     ▲
    濃い輪郭線
```

この2つの組み合わせが「二重」に見える可能性があります。

**判定**: ⚠️ **設計意図通りだが、ユーザーには二重に見える可能性**

---

#### 原因B: 複数の器具が近接・重複
**Frame 0の器具位置**:
- id=0 (把持鉗子): bbox=[758, 211, 791, 457]
- id=1 (剥離鉗子): bbox=[644, 447, 810, 511]

**位置関係**:
```
        id=0
    ┌────┐
    │    │
    │    │  ← Y座標447でid=1と重複
    └────┘
  ┌──────────┐
  │  id=1    │
  └──────────┘
```

Y座標447-457の範囲で2つの器具が重なっています。

**判定**: ⚠️ **実際に2つの器具が重複している可能性**

---

#### 原因C: 描画の重複呼び出し
**drawOverlayAtTimeの呼び出し箇所**:
1. Line 426: RVFC (再生中、毎フレーム)
2. Line 442: RAF (フォールバック、再生中)
3. Line 477: 一時停止中の手動描画
4. Line 517: 初期描画
5. Line 527: シーク時
6. **Line 579: データ更新時** ← 🚨
7. **Line 586: 表示設定変更時** ← 🚨

**問題点**:
- Line 579と586のuseEffectが**同時に発火**する可能性
- 157行のフレームスキップは**一時停止中のみ有効**

**判定**: ⚠️ **再生中に同じフレームが複数回描画される可能性**

---

## 🎯 問題の特定

### 質問1: どのような「二重」か？

**パターンA: 輪郭が二重**
```
┌═══════┐  ← 外側の輪郭
│┌─────┐│  ← 内側の輪郭
││     ││
│└─────┘│
└═══════┘
```
→ 原因: 塗りつぶし(fill)と輪郭(stroke)の両方が描画されている

**パターンB: 器具全体が二重**
```
┌─────┐
│  1  │  ← 1つ目の器具
└─────┘
┌─────┐
│  2  │  ← 2つ目の器具（少しずれて重なっている）
└─────┘
```
→ 原因: 実際に2つの異なる器具が検出されている

**パターンC: 完全に重複**
```
┌─────┐
┌─────┐  ← 同じ位置に2回描画
│     │
└─────┘
└─────┘
```
→ 原因: 同じdetectionが2回描画されている（バグ）

---

## 🔧 推奨される解決策

### 解決策1: 輪郭線の調整（パターンAの場合）

**現在のコード**:
```typescript
// 塗りつぶし
ctx.fill()

// 輪郭線
ctx.strokeStyle = color
ctx.lineWidth = 2.5
ctx.stroke()
```

**修正案**: 輪郭線を削除または細くする
```typescript
// 塗りつぶしのみ（輪郭線なし）
ctx.fill()

// または輪郭線を細く
ctx.lineWidth = 1.0
ctx.stroke()
```

---

### 解決策2: 描画呼び出しの最適化（パターンCの場合）

**579行のuseEffect**:
```typescript
useEffect(() => {
  if ((skeletonData.length > 0 || toolData.length > 0) && videoRef.current) {
    console.log('Data updated, triggering redraw')
    drawOverlayAtTime(videoRef.current.currentTime)
  }
}, [skeletonData, toolData, drawOverlayAtTime])
```

**問題**:
- skeletonDataとtoolDataの両方が同時に更新されると2回描画
- drawOverlayAtTimeが依存配列にあるため、頻繁に再実行

**修正案**:
```typescript
useEffect(() => {
  // 再生中はRVFC/RAFに任せる
  if (isPlaying) return

  if ((skeletonData.length > 0 || toolData.length > 0) && videoRef.current) {
    drawOverlayAtTime(videoRef.current.currentTime)
  }
}, [skeletonData, toolData, isPlaying])  // drawOverlayAtTimeを削除
```

---

### 解決策3: フレームスキップの改善

**157-159行のロジック**:
```typescript
if (currentFrame === lastDrawnFrameRef.current && !isPlaying) {
  return
}
```

**問題**: 再生中は毎回描画される

**修正案**:
```typescript
if (currentFrame === lastDrawnFrameRef.current) {
  // 再生中でも同じフレームはスキップ
  return
}
```

---

## 🧪 デバッグ方法

### ブラウザコンソールでの確認

1. **描画回数のカウント**:
```typescript
// drawOverlayAtTimeの最初に追加
console.log(`[Draw] Frame ${currentFrame}, Time ${currentTimestamp.toFixed(3)}`)
```

2. **detection数の確認**:
```typescript
// 270行の前に追加
console.log(`[Detections] Frame ${currentFrame}: ${tools?.detections?.length || 0} detections`)
```

3. **各detectionの詳細**:
```typescript
// 271行のループ内に追加
console.log(`  Detection ${detection.id}: bbox=${detection.bbox}, contour=${detection.contour?.length || 0} points`)
```

---

## 📝 次のステップ

1. **ユーザーに確認**:
   - 「二重」の具体的な見え方（パターンA/B/C）
   - ブラウザのコンソールログ
   - スクリーンショット

2. **一時的な修正**:
   - 輪郭線を削除してテスト（解決策1）
   - 描画呼び出しを最適化（解決策2）

3. **根本的な修正**:
   - 描画ロジックの統一
   - useEffectの依存関係整理
   - フレームスキップの改善

---

## 🎓 設計上の考察

### 現在の設計意図
- **塗りつぶし**: 器具の形状を視覚的に表示
- **輪郭線**: 形状の境界を明確化
- **ラベル**: 器具名と信頼度を表示

### 視覚的な改善案
1. **輪郭線を削除**: 塗りつぶしのみでシンプルに
2. **透明度を調整**: 35% → 50%でより目立たせる
3. **色を変更**: 紫 → 青/緑など視認性の高い色

---

**調査者**: Claude Code
**最終更新**: 2025-10-18 22:50
**ステータス**: 🔍 **調査完了、ユーザー確認待ち**
