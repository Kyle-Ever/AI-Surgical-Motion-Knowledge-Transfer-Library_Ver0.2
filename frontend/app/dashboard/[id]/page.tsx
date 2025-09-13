'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Download } from 'lucide-react'
import dynamic from 'next/dynamic'

// 動的インポート（SSR対策）
const Chart = dynamic(() => import('@/components/Chart'), { ssr: false })
const VideoPlayer = dynamic(() => import('@/components/VideoPlayer'), { ssr: false })

// モックデータ
const mockAnalysisData = {
  videoInfo: {
    filename: 'surgery_20250104.mp4',
    surgeryName: '腹腔鏡手術',
    surgeryDate: '2025-01-04',
    surgeonName: '山田医師',
    duration: 600, // 10分
  },
  statistics: {
    avgVelocity: 15.3,
    maxVelocity: 45.2,
    totalDistance: 1523.4,
    totalFrames: 3000,
  },
  trajectoryData: {
    labels: Array.from({ length: 50 }, (_, i) => i * 2),
    datasets: [
      {
        label: '左手',
        data: Array.from({ length: 50 }, () => Math.random() * 100),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.5)',
      },
      {
        label: '右手',
        data: Array.from({ length: 50 }, () => Math.random() * 100),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.5)',
      },
    ],
  },
  velocityData: {
    labels: Array.from({ length: 50 }, (_, i) => i * 2),
    datasets: [
      {
        label: '速度',
        data: Array.from({ length: 50 }, () => Math.random() * 50),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.5)',
      },
    ],
  },
}

export default function DashboardPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [videoId, setVideoId] = useState<string>('')

  // パラメータを取得
  useEffect(() => {
    setVideoId(params.id)
  }, [params])

  // APIから解析結果を取得
  useEffect(() => {
    if (!videoId) return
    
    const fetchAnalysisData = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/v1/analysis/${videoId}`)
        if (response.ok) {
          const data = await response.json()
          setAnalysisData(data)
        }
      } catch (error) {
        console.error('Failed to fetch analysis data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAnalysisData()
  }, [videoId])

  const handleExport = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/analysis/${videoId}/export`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `analysis_${params.id}.csv`
        a.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            解析結果 - {mockAnalysisData.videoInfo.surgeryName}
          </h1>
          <p className="text-gray-600 mt-1">
            {mockAnalysisData.videoInfo.surgeryDate} / {mockAnalysisData.videoInfo.surgeonName}
          </p>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <Download className="w-4 h-4" />
          <span>エクスポート</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 動画プレーヤー */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">解析済み動画</h2>
          {loading ? (
            <div className="bg-gray-100 rounded-lg aspect-video flex items-center justify-center">
              <p className="text-gray-500">読み込み中...</p>
            </div>
          ) : (
            <div className="w-full max-w-full overflow-hidden rounded-lg">
              <VideoPlayer
                videoUrl={analysisData?.video_url}
                skeletonData={analysisData?.skeleton_data ? JSON.parse(analysisData.skeleton_data) : []}
                toolData={analysisData?.coordinate_data?.frames || []}
                width={640}
                height={360}
              />
            </div>
          )}
        </div>

        {/* 統計サマリー */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">統計サマリー</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">平均速度</p>
              <p className="text-2xl font-bold text-blue-600">
                {mockAnalysisData.statistics.avgVelocity.toFixed(1)} mm/s
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">最大速度</p>
              <p className="text-2xl font-bold text-green-600">
                {mockAnalysisData.statistics.maxVelocity.toFixed(1)} mm/s
              </p>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">総移動距離</p>
              <p className="text-2xl font-bold text-purple-600">
                {mockAnalysisData.statistics.totalDistance.toFixed(0)} mm
              </p>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">総フレーム数</p>
              <p className="text-2xl font-bold text-orange-600">
                {mockAnalysisData.statistics.totalFrames}
              </p>
            </div>
          </div>
        </div>

        {/* 軌跡グラフ */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">軌跡グラフ</h2>
          <Chart type="line" data={mockAnalysisData.trajectoryData} />
        </div>

        {/* 速度変化グラフ */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">速度変化</h2>
          <Chart type="line" data={mockAnalysisData.velocityData} />
        </div>
      </div>

      {/* データテーブル */}
      <div className="mt-6 bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-lg font-semibold mb-4">データテーブル</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  時間
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  X座標
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Y座標
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  速度
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  骨格角度
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {Array.from({ length: 5 }, (_, i) => (
                <tr key={i}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    0:{(i * 2).toString().padStart(2, '0')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {(123 + i * 10).toFixed(1)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {(456 + i * 15).toFixed(1)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {(12.3 + i * 2).toFixed(1)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {45 + i * 3}°
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex justify-center">
          <button className="px-4 py-2 text-sm text-blue-600 hover:text-blue-800">
            もっと見る
          </button>
        </div>
      </div>

      {/* アクションボタン */}
      <div className="mt-6 flex justify-end space-x-4">
        <button 
          onClick={() => router.push('/library')}
          className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
        >
          ライブラリへ戻る
        </button>
        <button 
          onClick={() => {
            alert('解析結果がライブラリに登録されました')
            router.push('/library')
          }}
          className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
        >
          ライブラリに登録
        </button>
      </div>
    </div>
  )
}