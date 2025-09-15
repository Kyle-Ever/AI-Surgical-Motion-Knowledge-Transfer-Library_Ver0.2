'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Filter, ChevronRight, Trash2, Download } from 'lucide-react'
import { getCompletedAnalyses, exportAnalysisData } from '@/lib/api'

const mockLibrary = [
  {
    id: '1',
    techniqueName: '腹腔鏡手術_20250104',
    surgeonName: '山田医師',
    date: '2025-01-04',
    category: '腹腔鏡',
  },
  {
    id: '2',
    techniqueName: '内視鏡手術_20250102',
    surgeonName: '佐藤医師',
    date: '2025-01-02',
    category: '内視鏡',
  },
  {
    id: '3',
    techniqueName: '開腹手術_20241228',
    surgeonName: '田中医師',
    date: '2024-12-28',
    category: '開腹',
  },
]

export default function LibraryPage() {
  const router = useRouter()
  const [libraryItems, setLibraryItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // APIからライブラリデータを取得
  useEffect(() => {
    fetchLibraryItems()
  }, [])

  const fetchLibraryItems = async () => {
    try {
      // 完了した解析結果を取得
      const data = await getCompletedAnalyses()
      console.log('Fetched library data:', data)
      if (data && data.length > 0) {

        // ライブラリ用にデータを整形
        const formattedItems = data.map((item: any) => {
          // 手術名と医師名を動画情報から取得、またはファイル名から生成
          const surgeryName = item.video?.surgery_name ||
                              item.video?.original_filename?.replace('.mp4', '') ||
                              `解析_${item.id.substring(0, 8)}`
          const surgeonName = item.video?.surgeon_name || '未設定'

          return {
            id: item.id,
            techniqueName: surgeryName,
            surgeonName: surgeonName,
            date: item.completed_at ? new Date(item.completed_at).toLocaleDateString('ja-JP') :
                  item.created_at ? new Date(item.created_at).toLocaleDateString('ja-JP') : '-',
            category: item.video?.video_type === 'internal' ? '内視鏡' :
                     item.video?.video_type === 'external' ? '外部カメラ' : '不明',
            score: item.scores?.overall || null,
            status: item.status
          }
        })
        setLibraryItems(formattedItems)
        console.log('Formatted library items:', formattedItems)
      } else {
        // データがない場合は空配列を設定
        console.log('No completed analyses found')
        setLibraryItems([])
      }
    } catch (error) {
      console.error('Failed to fetch library items:', error)
      // エラー時は空配列を設定
      setLibraryItems([])
    } finally {
      setLoading(false)
    }
  }

  const handleItemClick = (itemId: string) => {
    router.push(`/dashboard/${itemId}`)
  }

  const handleDelete = async (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation() // 親要素のクリックイベントを防ぐ

    if (window.confirm('この解析結果を削除しますか？')) {
      try {
        // APIコールで実際に削除
        const response = await fetch(`http://localhost:8000/api/v1/analysis/${itemId}`, {
          method: 'DELETE'
        })

        if (response.ok) {
          // 削除成功後、リストを再取得
          fetchLibraryItems()
          console.log(`Successfully deleted analysis: ${itemId}`)
        } else {
          console.error('Failed to delete analysis:', response.statusText)
          alert('削除に失敗しました')
        }
      } catch (error) {
        console.error('Delete error:', error)
        alert('削除中にエラーが発生しました')
      }
    }
  }

  const handleExport = async (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation() // 親要素のクリックイベントを防ぐ

    try {
      await exportAnalysisData(itemId)
      console.log(`Successfully exported analysis: ${itemId}`)
    } catch (error) {
      console.error('Export error:', error)
      alert('エクスポートに失敗しました')
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">手技ライブラリ</h1>
        <p className="text-gray-600 mt-1">保存済みの解析結果を管理・閲覧できます</p>
      </div>

      {/* 検索・フィルター */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="flex items-center space-x-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="検索..."
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50">
            <Filter className="w-4 h-4" />
            <span>フィルター</span>
          </button>
        </div>
      </div>

      {/* ライブラリ一覧 */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            読み込み中...
          </div>
        ) : libraryItems.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            ライブラリにアイテムがありません
          </div>
        ) : (
          libraryItems.map((item) => (
          <div
            key={item.id}
            className="border-b border-gray-200 p-4 hover:bg-gray-50 cursor-pointer"
            onClick={() => handleItemClick(item.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900">
                  {item.techniqueName}
                </h3>
                <div className="mt-1 text-sm text-gray-600">
                  執刀医: {item.surgeonName} / 登録日: {item.date}
                </div>
                <div className="mt-2">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    {item.category}
                  </span>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={(e) => handleExport(e, item.id)}
                  className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                  title="エクスポート"
                >
                  <Download className="w-5 h-5" />
                </button>
                <button
                  onClick={(e) => handleDelete(e, item.id)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="削除"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </div>
            </div>
          </div>
        )))}
      </div>

      {/* アクションボタン */}
      <div className="mt-6 flex justify-center">
        <button className="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700">
          採点モードで使用
        </button>
      </div>
    </div>
  )
}