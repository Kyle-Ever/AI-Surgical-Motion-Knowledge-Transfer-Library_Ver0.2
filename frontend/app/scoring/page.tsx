'use client'

import { useState } from 'react'
import { Upload, FileVideo } from 'lucide-react'

export default function ScoringPage() {
  const [referenceModel, setReferenceModel] = useState('')
  const [evaluationFile, setEvaluationFile] = useState<File | null>(null)

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
          <select
            value={referenceModel}
            onChange={(e) => setReferenceModel(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">ライブラリから選択</option>
            <option value="model1">腹腔鏡手術_20250104 - 山田医師</option>
            <option value="model2">内視鏡手術_20250102 - 佐藤医師</option>
            <option value="model3">開腹手術_20241228 - 田中医師</option>
          </select>
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
              >
                削除
              </button>
            </div>
          )}
        </div>

        {/* 比較開始ボタン */}
        <div className="flex justify-center">
          <button
            disabled={!referenceModel || !evaluationFile}
            className="px-8 py-3 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            比較を開始
          </button>
        </div>
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