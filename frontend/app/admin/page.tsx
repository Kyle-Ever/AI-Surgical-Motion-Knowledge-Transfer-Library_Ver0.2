"use client"

import { useState, useEffect } from "react"
import { useAdminConfig, MetricsConfig } from "@/hooks/useAdminConfig"
import { RotateCcw, Save, ChevronDown, ChevronRight, AlertCircle, CheckCircle, Info } from "lucide-react"

// --- パラメータ定義 ---

interface ParamDef {
  key: string
  label: string
  description: string
  min: number
  max: number
  step: number
  unit?: string
  /** 影響先の指標（閾値・スコアリング用） */
  affects?: {
    metric: string           // e.g. "B1" "A2"
    color: string            // Tailwind badge色
    detail: string           // 詳しい影響説明
  }
}

const WEIGHT_PARAMS_A: ParamDef[] = [
  { key: "a1", label: "A1: 動作経済性", description: "総移動距離ベースの効率性 (ICSAD検証済み)", min: 0, max: 1, step: 0.05,
    affects: { metric: "A1", color: "bg-blue-100 text-blue-700", detail: "【指標の意味】手技中の左右の手の総移動距離を評価。熟練した術者は移動距離が短い。ICSADの3大指標の一つ (Oropesa et al. 2013)。\n【重みの効果】値を上げる → A1が総合スコアに与える影響が大きくなる。動作の効率性をより重視した評価になります。A1+A2+A3の合計は1.0にしてください。" } },
  { key: "a2", label: "A2: 動作滑らかさ", description: "SPARC — スペクトル弧長 (Balasubramanian 2012)", min: 0, max: 1, step: 0.05,
    affects: { metric: "A2", color: "bg-indigo-100 text-indigo-700", detail: "【指標の意味】SPARC（Spectral Arc Length）で動作の滑らかさを定量化。滑らかな動き＝高スコア。スムースネス評価のゴールドスタンダード (Balasubramanian et al. 2012)。\n【重みの効果】値を上げる → A2が総合スコアに与える影響が大きくなる。動きの滑らかさをより重視した評価になります。" } },
  { key: "a3", label: "A3: 両手協調性", description: "速度相関 + 片手保持安定性フォールバック (GOALS準拠)", min: 0, max: 1, step: 0.05,
    affects: { metric: "A3", color: "bg-cyan-100 text-cyan-700", detail: "【指標の意味】両手検出時は速度相関＋バランスで評価。片手のみの場合は保持手の安定性で評価。片手で組織保持＋他方で操作する手技にも対応 (Vassiliou et al. 2005)。\n【重みの効果】値を上げる → A3が総合スコアに与える影響が大きくなる。両手の連携をより重視した評価になります。" } },
]

const WEIGHT_PARAMS_B: ParamDef[] = [
  { key: "b1", label: "B1: ロスタイム", description: "両手同時停止時間 (D'Angelo 2015準拠)", min: 0, max: 1, step: 0.05,
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【指標の意味】両手とも停止している時間を3段階で分類。片手保持中の停止はカウントしない。3秒超の両手停止＝迷い・計画不足として減点 (D'Angelo et al. 2015)。\n【重みの効果】値を上げる → B1が総合スコアに与える影響が大きくなる。ロスタイムの多さによる減点が大きくなります。B1+B2+B3の合計は1.0にしてください。" } },
  { key: "b2", label: "B2: 動作回数効率", description: "ヒステリシス付き閾値交差カウント (ICSAD準拠)", min: 0, max: 1, step: 0.05,
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【指標の意味】ヒステリシス付き閾値交差で動作回数をカウント。チャタリング防止済み。少ない動作回数＝高効率 (Dosis et al. 2005)。\n【重みの効果】値を上げる → B2が総合スコアに与える影響が大きくなる。無駄な動作回数の多さによる減点が大きくなります。" } },
  { key: "b3", label: "B3: 作業空間偏差", description: "凸包面積ベースの動作範囲 (D'Angelo 2016検証済み)", min: 0, max: 1, step: 0.05,
    affects: { metric: "B3", color: "bg-amber-100 text-amber-700", detail: "【指標の意味】手の移動範囲の凸包面積で作業空間の広さを評価。熟練者は狭い範囲に集中して動作する。path lengthとは独立した情報を提供 (D'Angelo et al. 2016)。\n【重みの効果】値を上げる → B3が総合スコアに与える影響が大きくなる。作業空間の広さによる減点が大きくなります。" } },
]

const WEIGHT_PARAMS_GROUP: ParamDef[] = [
  { key: "group_a", label: "Group A: 動作品質", description: "A1-A3の総合グループ", min: 0, max: 1, step: 0.05,
    affects: { metric: "A", color: "bg-blue-100 text-blue-700", detail: "【効果】値を上げる → 動作品質（経済性・滑らかさ・協調性）が総合スコアにより大きく影響します。値を下げる → ムダ検出（ロスタイム・動作回数・作業空間）の比重が相対的に増えます。Group A + Group B = 1.0 にしてください。" } },
  { key: "group_b", label: "Group B: ムダ検出", description: "B1-B3の総合グループ", min: 0, max: 1, step: 0.05,
    affects: { metric: "B", color: "bg-red-100 text-red-700", detail: "【効果】値を上げる → ムダ検出（ロスタイム・動作回数・作業空間）が総合スコアにより大きく影響します。値を下げる → 動作品質（経済性・滑らかさ・協調性）の比重が相対的に増えます。Group A + Group B = 1.0 にしてください。" } },
]

const ADAPTIVE_PARAMS: ParamDef[] = [
  { key: "idle_percentile", label: "停止判定の百分位数", description: "速度分布のこ��百分位数以下を停止と判定", min: 1, max: 50, step: 1, unit: "%ile",
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【効果】上げる → より多くのフレームが停止判定される → ロスタイムが増加 → B1スコアが下がる。下げる → 非常に低速のフレームのみ停止判定 → B1スコアが上がる。デフォルトP15推奨。" } },
  { key: "movement_percentile", label: "動作検出の百分位数", description: "速度分布のこの百分位数を動作開始閾値に", min: 1, max: 50, step: 1, unit: "%ile",
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【効果】上げる → 動作開始閾値が高くなる → 小さな動きが無視される → 動作カウントが減る → B2スコアが上がる。下げる → 動作���ウントが増えやすい → B2スコアが下がる。デフォルトP30推奨。" } },
]

const THRESHOLD_PARAMS: ParamDef[] = [
  { key: "idle_velocity_threshold", label: "停止速度閾値（正規化）", description: "両手ともこの速度以下で停止と判定（D'Angelo 2015準拠）", min: 0.001, max: 0.05, step: 0.001,
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【効果】上げる → 停止と判定されるフレームが増える → ロスタイムが増加 → B1スコアが下がる。下げる → 停止判定が厳しくなる → ロスタイムが減少 → B1スコアが上がる。片手のみ停止（保持）はカウントされません。正規化座標の動画に適用。" } },
  { key: "idle_velocity_threshold_pixel", label: "停止速度閾値（ピクセル）", description: "ピクセル座標時の両手同時停止閾値", min: 1, max: 50, step: 0.5, unit: "px/frame",
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【効果】上げる → 停止判定が緩くなる → ロスタイムが増加 → B1スコアが下がる。下げる → 停止判定が厳しくなる → B1スコアが上がる。ピクセル座標の動画で使用。片手保持中の停止はカウントされません。" } },
  { key: "micro_pause_max_sec", label: "マイクロポーズ上限", description: "この秒数未満の両手停止はペナルティなし", min: 0.1, max: 5, step: 0.1, unit: "秒",
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【効果】上げる → 短い停止がペナルティ対象外になる → B1スコアが上がる（甘い評価）。下げる → 短い停止もペナルティ対象になる → B1スコアが下がる（厳しい評価）。" } },
  { key: "check_pause_max_sec", label: "確認停止上限", description: "この秒数を超える両手停止はロスタイム", min: 1, max: 10, step: 0.5, unit: "秒",
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【効果】上げる → ロスタイム判定が緩くなる → 長い停止も「確認停止（出血チェック等）」扱いになる → B1スコアが上がる。下げる → 短い停止でもロスタイム扱い → B1スコアが下がる。" } },
  { key: "movement_velocity_threshold", label: "動作検出閾値（正規化）", description: "ヒステリシス付き動作開始の上昇閾値", min: 0.001, max: 0.05, step: 0.001,
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【効果】上げる → 小さな動きが無視される → 動作カウントが減る → B2スコアが上がる。下げる → 細かい動きもカウントされる → 動作回数が増える → B2スコアが下がる。動作終了判定はこの値×ヒステリシス係数。" } },
  { key: "movement_velocity_threshold_pixel", label: "動作検出閾値（ピクセル）", description: "ピクセル座標時のヒステリシス付き動作閾値", min: 1, max: 50, step: 0.5, unit: "px/frame",
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【効果】上げる → 小さな動きが無視される → 動作カウントが減る → B2スコアが上がる。下げる → 動作カウントが増える → B2スコアが下がる。ピクセル座標の動画で使用。" } },
  { key: "smoothing_window", label: "平滑化ウィンドウ", description: "移動平均のフレーム数（奇数）", min: 3, max: 15, step: 2, unit: "frames",
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【効果】上げる → ノイズが除去され動作カウントが安定するが、短い動作を検出しにくくなる → B2スコアがやや上がる。下げる → 細かいノイズにも反応しやすくなる → 動作カウントが増えやすい → B2スコアが下がる。" } },
  { key: "hysteresis_ratio", label: "ヒステリシス係数", description: "動作終了判定の下降閾値 = 上昇閾値 × この係数", min: 0.3, max: 0.95, step: 0.05,
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【効果】上げる（1.0に近づける） → 上昇・下降閾値の差が小さくなる → チャタリングが起きやすくなる → 動作カウントが増えやすい → B2スコアが下がる。下げる → ヒステリシス幅が広がる → チャタリング抑制が強まる → 動作カウントが安定。デフォルト0.7推奨。" } },
]

const SCORING_PARAMS: ParamDef[] = [
  { key: "a1_max_path_pixel", label: "A1: 最大パス長（ピクセル）", description: "この値でスコア0点", min: 1000, max: 200000, step: 1000, unit: "px",
    affects: { metric: "A1", color: "bg-blue-100 text-blue-700", detail: "【効果】上げる → 0点のラインが遠くなる → A1スコアが上がりやすくなる（甘い評価）。下げる → 少ない移動距離でも0点に近づく → A1スコアが下がりやすくなる（厳しい評価）。ピクセル座標の動画に適用。" } },
  { key: "a1_max_path_normalized", label: "A1: 最大パス長（正規化）", description: "正規化座標時の上限", min: 1, max: 50, step: 0.5,
    affects: { metric: "A1", color: "bg-blue-100 text-blue-700", detail: "【効果】上げる → A1スコアが上がりやすくなる（甘い評価）。下げる → A1スコアが下がりやすくなる（厳しい評価）。正規化座標の動画に適用。" } },
  { key: "a2_sparc_min", label: "A2: SPARC下限", description: "この値でスコア0点（ぎこちない）", min: -15, max: -2, step: 0.5,
    affects: { metric: "A2", color: "bg-indigo-100 text-indigo-700", detail: "【効果】下げる（例: -7→-10） → 0点のラインが遠くなる → ぎこちない動きでもスコアが出やすくなる → A2が甘い評価に。上げる（例: -7→-4） → 少しのぎこちなさでも0点に近づく → A2が厳しい評価に。" } },
  { key: "a2_sparc_max", label: "A2: SPARC上限", description: "この値でスコア100点（滑らか）", min: -5, max: 0, step: 0.1,
    affects: { metric: "A2", color: "bg-indigo-100 text-indigo-700", detail: "【効果】上げる（例: -1→0） → 100点を取りにくくなる → A2が厳しい評価に。下げる（例: -1→-2） → 100点を取りやすくなる → A2が甘い評価に。" } },
  { key: "a3_both_hands_min_ratio", label: "A3: 両手検出最低比率", description: "これ以下は片手保持安定性で評価", min: 0.05, max: 0.8, step: 0.05,
    affects: { metric: "A3", color: "bg-cyan-100 text-cyan-700", detail: "【効果】上げる → 「片手保持安定性」モードに切り替わりやすくなる（片手操作の手技で有利）。下げる → 両手速度相関モードが多く適用される。片手保持モードでは保持手の位置安定性で評価。データ完全不足時のみN/A。" } },
  { key: "a3_correlation_weight", label: "A3: 相関重み（両手モード時）", description: "速度相互相関の重み（両手検出時のみ使用）", min: 0, max: 1, step: 0.05,
    affects: { metric: "A3", color: "bg-cyan-100 text-cyan-700", detail: "【効果】上げる → 左右の動きのタイミング同期をより重視。下げる → 速度バランス（均等さ）をより重視。バランス重みと合わせて1.0にしてください。片手保持モード時は使用されません。" } },
  { key: "a3_balance_weight", label: "A3: バランス重み（両手モード時）", description: "速度バランスの重み（両手検出時のみ使用）", min: 0, max: 1, step: 0.05,
    affects: { metric: "A3", color: "bg-cyan-100 text-cyan-700", detail: "【効果】上げる → 左右の手の速度の均等さをより重視。下げる → タイミング同期（相関）をより重視。相関重みと合わせて1.0にしてください。片手保持モード時は使用されません。" } },
  { key: "b1_max_idle_ratio", label: "B1: 最大アイドル比率", description: "ロスタイム比率がこの値でスコア0点", min: 0.01, max: 1.0, step: 0.01,
    affects: { metric: "B1", color: "bg-red-100 text-red-700", detail: "【効果】上げる → 0点のラインが遠くなる → 多くのロスタイムが許容される → B1スコアが上がりやすい（甘い評価）。下げる（例: 0.30→0.05） → 少しのロスタイムでも大きく減点される → B1スコアが下がりやすい（厳しい評価）。デフォルト0.30は甘めです。" } },
  { key: "b2_max_movements_per_minute", label: "B2: 最大動作回数/分", description: "動作回数がこの値でスコア0点", min: 5, max: 200, step: 5, unit: "回/分",
    affects: { metric: "B2", color: "bg-orange-100 text-orange-700", detail: "【効果】上げる → 多くの動作回数が許容される → B2スコアが上がりやすい（甘い評価）。下げる（例: 60→15） → 少ない動作回数でもスコアが低くなる → B2スコアが下がりやすい（厳しい評価）。デフォルト60は甘めです。" } },
  { key: "b3_max_area_pixel", label: "B3: 最大面積（ピクセル）", description: "凸包面積がこの値でスコア0点", min: 10000, max: 2000000, step: 10000, unit: "px\u00B2",
    affects: { metric: "B3", color: "bg-amber-100 text-amber-700", detail: "【効果】上げる → 広い作業空間が許容される → B3スコアが上がりやすい（甘い評価）。下げる → 狭い範囲でも0点に近づく → B3スコアが下がりやすい（厳しい評価）。ピクセル座標の動画に適用。" } },
  { key: "b3_max_area_normalized", label: "B3: 最大面積（正規化）", description: "正規化座標時の面積上限", min: 0.01, max: 1.0, step: 0.01,
    affects: { metric: "B3", color: "bg-amber-100 text-amber-700", detail: "【効果】上げる → B3スコアが上がりやすい（甘い評価）。下げる → B3スコアが下がりやすい（厳しい評価）。正規化座標の動画に適用。" } },
]

const SPARC_PARAMS: ParamDef[] = [
  { key: "freq_cutoff_hz", label: "FFTカットオフ周波数", description: "SPARC計算の周波数上限", min: 5, max: 50, step: 1, unit: "Hz",
    affects: { metric: "A2", color: "bg-indigo-100 text-indigo-700", detail: "【効果】上げる → 高周波ノイズも評価対象になる → スペクトル弧長が長くなる → A2スコアが下がりやすい（厳しい評価）。下げる → 低周波のみ評価される → A2スコアが上がりやすい（甘い評価）。デフォルト20Hz推奨。" } },
  { key: "amplitude_threshold", label: "振幅閾値", description: "適応カットオフの閾値", min: 0.01, max: 0.2, step: 0.01,
    affects: { metric: "A2", color: "bg-indigo-100 text-indigo-700", detail: "【効果】上げる → 低い振幅でもカットオフされる → 低周波のみ評価 → A2スコアが上がりやすい（甘い評価）。下げる → より高い周波数まで評価対象 → A2スコアが下がりやすい（厳しい評価）。" } },
]

// --- コンポーネント ---

function WeightSum({ values, keys }: { values: Record<string, number>; keys: string[] }) {
  const sum = keys.reduce((acc, k) => acc + (values[k] || 0), 0)
  const isValid = Math.abs(sum - 1.0) <= 0.01
  return (
    <span className={`text-sm font-mono ml-2 font-semibold ${isValid ? "text-emerald-600" : "text-red-600"}`}>
      (合計: {sum.toFixed(2)})
    </span>
  )
}

function Section({
  title,
  children,
  defaultOpen = false,
}: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-5 py-3.5 bg-gray-50 hover:bg-gray-100 text-left font-semibold text-gray-800 transition-colors"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
        {title}
      </button>
      {open && <div className="p-5 space-y-4 bg-white">{children}</div>}
    </div>
  )
}

function Tooltip({ content, children }: { content: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 px-3 py-2.5 text-xs leading-relaxed text-gray-700 bg-white border border-gray-200 rounded-lg shadow-lg pointer-events-none">
          {content}
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-white" />
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-200" />
        </span>
      )}
    </span>
  )
}

function ParamSlider({
  param,
  value,
  defaultValue,
  onChange,
}: {
  param: ParamDef
  value: number
  defaultValue?: number
  onChange: (val: number) => void
}) {
  const isChanged = defaultValue !== undefined && Math.abs(value - defaultValue) > Number.EPSILON
  const percent = ((value - param.min) / (param.max - param.min)) * 100

  return (
    <div className="py-3 border-b border-gray-100 last:border-0">
      <div className="flex items-baseline justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">{param.label}</span>
          {param.affects && (
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${param.affects.color}`}>
              {param.affects.metric}
            </span>
          )}
          {param.affects && (
            <Tooltip content={param.affects.detail}>
              <Info className="w-3.5 h-3.5 text-gray-400 hover:text-blue-500 cursor-help transition-colors" />
            </Tooltip>
          )}
          {isChanged && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" title="変更あり" />
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="number"
            value={value}
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              if (!isNaN(v)) onChange(v)
            }}
            min={param.min}
            max={param.max}
            step={param.step}
            className="w-24 px-2 py-1 text-sm bg-white border border-gray-300 rounded-md text-gray-800 text-right font-mono focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
          {param.unit && <span className="text-xs text-gray-500 min-w-[3rem]">{param.unit}</span>}
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-2">
        {param.description}
        {defaultValue !== undefined && (
          <span className="ml-1 text-gray-400">
            (default: {defaultValue})
          </span>
        )}
      </p>
      <div className="relative">
        <input
          type="range"
          min={param.min}
          max={param.max}
          step={param.step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="admin-slider w-full"
          style={{
            background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${percent}%, #e5e7eb ${percent}%, #e5e7eb 100%)`
          }}
        />
        <div className="flex justify-between text-[10px] text-gray-400 mt-0.5 px-0.5">
          <span>{param.min}</span>
          <span>{param.max}</span>
        </div>
      </div>
    </div>
  )
}

export default function AdminPage() {
  const { config, defaults, isLoading, isSaving, error, saveSuccess, saveConfig, resetConfig } = useAdminConfig()
  const [draft, setDraft] = useState<MetricsConfig | null>(null)

  useEffect(() => {
    if (config) setDraft(structuredClone(config))
  }, [config])

  if (isLoading || !draft || !defaults) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-gray-500 text-sm">設定を読み込み中...</div>
      </div>
    )
  }

  const updateWeight = (key: string, val: number) => {
    setDraft((d) => d ? { ...d, weights: { ...d.weights, [key]: val } } : d)
  }
  const updateThreshold = (key: string, val: number | boolean) => {
    setDraft((d) => d ? { ...d, thresholds: { ...d.thresholds, [key]: val } } : d)
  }
  const updateScoring = (key: string, val: number) => {
    setDraft((d) => d ? { ...d, scoring: { ...d.scoring, [key]: val } } : d)
  }
  const updateSparc = (key: string, val: number) => {
    setDraft((d) => d ? { ...d, sparc: { ...d.sparc, [key]: val } } : d)
  }

  const handleSave = async () => {
    if (!draft) return
    try {
      await saveConfig(draft)
    } catch {
      // error is set in the hook
    }
  }

  const handleReset = async () => {
    if (!confirm("すべてのパラメータをデフォルト値に戻しますか？")) return
    await resetConfig()
  }

  return (
    <div className="min-h-screen" style={{ background: '#ffffff', colorScheme: 'light' }}>
      <style jsx global>{`
        /* 管理者パネル: 親レイアウトの背景をオーバーライド */
        .app-main:has(.admin-panel),
        .app-layout:has(.admin-panel),
        .app-shell:has(.admin-panel) {
          background: #ffffff !important;
        }
        .admin-slider {
          -webkit-appearance: none;
          appearance: none;
          height: 6px;
          border-radius: 3px;
          outline: none;
          cursor: pointer;
        }
        .admin-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #3b82f6;
          border: 2px solid white;
          box-shadow: 0 1px 3px rgba(0,0,0,0.2);
          cursor: pointer;
          transition: box-shadow 0.15s;
        }
        .admin-slider::-webkit-slider-thumb:hover {
          box-shadow: 0 0 0 4px rgba(59,130,246,0.15), 0 1px 3px rgba(0,0,0,0.2);
        }
        .admin-slider::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #3b82f6;
          border: 2px solid white;
          box-shadow: 0 1px 3px rgba(0,0,0,0.2);
          cursor: pointer;
        }
      `}</style>

      <div className="admin-panel max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* ヘッダ */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">管理者パネル</h1>
            <p className="text-sm text-gray-500 mt-1">6指標のパラメータ・感度を調整できます。各指標は学術的に検証された手法に基づいています。変更は新規解析から適用されます。</p>
          </div>
          <button
            onClick={handleReset}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg disabled:opacity-50 transition-colors shadow-sm"
          >
            <RotateCcw className="w-4 h-4" />
            デフォルトに戻す
          </button>
        </div>

        {/* メッセージ */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}
        {saveSuccess && (
          <div className="flex items-center gap-2 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm">
            <CheckCircle className="w-4 h-4 shrink-0" />
            設定を保存しました
          </div>
        )}

        {/* セクション */}
        <Section title="重み設定 (Weights)" defaultOpen={true}>
          <div className="space-y-5">
            <div>
              <h3 className="text-sm font-semibold text-blue-700 mb-3">
                Group A: 動作品質
                <WeightSum values={draft.weights} keys={["a1", "a2", "a3"]} />
              </h3>
              {WEIGHT_PARAMS_A.map((p) => (
                <ParamSlider
                  key={p.key}
                  param={p}
                  value={(draft.weights as any)[p.key]}
                  defaultValue={(defaults.weights as any)[p.key]}
                  onChange={(v) => updateWeight(p.key, v)}
                />
              ))}
            </div>
            <hr className="border-gray-200" />
            <div>
              <h3 className="text-sm font-semibold text-rose-700 mb-3">
                Group B: ムダ検出
                <WeightSum values={draft.weights} keys={["b1", "b2", "b3"]} />
              </h3>
              {WEIGHT_PARAMS_B.map((p) => (
                <ParamSlider
                  key={p.key}
                  param={p}
                  value={(draft.weights as any)[p.key]}
                  defaultValue={(defaults.weights as any)[p.key]}
                  onChange={(v) => updateWeight(p.key, v)}
                />
              ))}
            </div>
            <hr className="border-gray-200" />
            <div>
              <h3 className="text-sm font-semibold text-violet-700 mb-3">
                総合グループ
                <WeightSum values={draft.weights} keys={["group_a", "group_b"]} />
              </h3>
              {WEIGHT_PARAMS_GROUP.map((p) => (
                <ParamSlider
                  key={p.key}
                  param={p}
                  value={(draft.weights as any)[p.key]}
                  defaultValue={(defaults.weights as any)[p.key]}
                  onChange={(v) => updateWeight(p.key, v)}
                />
              ))}
            </div>
          </div>
        </Section>

        <Section title="閾値設定 (Thresholds)">
          {/* 適応的閾値トグル */}
          <div className="pb-3 mb-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-gray-800">適応的閾値モード</span>
                <p className="text-xs text-gray-500 mt-0.5">
                  ONにすると、動画ごとの速度分布に基づいて停止・動作検出閾値を自���調整し��す。
                  OFFの場合は下の固定閾値を使用します。
                </p>
              </div>
              <button
                type="button"
                onClick={() => updateThreshold("adaptive_threshold", !draft.thresholds.adaptive_threshold)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  draft.thresholds.adaptive_threshold ? "bg-blue-600" : "bg-gray-300"
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow ${
                  draft.thresholds.adaptive_threshold ? "translate-x-6" : "translate-x-1"
                }`} />
              </button>
            </div>
          </div>

          {/* 適応的閾値パラメータ（ONの場合のみ表示） */}
          {draft.thresholds.adaptive_threshold && (
            <div className="pb-3 mb-3 border-b border-blue-200 bg-blue-50/50 -mx-5 px-5 py-3 rounded">
              <h4 className="text-xs font-semibold text-blue-700 mb-2">適応的閾値パラメータ（百分位数ベース）</h4>
              <p className="text-xs text-blue-600 mb-3">
                速度分布の百分位数で閾値を決定。固定閾値は下限として機能します。
              </p>
              {ADAPTIVE_PARAMS.map((p) => (
                <ParamSlider
                  key={p.key}
                  param={p}
                  value={(draft.thresholds as any)[p.key]}
                  defaultValue={(defaults.thresholds as any)[p.key]}
                  onChange={(v) => updateThreshold(p.key, v)}
                />
              ))}
            </div>
          )}

          {/* 固定閾値パラメータ */}
          <h4 className="text-xs font-semibold text-gray-500 mb-2">
            {draft.thresholds.adaptive_threshold ? "固定閾値（下限として使用）" : "固定閾値"}
          </h4>
          {THRESHOLD_PARAMS.map((p) => (
            <ParamSlider
              key={p.key}
              param={p}
              value={(draft.thresholds as any)[p.key]}
              defaultValue={(defaults.thresholds as any)[p.key]}
              onChange={(v) => updateThreshold(p.key, v)}
            />
          ))}
        </Section>

        <Section title="スコアリング範囲 (Scoring)">
          {SCORING_PARAMS.map((p) => (
            <ParamSlider
              key={p.key}
              param={p}
              value={(draft.scoring as any)[p.key]}
              defaultValue={(defaults.scoring as any)[p.key]}
              onChange={(v) => updateScoring(p.key, v)}
            />
          ))}
        </Section>

        <Section title="SPARC パラメータ">
          {SPARC_PARAMS.map((p) => (
            <ParamSlider
              key={p.key}
              param={p}
              value={(draft.sparc as any)[p.key]}
              defaultValue={(defaults.sparc as any)[p.key]}
              onChange={(v) => updateSparc(p.key, v)}
            />
          ))}
        </Section>

        {/* 保存ボタン */}
        <div className="sticky bottom-0 py-4 bg-white/90 backdrop-blur-sm border-t border-gray-200 -mx-6 px-6">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 transition-colors shadow-sm"
          >
            <Save className="w-4 h-4" />
            {isSaving ? "保存中..." : "設定を保存"}
          </button>
        </div>
      </div>
    </div>
  )
}
