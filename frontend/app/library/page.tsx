'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Filter, ChevronRight, Trash2, Download, Award } from 'lucide-react'
import { getCompletedAnalyses, exportAnalysisData } from '@/lib/api'
import { useCreateReferenceModel } from '@/hooks/useScoring'

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
  const [filteredItems, setFilteredItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [registerModalOpen, setRegisterModalOpen] = useState(false)
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null)
  const [modelName, setModelName] = useState('')
  const [modelDescription, setModelDescription] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterModalOpen, setFilterModalOpen] = useState(false)
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [dateFilter, setDateFilter] = useState<'all' | 'week' | 'month' | 'three-months'>('all')
  const { createModel, isLoading: isCreating } = useCreateReferenceModel()

  // APIからライブラリデータを取得
  useEffect(() => {
    fetchLibraryItems()
  }, [])

  const fetchLibraryItems = async () => {
    try {
      // 完了した解析結果を取得
      const data = await getCompletedAnalyses()
      console.log('Fetched library data:', data)
      console.log('Total items fetched from API:', data?.length || 0)

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
                     item.video?.video_type === 'external_no_instruments' ? '外部カメラ（器具なし）' :
                     item.video?.video_type === 'external_with_instruments' ? '外部カメラ（器具あり）' :
                     item.video?.video_type === 'external' ? '外部カメラ' : '不明',
            score: item.scores?.overall || null,
            status: item.status
          }
        })

        // 日付で降順ソート（最新が上）
        const sortedItems = formattedItems.sort((a: any, b: any) => {
          // dateは "YYYY-MM-DD" 形式の文字列なので、そのまま比較可能
          const dateA = a.date || '1970-01-01'
          const dateB = b.date || '1970-01-01'
          return dateB.localeCompare(dateA) // 降順
        })

        setLibraryItems(sortedItems)
        setFilteredItems(sortedItems) // 初期状態では全アイテムを表示
        console.log('Formatted library items:', sortedItems)
        console.log('Total formatted items:', sortedItems.length)
      } else {
        // データがない場合は空配列を設定
        console.log('No completed analyses found')
        setLibraryItems([])
        setFilteredItems([])
      }
    } catch (error) {
      console.error('Failed to fetch library items:', error)
      // エラー時は空配列を設定
      setLibraryItems([])
      setFilteredItems([])
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

  const handleRegisterAsReference = (e: React.MouseEvent, item: any) => {
    e.stopPropagation()
    setSelectedAnalysisId(item.id)
    setModelName(item.techniqueName || '')
    setModelDescription(`${item.surgeonName}による手術 - ${item.date}`)
    setRegisterModalOpen(true)
  }

  // フィルタリングロジック
  useEffect(() => {
    let filtered = [...libraryItems]

    // 検索フィルタ
    if (searchQuery) {
      filtered = filtered.filter(item =>
        item.techniqueName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.surgeonName.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    // カテゴリフィルタ
    if (selectedCategories.length > 0) {
      filtered = filtered.filter(item =>
        selectedCategories.includes(item.category)
      )
    }

    // 日付フィルタ
    if (dateFilter !== 'all') {
      const now = new Date()
      const filterDate = new Date()

      switch (dateFilter) {
        case 'week':
          filterDate.setDate(now.getDate() - 7)
          break
        case 'month':
          filterDate.setMonth(now.getMonth() - 1)
          break
        case 'three-months':
          filterDate.setMonth(now.getMonth() - 3)
          break
      }

      filtered = filtered.filter(item => {
        const itemDate = new Date(item.date.replace(/\//g, '-'))
        return itemDate >= filterDate
      })
    }

    setFilteredItems(filtered)
  }, [libraryItems, searchQuery, selectedCategories, dateFilter])

  const handleConfirmRegister = async () => {
    if (!selectedAnalysisId || !modelName) return

    try {
      await createModel(
        selectedAnalysisId,
        modelName,
        modelDescription,
        {
          surgeon_name: libraryItems.find(item => item.id === selectedAnalysisId)?.surgeonName,
          surgery_date: new Date().toISOString()
        }
      )
      alert('基準モデルとして登録しました')
      setRegisterModalOpen(false)
      setSelectedAnalysisId(null)
      setModelName('')
      setModelDescription('')

      // 採点モードへ移動するか確認
      if (window.confirm('採点モードへ移動しますか？')) {
        router.push('/scoring')
      }
    } catch (error) {
      console.error('Registration error:', error)
      alert('基準モデルの登録に失敗しました')
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
              placeholder="手技名・医師名で検索..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={() => setFilterModalOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <Filter className="w-4 h-4" />
            <span>フィルター</span>
            {(selectedCategories.length > 0 || dateFilter !== 'all') && (
              <span className="ml-1 px-2 py-0.5 bg-purple-100 text-purple-600 rounded-full text-xs">
                {selectedCategories.length + (dateFilter !== 'all' ? 1 : 0)}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ライブラリ一覧 */}
      <div className="bg-white rounded-lg shadow-sm">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            読み込み中...
          </div>
        ) : libraryItems.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            ライブラリにアイテムがありません
          </div>
        ) : (
          <div>
            <div className="p-4 border-b bg-gray-50">
              <span className="text-sm text-gray-600">
                {filteredItems.length === libraryItems.length
                  ? `全 ${libraryItems.length} 件の解析結果`
                  : `${filteredItems.length} / ${libraryItems.length} 件を表示`}
              </span>
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              {filteredItems.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  検索条件に一致するアイテムがありません
                </div>
              ) : (
                filteredItems.map((item) => (
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
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    item.category === '内視鏡' ? 'bg-purple-100 text-purple-800' :
                    item.category === '外部カメラ（器具あり）' ? 'bg-green-100 text-green-800' :
                    item.category === '外部カメラ（器具なし）' ? 'bg-blue-100 text-blue-800' :
                    item.category === '外部カメラ' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {item.category}
                  </span>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={(e) => handleRegisterAsReference(e, item)}
                  className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                  title="基準モデルとして登録"
                >
                  <Award className="w-5 h-5" />
                </button>
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
          </div>
        )}
      </div>

      {/* アクションボタン */}
      <div className="mt-6 flex justify-center">
        <button
          onClick={() => router.push('/scoring')}
          className="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
        >
          採点モードへ
        </button>
      </div>

      {/* 基準モデル登録モーダル */}
      {registerModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">基準モデルとして登録</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  モデル名 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="例: 腹腔鏡手術_熟練医モデル"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  説明
                </label>
                <textarea
                  value={modelDescription}
                  onChange={(e) => setModelDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  rows={3}
                  placeholder="このモデルの説明を入力してください"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setRegisterModalOpen(false)
                  setSelectedAnalysisId(null)
                  setModelName('')
                  setModelDescription('')
                }}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                キャンセル
              </button>
              <button
                onClick={handleConfirmRegister}
                disabled={!modelName || isCreating}
                className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCreating ? '登録中...' : '登録'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* フィルターモーダル */}
      {filterModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">フィルター設定</h2>

            {/* カテゴリフィルター */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-2">カテゴリ</h3>
              <div className="space-y-2">
                {['内視鏡', '外部カメラ（器具あり）', '外部カメラ（器具なし）', '外部カメラ'].map((category) => (
                  <label key={category} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(category)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedCategories([...selectedCategories, category])
                        } else {
                          setSelectedCategories(selectedCategories.filter(c => c !== category))
                        }
                      }}
                      className="mr-2 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm">{category}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* 期間フィルター */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-2">期間</h3>
              <select
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value as any)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <option value="all">すべて</option>
                <option value="week">過去1週間</option>
                <option value="month">過去1ヶ月</option>
                <option value="three-months">過去3ヶ月</option>
              </select>
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setSelectedCategories([])
                  setDateFilter('all')
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                リセット
              </button>
              <button
                onClick={() => setFilterModalOpen(false)}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                キャンセル
              </button>
              <button
                onClick={() => setFilterModalOpen(false)}
                className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
              >
                適用
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}