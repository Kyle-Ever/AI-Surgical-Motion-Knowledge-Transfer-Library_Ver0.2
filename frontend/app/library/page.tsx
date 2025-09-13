'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Filter, ChevronRight, Trash2 } from 'lucide-react'

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
      const response = await fetch('http://localhost:8000/api/v1/analysis/completed')
      if (response.ok) {
        const data = await response.json()
        // ライブラリ用にデータを整形
        const formattedItems = data.map((item: any) => ({
          id: item.id,
          techniqueName: item.video?.surgery_name || '未設定',
          surgeonName: item.video?.surgeon_name || '未設定',
          date: item.completed_at ? new Date(item.completed_at).toLocaleDateString('ja-JP') : '-',
          category: item.video?.video_type === 'internal' ? '内視鏡' : '外部カメラ'
        }))
        setLibraryItems(formattedItems)
      } else {
        // APIが失敗した場合はモックデータを使用
        setLibraryItems(mockLibrary)
      }
    } catch (error) {
      console.error('Failed to fetch library items:', error)
      // エラー時はモックデータを使用
      setLibraryItems(mockLibrary)
    } finally {
      setLoading(false)
    }
  }

  const handleItemClick = (itemId: string) => {
    router.push(`/dashboard/${itemId}`)
  }

  const handleDelete = (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation() // 親要素のクリックイベントを防ぐ
    
    if (window.confirm('このアイテムを削除しますか？')) {
      // ローカルステートから削除
      setLibraryItems(prev => prev.filter(item => item.id !== itemId))
      
      // TODO: APIコールで実際に削除
      // fetch(`/api/library/${itemId}`, { method: 'DELETE' })
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