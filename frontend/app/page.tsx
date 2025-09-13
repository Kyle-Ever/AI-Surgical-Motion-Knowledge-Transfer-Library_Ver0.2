'use client'

import Link from 'next/link'
import { FileVideo, Library, Award, History } from 'lucide-react'

const features = [
  {
    title: '新規解析',
    description: '手術動画をアップロードして解析を開始',
    icon: FileVideo,
    href: '/upload',
    color: 'bg-blue-500',
  },
  {
    title: 'ライブラリ',
    description: '保存済みの解析結果を閲覧・管理',
    icon: Library,
    href: '/library',
    color: 'bg-green-500',
  },
  {
    title: '採点モード',
    description: '手技を比較して評価・フィードバック',
    icon: Award,
    href: '/scoring',
    color: 'bg-purple-500',
  },
  {
    title: '履歴',
    description: '過去の解析履歴を確認',
    icon: History,
    href: '/history',
    color: 'bg-orange-500',
  },
]

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">AI手技モーション伝承ライブラリ</h1>
        <p className="text-gray-600">手術手技をデータ化し、指導医の技術を効果的に伝承します。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {features.map((feature) => {
          const Icon = feature.icon
          return (
            <Link
              key={feature.href}
              href={feature.href}
              className="group relative bg-white p-6 rounded-xl shadow-md hover:shadow-xl transition-all duration-300 hover:scale-105"
            >
              <div className="flex items-start space-x-4">
                <div className={`${feature.color} p-3 rounded-lg text-white group-hover:scale-110 transition-transform`}>
                  <Icon className="w-6 h-6" />
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-semibold text-gray-900 mb-2">{feature.title}</h2>
                  <p className="text-gray-600">{feature.description}</p>
                </div>
              </div>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent to-gray-50 opacity-0 group-hover:opacity-100 rounded-xl transition-opacity pointer-events-none" />
            </Link>
          )
        })}
      </div>

      <div className="mt-12 bg-blue-50 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">クイックスタート</h2>
        <div className="space-y-3">
          <div className="flex items-center space-x-3">
            <span className="flex items-center justify-center w-8 h-8 bg-blue-500 text-white rounded-full font-semibold">1</span>
            <p className="text-gray-700">動画をアップロードして映像タイプを選択</p>
          </div>
          <div className="flex items-center space-x-3">
            <span className="flex items-center justify-center w-8 h-8 bg-blue-500 text-white rounded-full font-semibold">2</span>
            <p className="text-gray-700">AI解析で手術器具と手の動きを自動追跡</p>
          </div>
          <div className="flex items-center space-x-3">
            <span className="flex items-center justify-center w-8 h-8 bg-blue-500 text-white rounded-full font-semibold">3</span>
            <p className="text-gray-700">解析結果をグラフで確認、データをエクスポート</p>
          </div>
        </div>
      </div>
    </div>
  )
}

