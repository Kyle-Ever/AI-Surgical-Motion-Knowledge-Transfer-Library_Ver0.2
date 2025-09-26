'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Upload, FileVideo, Loader2 } from 'lucide-react'
import { useReferenceModels, useStartComparison } from '@/hooks/useScoring'
import { useUploadVideo, useStartAnalysis } from '@/hooks/useApi'

export default function ScoringPage() {
  const router = useRouter()
  const { models: referenceModels, isLoading: modelsLoading } = useReferenceModels()
  const { uploadVideo, progress: uploadProgress } = useUploadVideo()
  const { startAnalysis } = useStartAnalysis()
  const { startComparison } = useStartComparison()

  const [selectedReferenceId, setSelectedReferenceId] = useState('')
  const [evaluationFile, setEvaluationFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [currentStep, setCurrentStep] = useState<'idle' | 'uploading' | 'analyzing' | 'comparing'>('idle')

  const handleComparisonStart = useCallback(async () => {
    if (!selectedReferenceId || !evaluationFile) return

    try {
      setIsProcessing(true)
      setCurrentStep('uploading')

      // 1. 動画をアップロード
      const uploadResponse = await uploadVideo(evaluationFile, {
        video_type: 'external',  // 手元カメラとして扱う
        surgery_name: '評価用動画',
        memo: `基準モデル${selectedReferenceId}との比較`
      })

      const videoId = uploadResponse.video_id

      // 2. 解析を開始
      setCurrentStep('analyzing')
      const analysisResponse = await startAnalysis(videoId, [])
      const analysisId = analysisResponse.id

      // 解析完了を待つ（ポーリング）
      // 最初に短い待機時間を設定（処理開始のため）
      await new Promise(resolve => setTimeout(resolve, 2000))  // 2秒待つ

      const maxAttempts = 60  // 最大60回試行（約5分）
      let attempts = 0
      let analysisCompleted = false

      while (!analysisCompleted && attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 3000))  // 3秒待つ
        attempts++

        try {
          const statusResponse = await fetch(`http://localhost:8000/api/v1/analysis/${analysisId}/status`)
          const statusData = await statusResponse.json()

          // overall_progress が 100 なら完了
          if (statusData.overall_progress === 100) {
            analysisCompleted = true
          } else if (statusData.overall_progress === -1) {
            // エラーの場合は progress が -1 になることがある
            throw new Error('解析に失敗しました')
          }
        } catch (error) {
          console.error('Status check error:', error)
        }
      }

      if (!analysisCompleted) {
        throw new Error('解析がタイムアウトしました')
      }

      // 3. 比較を開始
      setCurrentStep('comparing')
      const comparisonResponse = await startComparison(
        selectedReferenceId,
        analysisId
      )

      // 比較結果ページへ遷移
      router.push(`/scoring/result/${comparisonResponse.id}`)
    } catch (error: any) {
      console.error('Comparison error:', error)
      alert(error?.message || '比較処理中にエラーが発生しました')
      setIsProcessing(false)
      setCurrentStep('idle')
    }
  }, [selectedReferenceId, evaluationFile, uploadVideo, startAnalysis, startComparison, router])

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">採点モード</h1>
        <p className="text-gray-600 mt-1">
          指導医の手技と比較して評価・フィードバックを受けられます
        </p>
      </div>

      <div className="space-y-6">
        {/* 比較元モデル選択 */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">比較元モデル選択</h2>
          {modelsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-600">読み込み中...</span>
            </div>
          ) : (
            <select
              value={selectedReferenceId}
              onChange={(e) => setSelectedReferenceId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isProcessing}
            >
              <option value="">ライブラリから選択してください</option>
              {referenceModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                  {model.surgeon_name && ` - ${model.surgeon_name}`}
                  {model.surgery_date && ` (${new Date(model.surgery_date).toLocaleDateString()})`}
                </option>
              ))}
            </select>
          )}
          {referenceModels.length === 0 && !modelsLoading && (
            <p className="text-sm text-gray-500 mt-2">
              基準モデルがありません。ライブラリから解析済みの動画を基準モデルとして登録してください。
            </p>
          )}
        </div>

        {/* 評価する動画 */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">評価する動画</h2>
          {!evaluationFile ? (
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
              <FileVideo className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600 mb-2">動画を選択してください</p>
              <label className="inline-block">
                <input
                  type="file"
                  accept="video/mp4"
                  className="hidden"
                  disabled={isProcessing}
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setEvaluationFile(e.target.files[0])
                    }
                  }}
                />
                <span className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer">
                  ファイルを選択
                </span>
              </label>
              <p className="text-xs text-gray-500 mt-4">対応形式: MP4（最大2GB）</p>
            </div>
          ) : (
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <FileVideo className="w-8 h-8 text-blue-600" />
                <div>
                  <p className="font-medium text-gray-900">{evaluationFile.name}</p>
                  <p className="text-sm text-gray-500">
                    {(evaluationFile.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <button
                onClick={() => setEvaluationFile(null)}
                className="text-red-600 hover:text-red-800"
                disabled={isProcessing}
              >
                削除
              </button>
            </div>
          )}
        </div>

        {/* 比較開始ボタン */}
        <div className="flex justify-center">
          <button
            onClick={handleComparisonStart}
            disabled={!selectedReferenceId || !evaluationFile || isProcessing}
            className="px-8 py-3 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                {currentStep === 'uploading' && `アップロード中... ${uploadProgress}%`}
                {currentStep === 'analyzing' && '解析中...'}
                {currentStep === 'comparing' && '比較中...'}
              </>
            ) : (
              '比較を開始'
            )}
          </button>
        </div>

        {/* 処理状況表示 */}
        {isProcessing && (
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center">
              <Loader2 className="w-5 h-5 mr-3 animate-spin text-blue-600" />
              <div>
                <p className="font-medium text-blue-900">
                  {currentStep === 'uploading' && '動画をアップロード中...'}
                  {currentStep === 'analyzing' && '動画を解析中...'}
                  {currentStep === 'comparing' && '基準モデルと比較中...'}
                </p>
                <p className="text-sm text-blue-700 mt-1">
                  しばらくお待ちください。処理には数分かかる場合があります。
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 説明 */}
      <div className="mt-8 bg-blue-50 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-2">採点モードの使い方</h3>
        <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800">
          <li>ライブラリから比較元となる指導医の手技モデルを選択</li>
          <li>評価したい自分の手術動画をアップロード</li>
          <li>比較を開始してAIによる分析を待つ</li>
          <li>スコアと改善点のフィードバックを受け取る</li>
        </ol>
      </div>
    </div>
  )
}