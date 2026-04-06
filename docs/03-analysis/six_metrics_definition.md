# MindMotionAI 6指標メトリクス定義書

## 概要

MindMotionAIは、手術動画から術者の手の動きを追跡し、6つの運動学的指標（kinematic metrics）でパフォーマンスを定量評価します。各指標は外科教育・技術評価の学術研究に基づいて設計されており、臨床的な納得性と再現性を重視しています。

6指標は **2グループ** に分かれ、それぞれ50%の重みで総合スコア（0-100点）に統合されます。

| グループ | 指標 | 観点 |
|---------|------|------|
| **A: 動作品質** | A1: 動作経済性 | どれだけ無駄なく手を動かしたか |
| | A2: 動作滑らかさ | どれだけ滑らかに手を動かしたか |
| | A3: 両手協調性 | 両手が適切に連携しているか |
| **B: ムダ検出** | B1: ロスタイム | どれだけ手が止まっていたか |
| | B2: 動作回数効率 | 動作の回数が適切か |
| | B3: 作業空間偏差 | 手の移動範囲が適切か |

---

## A1: 動作経済性（Economy of Motion）

### 何を測るか
手技中の左右の手の**総移動距離**です。熟練した術者は必要最小限の動きで手技を完了するため、移動距離が短くなります。

### 学術的根拠
- **ICSAD（Imperial College Surgical Assessment Device）** の3大指標の一つとして、path lengthは最も初期から検証されてきたkinematic metricです
  - Dosis A et al. "Synchronized video and motion analysis for the assessment of procedures in the operating theater." *Archives of Surgery*, 2005
- **妥当性の検証**: 腹腔鏡技術評価のレビューで「time, path length, number of movements」が有効なパラメータとして確認されています
  - Oropesa I et al. *Surgical Endoscopy*, 2013 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/23233011/))
- **JIGSAWSベンチマーク** でもpath lengthは標準的な運動学的特徴量として使用されています
  - Ahmidi N et al. *IEEE Trans Biomed Eng*, 2017 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5559351/))

### 計算ロジック
1. 各フレームで左右の手首位置（x, y）を取得
2. 連続フレーム間のユークリッド距離を累積: `path = Σ√((x_i - x_{i-1})² + (y_i - y_{i-1})²)`
3. 左手パス長 + 右手パス長 = 総移動距離

### スコア変換
- **相対評価**（エキスパート基準値あり）: `score = max(0, min(100, (2.0 - 実測値/基準値) × 100))`
  - 基準値と同じ → 100点、基準値の2倍 → 0点
- **絶対評価**（基準値なし）: 最大パス長に対する比率で線形変換

---

## A2: 動作滑らかさ（SPARC — Spectral Arc Length）

### 何を測るか
手の動きの**滑らかさ**です。熟練した術者は無駄のない滑らかな動作を行い、未熟な術者は停止・再開を繰り返すぎこちない動きになります。

### 学術的根拠
SPARCは動作のスムースネスを定量化する指標として**現在のゴールドスタンダード**です。

- **原著論文**: Balasubramanian S, Melendez-Calderon A, Burdet E. "A robust and sensitive metric for quantifying movement smoothness." *IEEE Trans Biomed Eng*, 2012; 59(8):2126-2136 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/22180502/))
- **検証論文**: Balasubramanian S et al. "On the analysis of movement smoothness." *J NeuroEng Rehabil*, 2015; 12:112 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4674971/))
  - 従来のNJ（Normalized Jerk）やLDLJ（Log Dimensionless Jerk）よりSPARCが優れると結論
- **外科応用**: Araujo RL et al. "Motion Smoothness-Based Assessment of Surgical Expertise." *Sensors*, 2023; 23(6):3146 ([MDPI](https://www.mdpi.com/1424-8220/23/6/3146))

### 計算ロジック
1. 各手の速度プロファイルを計算
2. ピーク速度で正規化
3. FFT（高速フーリエ変換）で周波数スペクトルに変換
4. 適応的カットオフ周波数を決定（振幅が閾値0.05を下回る最初の周波数）
5. スペクトルの弧長を計算: `SPARC = -Σ√((Δf)² + (ΔV)²)`
6. 左右の手の平均を算出

### SPARC値の解釈
| SPARC値 | 解釈 |
|---------|------|
| -1.0付近 | 非常に滑らか（理想的な単一ベル型速度プロファイル） |
| -4.0付近 | 中程度 |
| -7.0付近 | 非常にぎこちない（多数のサブムーブメント） |

### スコア変換
- **相対評価**: `score = max(0, min(100, (2.0 - |SPARC実測|/|SPARC基準|) × 100))`
- **絶対評価**: -7.0（0点）〜 -1.0（100点）の線形マッピング

---

## A3: 両手協調性（Bimanual Coordination）

### 何を測るか
左右の手が**適切に連携して動いているか**を評価します。手術では、両手が同期して動く場面と、片手が組織を保持（静止）し他方が操作する場面の両方があります。本指標はどちらのパターンも正しく評価します。

### 学術的根拠
- **GOALSフレームワーク** の5評価項目の一つに "bimanual dexterity" が含まれています
  - Vassiliou MC et al. "A global assessment tool for evaluation of intraoperative laparoscopic skills." *Am J Surg*, 2005; 190(1):107-113 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/15972181/))
- **速度相互相関** はロボット手術の技術評価で使用されています
  - Judkins T, Oleynikov D, Stergiou N. "Objective evaluation of expert and novice performance during robotic surgical training tasks." *Surg Endosc*, 2009
- **最新研究** ではDynamic Time Warping (DTW) による両手協調評価が提案されています
  - "A new approach to laparoscopic skill assessment: Motion smoothness and bimanual coordination." *Surgery*, 2025 ([ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2468900925000246))

### 計算ロジック

#### モード1: 両手協調モード（両手が十分に検出されている場合）
両手の検出率が閾値（デフォルト30%）以上の場合に適用。

1. **速度相互相関**（重み60%）: 左右の速度プロファイルのPearson相関係数
2. **速度バランス**（重み40%）: 各フレームで `min(左速度, 右速度) / max(左速度, 右速度)` の平均
3. `coordination = 0.60 × max(0, correlation) + 0.40 × balance`

#### モード2: 片手保持安定性（フォールバック）
両手の検出率が閾値未満、または片手のみ検出されている場合に適用。手術では片手が組織保持のために静止しているのは正常な手技パターンです。

1. 速度が低い方の手を「保持手」と推定
2. 保持手の**位置分散**を計算（x分散 + y分散）
3. 分散が小さい = 安定した保持 = 高スコア: `stability = 1.0 - variance / max_variance`

### スコア変換
- coordination_value / stability（0〜1）を0〜100にスケール
- 両モードとも同じスケールで統一的にスコア化

---

## B1: ロスタイム（Lost Time — 両手同時停止）

### 何を測るか
**両手とも動いていない時間**（idle time）を検出し、その長さに応じて3段階に分類します。片手が保持のために静止している場合はロスタイムとしてカウントしません。

### 学術的根拠
- **D'Angelo AL et al.** "Idle time: an underdeveloped performance metric for assessing surgical skill." *Am J Surg*, 2015; 209(4):645-651 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4412306/))
  - 「両手が動いていない時間」を運動計画・意思決定の時間として定量化。**技術レベルと有意に相関**することを実証
- **D'Angelo AL et al.** "Use of sensors to quantify procedural idle time: Validity evidence for a new mastery metric." *Surgery*, 2019 ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0039606019306725))
  - Mastery metricとしてのバリデーション

### 計算ロジック
1. 各フレームで**左右それぞれ**の速度を閾値と比較
2. **両手とも閾値以下**の連続区間を検出（片手のみ停止は除外）
3. 3段階に分類:

| 分類 | 継続時間 | 解釈 | スコアへの影響 |
|------|---------|------|------------|
| マイクロポーズ | < 1秒 | 正常な動作間の微小停止 | なし |
| 確認停止 | 1〜3秒 | 出血確認、視野確認など臨床的に正当 | 参考情報のみ |
| **ロスタイム** | > 3秒 | 迷い、計画不足、躊躇 | **スコア減点対象** |

4. `lost_time_ratio = ロスタイム合計秒数 / 総手技時間`

### スコア変換
- **相対評価**: `score = max(0, min(100, (2.0 - 実測ratio/基準ratio) × 100))`
- **絶対評価**: `score = max(0, min(100, (1.0 - lost_ratio / 0.30) × 100))`

---

## B2: 動作回数効率（Movement Count — ヒステリシス付き閾値交差）

### 何を測るか
手技中の**離散的な動作の回数**を測定します。熟練した術者は少ない動作回数で手技を完了します。

### 学術的根拠
- **ICSADの3大指標**の一つ（time, path length, **number of movements**）
  - Dosis A et al. *Archives of Surgery*, 2005
- 妥当性検証済み
  - Oropesa I et al. *Surgical Endoscopy*, 2013 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/23233011/))

### 計算ロジック
1. 左右の手の速度を平均化（combined velocity）
2. 移動平均（ウィンドウサイズ5フレーム）で平滑化
3. **ヒステリシス付き閾値交差**でカウント:
   - **動作開始**: 速度が上昇閾値（threshold）を超えた時点
   - **動作終了**: 速度が下降閾値（threshold × 0.7）を下回った時点
   - ヒステリシスにより、閾値付近での微振動（チャタリング）による誤カウントを防止
4. `movements_per_minute = (カウント数 / 総時間) × 60`

### なぜヒステリシスが必要か
従来の単一閾値では、速度が閾値付近で微振動すると1回の動作が複数回としてカウントされる問題がありました。上昇閾値と下降閾値を分離することで、信号処理の標準的手法であるチャタリング防止を実現しています。

### スコア変換
- **相対評価**: `score = max(0, min(100, (2.0 - 実測mpm/基準mpm) × 100))`
- **絶対評価**: `score = (1.0 - min(mpm/60, 1.0)) × 100`

---

## B3: 作業空間偏差（Working Volume Deviation）

### 何を測るか
手技中の手の**移動範囲の広さ**を凸包（convex hull）面積として計算します。熟練した術者は必要な範囲に集中して動作するため、作業空間が小さくなります。

### 学術的根拠
- **D'Angelo AL et al.** "Working volume: Validity evidence for a motion based metric of surgical efficiency." *Am J Surg*, 2016; 211(2):445-450 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4724457/))
  - 凸包による作業ボリュームは技術レベルを弁別する有効な指標
  - **指導医 < レジデント < 学生**（線形関係）が確認
  - **path lengthとは独立した情報**を提供（移動距離では捉えられない「空間的広がり」を捕捉）
- **最新の発展**: "Reliability Volume: a novel metric for surgical skill evaluation." *Frontiers in Medicine*, 2025 ([Frontiers](https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2025.1591043/full))

### 計算ロジック
1. 全フレームの左右の手首位置を2D点群として収集
2. 重複点を除去
3. **凸包（Convex Hull）** を計算（scipy.spatial.ConvexHull）
4. 凸包の面積 = 作業空間の広さ
5. 補助情報: バウンディングボックス面積、重心座標

### スコア変換
- **相対評価**（エキスパート基準値あり）:
  - `ratio = 実測面積 / 基準面積`
  - `deviation = |ratio - 1.0|`（1.0からの乖離度）
  - `score = max(0, min(100, (1.0 - deviation) × 100))`
  - **双方向評価**: 広すぎても狭すぎても減点
- **絶対評価**: 最大面積に対する比率で線形変換

---

## 総合スコアの算出

### グループ内の重み配分

| 指標 | Group A重み | 指標 | Group B重み |
|------|-----------|------|-----------|
| A1: 動作経済性 | 0.40 | B1: ロスタイム | 0.40 |
| A2: 動作滑らかさ | 0.35 | B2: 動作回数効率 | 0.30 |
| A3: 両手協調性 | 0.25 | B3: 作業空間偏差 | 0.30 |

### 総合スコア
```
Motion Quality Score = A1×0.40 + A2×0.35 + A3×0.25
Waste Detection Score = B1×0.40 + B2×0.30 + B3×0.30
Overall Score = MQ×0.50 + WD×0.50
```

### A3がN/Aの場合
データ不足でA3が計算不能の場合、A3の重み（0.25）はA1とA2に比例配分されます。

---

## 評価モード

### 絶対評価（Absolute Mode）
エキスパート基準値がない場合に使用。固定の閾値に基づいてスコアを算出します。汎用的ですが、手術の種類や難易度を考慮しません。

### 相対評価（Relative Mode）
エキスパートの実測データを基準値として使用。基準値と同じ値で100点、基準値の2倍で0点となる線形スケールです。手術の種類や施設ごとの特性を反映できます。

---

## 参考文献一覧

1. Balasubramanian S et al. "A robust and sensitive metric for quantifying movement smoothness." *IEEE Trans Biomed Eng*, 2012; 59(8):2126-2136
2. Balasubramanian S et al. "On the analysis of movement smoothness." *J NeuroEng Rehabil*, 2015; 12:112
3. Dosis A et al. "Synchronized video and motion analysis for the assessment of procedures in the operating theater." *Arch Surg*, 2005
4. Oropesa I et al. "Is motion analysis a valid tool for assessing laparoscopic skill?" *Surg Endosc*, 2013
5. Ahmidi N et al. "A Dataset and Benchmarks for Segmentation and Recognition of Gestures in Robotic Surgery." *IEEE Trans Biomed Eng*, 2017; 64(9):2025-2041
6. Vassiliou MC et al. "A global assessment tool for evaluation of intraoperative laparoscopic skills." *Am J Surg*, 2005; 190(1):107-113
7. D'Angelo AL et al. "Idle time: an underdeveloped performance metric for assessing surgical skill." *Am J Surg*, 2015; 209(4):645-651
8. D'Angelo AL et al. "Use of sensors to quantify procedural idle time: Validity evidence for a new mastery metric." *Surgery*, 2019
9. D'Angelo AL et al. "Working volume: Validity evidence for a motion based metric of surgical efficiency." *Am J Surg*, 2016; 211(2):445-450
10. Martin JA et al. "Objective structured assessment of technical skill (OSATS) for surgical residents." *Br J Surg*, 1997; 84(2):273-278
11. Goh AC et al. "Global evaluative assessment of robotic skills: validation of a clinical assessment tool." *J Urol*, 2012; 187:247-252
12. Araujo RL et al. "Motion Smoothness-Based Assessment of Surgical Expertise." *Sensors*, 2023; 23(6):3146
13. Gao Y et al. "JHU-ISI Gesture and Skill Assessment Working Set (JIGSAWS)." *MICCAI Workshop*, 2014

---

*本ドキュメントは MindMotionAI v0.1 の指標定義を記載しています。各指標のパラメータは管理者パネルから調整可能です。*
