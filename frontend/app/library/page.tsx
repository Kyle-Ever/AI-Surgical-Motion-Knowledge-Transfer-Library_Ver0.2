'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Filter, ChevronRight, Trash2, Download, Award, Database, FileText } from 'lucide-react'
import { api, getCompletedAnalyses, getCompletedComparisons, exportAnalysisData } from '@/lib/api'
import { useCreateReferenceModel, useReferenceModels, useDeleteReferenceModel } from '@/hooks/useScoring'

type TabType = 'analyses' | 'references'

export default function LibraryPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<TabType>('analyses')

  // === 解析結果タブ ===
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

  // === 基準モデルタブ ===
  const { models, isLoading: modelsLoading, refetch: refetchModels } = useReferenceModels()
  const { deleteModel, isLoading: isDeleting } = useDeleteReferenceModel()
  const [refSearchQuery, setRefSearchQuery] = useState('')

  // APIからライブラリデータを取得
  useEffect(() => {
    fetchLibraryItems()
  }, [])

  const fetchLibraryItems = async () => {
    try {
      const [analysesData, comparisonsData] = await Promise.all([
        getCompletedAnalyses(),
        getCompletedComparisons()
      ])

      const allItems = []

      if (analysesData && analysesData.length > 0) {
        const formattedAnalyses = analysesData.map((item: any) => {
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
            category: item.video?.video_type === 'eye_gaze' ? '視線解析' :
                     item.video?.video_type === 'internal' ? '内視鏡' :
                     item.video?.video_type === 'external_no_instruments' ? '外部カメラ（器具なし）' :
                     item.video?.video_type === 'external_with_instruments' ? '外部カメラ（器具あり）' :
                     item.video?.video_type === 'external' ? '外部カメラ' : '不明',
            score: item.scores?.overall || null,
            status: item.status,
            type: 'analysis',
            rawDate: item.completed_at || item.created_at
          }
        })
        allItems.push(...formattedAnalyses)
      }

      if (comparisonsData && comparisonsData.length > 0) {
        const formattedComparisons = comparisonsData.map((item: any) => {
          const surgeryName = item.learner_analysis?.video?.surgery_name ||
                             item.learner_analysis?.video?.original_filename?.replace('.mp4', '') ||
                             `採点_${item.id.substring(0, 8)}`
          const surgeonName = item.learner_analysis?.video?.surgeon_name || '学習者'

          return {
            id: item.id,
            techniqueName: `【採点】${surgeryName}`,
            surgeonName: surgeonName,
            date: item.completed_at ? new Date(item.completed_at).toLocaleDateString('ja-JP') :
                  item.created_at ? new Date(item.created_at).toLocaleDateString('ja-JP') : '-',
            category: '採点結果',
            score: item.overall_score || null,
            status: item.status,
            type: 'comparison',
            comparisonId: item.id
          }
        })
        allItems.push(...formattedComparisons)
      }

      const sortedItems = allItems.sort((a: any, b: any) => {
        const getDateValue = (item: any) => {
          if (item.rawDate) return new Date(item.rawDate).getTime()
          const dateStr = item.date || '1970-01-01'
          const normalized = dateStr.replace(/\//g, '-')
          const dateObj = new Date(normalized)
          return isNaN(dateObj.getTime()) ? 0 : dateObj.getTime()
        }
        return getDateValue(b) - getDateValue(a)
      })

      setLibraryItems(sortedItems)
      setFilteredItems(sortedItems)
    } catch (error) {
      console.error('Failed to fetch library items:', error)
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
    e.stopPropagation()
    if (!window.confirm('この解析結果を削除しますか？')) return
    try {
      const item = libraryItems.find(i => i.id === itemId)
      const deleteEndpoint = item?.type === 'comparison'
        ? `/scoring/comparisons/${itemId}`
        : `/analysis/${itemId}`
      await api.delete(deleteEndpoint)
      fetchLibraryItems()
    } catch (error: any) {
      console.error('Delete error:', error)
      alert(error?.code === 'ERR_NETWORK'
        ? 'サーバーに接続できません'
        : `削除に失敗しました: ${error?.message || error}`)
    }
  }

  const handleExport = async (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation()
    try { await exportAnalysisData(itemId) }
    catch { alert('エクスポートに失敗しました') }
  }

  const handleRegisterAsReference = (e: React.MouseEvent, item: any) => {
    e.stopPropagation()
    setSelectedAnalysisId(item.id)
    setModelName(item.techniqueName || '')
    setModelDescription(`${item.surgeonName}による手術 - ${item.date}`)
    setRegisterModalOpen(true)
  }

  // フィルタリング
  useEffect(() => {
    let filtered = [...libraryItems]
    if (searchQuery) {
      filtered = filtered.filter(item =>
        item.techniqueName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.surgeonName.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    if (selectedCategories.length > 0) {
      filtered = filtered.filter(item => selectedCategories.includes(item.category))
    }
    if (dateFilter !== 'all') {
      const filterDate = new Date()
      if (dateFilter === 'week') filterDate.setDate(filterDate.getDate() - 7)
      else if (dateFilter === 'month') filterDate.setMonth(filterDate.getMonth() - 1)
      else if (dateFilter === 'three-months') filterDate.setMonth(filterDate.getMonth() - 3)
      filtered = filtered.filter(item => {
        const normalizedDate = item.date ? item.date.replace(/\//g, '-') : '1970-01-01'
        const itemDate = new Date(normalizedDate)
        return isNaN(itemDate.getTime()) ? true : itemDate >= filterDate
      })
    }
    setFilteredItems(filtered)
  }, [libraryItems, searchQuery, selectedCategories, dateFilter])

  const handleConfirmRegister = async () => {
    if (!selectedAnalysisId || !modelName) return
    try {
      await createModel(selectedAnalysisId, modelName, modelDescription, {
        surgeon_name: libraryItems.find(item => item.id === selectedAnalysisId)?.surgeonName,
        surgery_date: new Date().toISOString()
      })
      alert('基準モデルとして登録しました')
      setRegisterModalOpen(false)
      setSelectedAnalysisId(null)
      setModelName('')
      setModelDescription('')
      refetchModels()
      setActiveTab('references')
    } catch {
      alert('基準モデルの登録に失敗しました')
    }
  }

  // === 基準モデル削除 ===
  const handleDeleteReference = async (e: React.MouseEvent, refId: string, refName: string) => {
    e.stopPropagation()
    if (!window.confirm(`基準モデル「${refName}」を削除しますか？`)) return
    try {
      await deleteModel(refId)
      refetchModels()
    } catch {
      alert('削除に失敗しました')
    }
  }

  // 基準モデルのフィルタリング
  const filteredModels = models.filter(m =>
    !refSearchQuery ||
    m.name.toLowerCase().includes(refSearchQuery.toLowerCase()) ||
    (m.surgeon_name || '').toLowerCase().includes(refSearchQuery.toLowerCase())
  )

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">手技ライブラリ</h1>
        <p className="text-gray-600 mt-1">保存済みの解析結果と基準モデルを管理できます</p>
      </div>

      {/* タブ切替 */}
      <div className="flex border-b border-gray-200 mb-6">
        <button
          onClick={() => setActiveTab('analyses')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'analyses'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <FileText className="w-4 h-4" />
          解析結果
          <span className="ml-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
            {libraryItems.length}
          </span>
        </button>
        <button
          onClick={() => setActiveTab('references')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'references'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <Database className="w-4 h-4" />
          基準モデル
          <span className="ml-1 px-2 py-0.5 bg-purple-100 text-purple-600 rounded-full text-xs">
            {models.length}
          </span>
        </button>
      </div>

      {/* === 解析結果タブ === */}
      {activeTab === 'analyses' && (
        <>
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

          {/* 一覧 */}
          <div className="bg-white rounded-lg shadow-sm">
            {loading ? (
              <div className="p-8 text-center text-gray-500">読み込み中...</div>
            ) : libraryItems.length === 0 ? (
              <div className="p-8 text-center text-gray-500">ライブラリにアイテムがありません</div>
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
                    <div className="p-8 text-center text-gray-500">検索条件に一致するアイテムがありません</div>
                  ) : (
                    filteredItems.map((item) => (
                      <div
                        key={item.id}
                        className="border-b border-gray-200 p-4 hover:bg-gray-50 cursor-pointer"
                        onClick={() => handleItemClick(item.id)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <h3 className="text-lg font-semibold text-gray-900">{item.techniqueName}</h3>
                            <div className="mt-1 text-sm text-gray-600">
                              執刀医: {item.surgeonName} / 登録日: {item.date}
                            </div>
                            <div className="mt-2">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                item.category === '視線解析' ? 'bg-orange-100 text-orange-800' :
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
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* === 基準モデルタブ === */}
      {activeTab === 'references' && (
        <>
          {/* 検索 */}
          <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
            <div className="flex items-center space-x-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="モデル名・医師名で検索..."
                  value={refSearchQuery}
                  onChange={(e) => setRefSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
          </div>

          {/* 基準モデル一覧 */}
          <div className="bg-white rounded-lg shadow-sm">
            {modelsLoading ? (
              <div className="p-8 text-center text-gray-500">読み込み中...</div>
            ) : models.length === 0 ? (
              <div className="p-12 text-center">
                <Database className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 mb-2">基準モデルがまだ登録されていません</p>
                <p className="text-sm text-gray-400 mb-4">
                  「解析結果」タブから解析を選択し、
                  <Award className="w-4 h-4 inline text-purple-500 mx-1" />
                  アイコンで基準モデルとして登録できます
                </p>
                <button
                  onClick={() => setActiveTab('analyses')}
                  className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 text-sm"
                >
                  解析結果を見る
                </button>
              </div>
            ) : (
              <div>
                <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
                  <span className="text-sm text-gray-600">
                    {filteredModels.length === models.length
                      ? `全 ${models.length} 件の基準モデル`
                      : `${filteredModels.length} / ${models.length} 件を表示`}
                  </span>
                </div>
                <div className="max-h-[600px] overflow-y-auto">
                  {filteredModels.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">検索条件に一致するモデルがありません</div>
                  ) : (
                    filteredModels.map((model) => (
                      <div
                        key={model.id}
                        className="border-b border-gray-200 p-4 hover:bg-gray-50"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Award className="w-5 h-5 text-purple-500" />
                              <h3 className="text-lg font-semibold text-gray-900">{model.name}</h3>
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-700">
                                基準モデル
                              </span>
                            </div>
                            {model.description && (
                              <p className="mt-1 text-sm text-gray-500">{model.description}</p>
                            )}
                            <div className="mt-1.5 flex items-center gap-4 text-sm text-gray-600">
                              {model.surgeon_name && (
                                <span>執刀医: {model.surgeon_name}</span>
                              )}
                              {model.surgery_date && (
                                <span>手術日: {new Date(model.surgery_date).toLocaleDateString('ja-JP')}</span>
                              )}
                              <span>登録日: {new Date(model.created_at).toLocaleDateString('ja-JP')}</span>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={(e) => handleDeleteReference(e, model.id, model.name)}
                              disabled={isDeleting}
                              className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                              title="基準モデルを削除"
                            >
                              <Trash2 className="w-5 h-5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}

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
                <label className="block text-sm font-medium text-gray-700 mb-1">説明</label>
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
                onClick={() => { setRegisterModalOpen(false); setSelectedAnalysisId(null); setModelName(''); setModelDescription('') }}
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
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-2">カテゴリ</h3>
              <div className="space-y-2">
                {['視線解析', '内視鏡', '外部カメラ（器具あり）', '外部カメラ（器具なし）', '外部カメラ'].map((category) => (
                  <label key={category} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(category)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedCategories([...selectedCategories, category])
                        else setSelectedCategories(selectedCategories.filter(c => c !== category))
                      }}
                      className="mr-2 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm">{category}</span>
                  </label>
                ))}
              </div>
            </div>
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
              <button onClick={() => { setSelectedCategories([]); setDateFilter('all') }} className="px-4 py-2 text-gray-600 hover:text-gray-800">リセット</button>
              <button onClick={() => setFilterModalOpen(false)} className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50">キャンセル</button>
              <button onClick={() => setFilterModalOpen(false)} className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700">適用</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
