'use client'

import React, { useState, useEffect } from 'react'
import { Settings, Eye, Play, Pause, Columns } from 'lucide-react'
import { useReferenceModels } from '@/hooks/useScoring'
import { api } from '@/lib/api'

interface ReferenceVideoInfo {
  videoId: string
  videoUrl: string
  modelName: string
  surgeonName?: string
  surgeryType?: string
  ratios?: Record<string, number>  // metric_name -> ratio_to_expert
}

interface ComparisonSettingsPanelProps {
  analysisId: string
  videoType?: string
  totalFrames?: number
  detectionRate?: { left: number; right: number }
  evaluationMode?: string
  onReferenceSelect?: (modelId: string) => void
  selectedReferenceId?: string | null
  sixMetrics?: any  // 相対評価後のスコアデータ
  onDualVideoMode?: () => void  // 横並び表示切替
  className?: string
}

const ComparisonSettingsPanel: React.FC<ComparisonSettingsPanelProps> = ({
  analysisId,
  videoType,
  totalFrames,
  detectionRate,
  evaluationMode = 'absolute',
  onReferenceSelect,
  selectedReferenceId,
  sixMetrics,
  onDualVideoMode,
  className = '',
}) => {
  const { models, isLoading: modelsLoading } = useReferenceModels()
  const [refVideoInfo, setRefVideoInfo] = useState<ReferenceVideoInfo | null>(null)
  const [miniPlaying, setMiniPlaying] = useState(false)
  const miniVideoRef = React.useRef<HTMLVideoElement>(null)

  // 基準モデル選択時に動画情報を取得
  useEffect(() => {
    if (!selectedReferenceId) {
      setRefVideoInfo(null)
      return
    }

    const fetchRefVideo = async () => {
      try {
        const refRes = await api.get(`/scoring/reference/${selectedReferenceId}`)
        const refModel = refRes.data
        if (refModel?.analysis_id) {
          const analysisRes = await api.get(`/analysis/${refModel.analysis_id}`)
          if (analysisRes.data?.video_id) {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
            setRefVideoInfo({
              videoId: analysisRes.data.video_id,
              videoUrl: `${apiBase}/videos/${analysisRes.data.video_id}/stream`,
              modelName: refModel.name,
              surgeonName: refModel.surgeon_name,
              surgeryType: refModel.surgery_type,
            })
          }
        }
      } catch (err) {
        console.error('Failed to fetch reference video:', err)
        setRefVideoInfo(null)
      }
    }

    fetchRefVideo()
  }, [selectedReferenceId])

  // ミニ動画の再生/停止
  const toggleMiniPlay = () => {
    if (!miniVideoRef.current) return
    if (miniPlaying) {
      miniVideoRef.current.pause()
    } else {
      miniVideoRef.current.play()
    }
    setMiniPlaying(!miniPlaying)
  }

  const videoTypeLabel = {
    external: '外部視点',
    external_no_instruments: '外部視点（器具なし）',
    external_with_instruments: '外部視点（器具あり）',
    internal: '内部視点',
    eye_gaze: '視線解析',
  }[videoType || ''] || videoType || '--'

  const isRelative = evaluationMode === 'relative'
  const modeLabel = isRelative ? '相対評価' : '絶対評価'
  const modeBadgeColor = isRelative
    ? 'bg-purple-100 text-purple-700 border-purple-200'
    : 'bg-gray-100 text-gray-600 border-gray-200'

  // 比較概要（ratioの抽出）
  const getRatios = () => {
    if (!sixMetrics) return null
    const ratios: { label: string; ratio: number | null }[] = []
    for (const groupKey of ['motion_quality', 'waste_detection']) {
      const group = sixMetrics[groupKey]
      if (!group?.metrics) continue
      for (const [, m] of Object.entries(group.metrics) as any) {
        if (m.ratio_to_expert != null) {
          ratios.push({ label: m.metric_label_ja, ratio: m.ratio_to_expert })
        }
      }
    }
    return ratios.length > 0 ? ratios : null
  }

  return (
    <div className={`bg-white rounded-lg shadow-sm border border-gray-200 p-4 space-y-3 overflow-hidden ${className}`}>
      <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
        <Settings className="w-4 h-4" />
        比較設定
      </h3>

      {/* 基準モデル選択 */}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">基準モデル</label>
        {modelsLoading ? (
          <div className="h-9 bg-gray-100 rounded animate-pulse" />
        ) : models.length > 0 ? (
          <select
            value={selectedReferenceId || ''}
            onChange={(e) => onReferenceSelect?.(e.target.value)}
            className="w-full p-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
          >
            <option value="">なし（絶対評価）</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        ) : (
          <div className="text-xs text-gray-400 bg-gray-50 rounded p-2">
            基準モデル未登録（ライブラリから登録可能）
          </div>
        )}
      </div>

      {/* 評価モード */}
      <div>
        <span className={`inline-block text-xs px-2.5 py-1 rounded-full border ${modeBadgeColor}`}>
          {modeLabel}
        </span>
      </div>

      {/* === 基準動画が選択されている場合: ミニプレイヤー + 比較概要 === */}
      {refVideoInfo && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          {/* ミニ動画プレイヤー */}
          <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
            <video
              ref={miniVideoRef}
              src={refVideoInfo.videoUrl}
              className="w-full h-full object-contain"
              onEnded={() => setMiniPlaying(false)}
              muted
            />
            {/* 再生ボタンオーバーレイ */}
            <button
              onClick={toggleMiniPlay}
              className="absolute inset-0 flex items-center justify-center bg-black/20 hover:bg-black/30 transition-colors"
            >
              {!miniPlaying && (
                <div className="w-10 h-10 bg-white/90 rounded-full flex items-center justify-center">
                  <Play className="w-5 h-5 text-gray-800 ml-0.5" />
                </div>
              )}
            </button>
            {/* ラベル */}
            <div className="absolute top-1.5 left-1.5 bg-purple-600/90 text-white text-[10px] px-1.5 py-0.5 rounded">
              基準動画
            </div>
          </div>

          {/* 並べて比較ボタン */}
          {onDualVideoMode && (
            <button
              onClick={onDualVideoMode}
              className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-md hover:bg-purple-100 transition-colors"
            >
              <Columns className="w-3.5 h-3.5" />
              並べて比較
            </button>
          )}

          {/* 基準モデル情報 */}
          <div className="text-xs space-y-0.5">
            <div className="font-medium text-gray-800">{refVideoInfo.modelName}</div>
            {refVideoInfo.surgeonName && (
              <div className="text-gray-500">{refVideoInfo.surgeonName}</div>
            )}
            {refVideoInfo.surgeryType && (
              <div className="text-gray-400">{refVideoInfo.surgeryType}</div>
            )}
          </div>

          {/* 比較概要（ratio一覧�� */}
          {getRatios() && (
            <div className="bg-gray-50 rounded p-2 space-y-1">
              <div className="text-[10px] font-semibold text-gray-500 mb-1">比較概要</div>
              {getRatios()!.map((r, i) => {
                const color = r.ratio! <= 1.0 ? 'text-green-600' :
                              r.ratio! <= 1.5 ? 'text-yellow-600' : 'text-red-600'
                return (
                  <div key={i} className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-600">{r.label}</span>
                    <span className={`font-mono font-bold ${color}`}>
                      x{r.ratio!.toFixed(2)}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* === 基準未選択時: 解析情報を表示 === */}
      {!refVideoInfo && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Eye className="w-3.5 h-3.5" />
            解析情報
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-gray-400">タイプ</div>
              <div className="font-medium text-gray-700">{videoTypeLabel}</div>
            </div>
            <div>
              <div className="text-gray-400">フレーム</div>
              <div className="font-medium text-gray-700">{totalFrames ?? '--'}</div>
            </div>
            {detectionRate && (
              <>
                <div>
                  <div className="text-gray-400">左手検出</div>
                  <div className="font-medium text-gray-700">
                    {(detectionRate.left * 100).toFixed(0)}%
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">右手検出</div>
                  <div className="font-medium text-gray-700">
                    {(detectionRate.right * 100).toFixed(0)}%
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ComparisonSettingsPanel
