'use client'

import { Calendar, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react'

const mockHistory = [
  {
    id: '1',
    filename: 'surgery_20250104_morning.mp4',
    surgeryName: '腹腔鏡手術',
    date: '2025-01-04 10:30',
    status: 'completed',
    duration: '10:32',
    surgeon: '山田医師',
  },
  {
    id: '2',
    filename: 'surgery_20250103_afternoon.mp4',
    surgeryName: '内視鏡手術',
    date: '2025-01-03 14:15',
    status: 'completed',
    duration: '08:45',
    surgeon: '佐藤医師',
  },
  {
    id: '3',
    filename: 'surgery_20250102_test.mp4',
    surgeryName: 'テスト解析',
    date: '2025-01-02 09:00',
    status: 'failed',
    duration: '02:15',
    surgeon: '田中医師',
  },
  {
    id: '4',
    filename: 'surgery_20241228.mp4',
    surgeryName: '開腹手術',
    date: '2024-12-28 11:20',
    status: 'completed',
    duration: '15:48',
    surgeon: '田中医師',
  },
  {
    id: '5',
    filename: 'surgery_20241225_demo.mp4',
    surgeryName: 'デモ手術',
    date: '2024-12-25 16:00',
    status: 'processing',
    duration: '05:30',
    surgeon: '山田医師',
  },
]

const statusConfig = {
  completed: {
    icon: CheckCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    label: '完了',
  },
  processing: {
    icon: AlertCircle,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    label: '処理中',
  },
  failed: {
    icon: XCircle,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    label: '失敗',
  },
}

export default function HistoryPage() {
  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">解析履歴</h1>
        <p className="text-gray-600 mt-1">過去の解析処理を確認できます</p>
      </div>

      {/* フィルター */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Calendar className="w-4 h-4 text-gray-500" />
            <input
              type="date"
              className="px-3 py-1 border border-gray-300 rounded-md text-sm"
            />
            <span className="text-gray-500">〜</span>
            <input
              type="date"
              className="px-3 py-1 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <select className="px-3 py-1 border border-gray-300 rounded-md text-sm">
            <option value="">すべてのステータス</option>
            <option value="completed">完了</option>
            <option value="processing">処理中</option>
            <option value="failed">失敗</option>
          </select>
        </div>
      </div>

      {/* 履歴テーブル */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                ファイル名
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                手術名
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                執刀医
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                日時
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                動画時間
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                ステータス
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                アクション
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {mockHistory.map((item) => {
              const status = statusConfig[item.status as keyof typeof statusConfig]
              const StatusIcon = status.icon
              
              return (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {item.filename}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {item.surgeryName}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {item.surgeon}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {item.date}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="flex items-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {item.duration}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.bgColor} ${status.color}`}>
                      <StatusIcon className="w-3 h-3 mr-1" />
                      {status.label}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {item.status === 'completed' && (
                      <button className="text-blue-600 hover:text-blue-800">
                        結果を見る
                      </button>
                    )}
                    {item.status === 'processing' && (
                      <button className="text-blue-600 hover:text-blue-800">
                        進捗確認
                      </button>
                    )}
                    {item.status === 'failed' && (
                      <button className="text-orange-600 hover:text-orange-800">
                        再実行
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* ページネーション */}
      <div className="mt-6 flex items-center justify-between">
        <div className="text-sm text-gray-700">
          全 {mockHistory.length} 件
        </div>
        <div className="flex space-x-2">
          <button className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50">
            前へ
          </button>
          <button className="px-3 py-1 bg-blue-600 text-white rounded-md text-sm">
            1
          </button>
          <button className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50">
            2
          </button>
          <button className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50">
            次へ
          </button>
        </div>
      </div>
    </div>
  )
}