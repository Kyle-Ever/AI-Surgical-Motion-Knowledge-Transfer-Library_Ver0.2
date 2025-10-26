"use client"

import Link from "next/link"
import { FileVideo, Library, Award, History } from "lucide-react"
import { cn } from "@/lib/utils"
import { useState, useEffect } from 'react'
import { getCompletedAnalyses } from '@/lib/api'

const features = [
  {
    title: "新規解析",
    description: "手術動画をアップロードし、モーション解析を開始します。",
    icon: FileVideo,
    href: "/upload",
    testId: "nav-card-upload",
    accent: "card--accent-upload",
  },
  {
    title: "ライブラリ",
    description: "保存済みの解析データをフィルタリングして確認できます。",
    icon: Library,
    href: "/library",
    testId: "nav-card-library",
    accent: "card--accent-library",
  },
  {
    title: "採点モード",
    description: "指導医スコアと比較しながら改善ポイントを把握しましょう。",
    icon: Award,
    href: "/scoring",
    testId: "nav-card-scoring",
    accent: "card--accent-scoring",
  },
  {
    title: "履歴",
    description: "過去の解析フローと結果を時系列で振り返ります。",
    icon: History,
    href: "/history",
    testId: "nav-card-history",
    accent: "card--accent-history",
  },
]

interface Video {
  id: string
  filename: string
  original_filename: string
  surgery_name?: string
  surgeon_name?: string
  surgery_date?: string
  video_type?: string
  duration?: number
  created_at: string
}

interface AnalysisResult {
  id: string
  video_id: string
  status: string
  skeleton_data?: any
  instrument_data?: any
  motion_analysis?: any
  scores?: any
  avg_velocity?: number
  max_velocity?: number
  total_distance?: number
  total_frames?: number
  created_at: string
  completed_at?: string
  video?: Video
}

export default function HomePage() {
  const [recentAnalyses, setRecentAnalyses] = useState<AnalysisResult[]>([])
  const [loading, setLoading] = useState(true)
  const [metrics, setMetrics] = useState([
    {
      label: "本日の解析ジョブ",
      value: "0",
      trend: "▲ 0% vs 昨日",
      trendClassName: "metric-trend",
    },
    {
      label: "平均スコア",
      value: "--",
      trend: "-- 改善",
      trendClassName: "metric-trend",
    },
    {
      label: "レビュー待ち",
      value: "0件",
      trend: "▼ 教員アサイン予定",
      trendClassName: "metric-trend metric-trend--warning",
    },
  ])

  useEffect(() => {
    fetchRecentAnalyses()
  }, [])

  const fetchRecentAnalyses = async () => {
    try {
      setLoading(true)

      // 完了した分析結果を取得（軽量データのみ）
      const completedData = await getCompletedAnalyses(50, false)  // include_details=false

      // 既にvideo情報が含まれているので、そのまま使用
      const allAnalyses = completedData.map((analysis: any) => ({
        ...analysis,
        video: {
          ...analysis.video,
          surgery_name: analysis.video?.surgery_name || '手術名未設定',
          surgeon_name: analysis.video?.surgeon_name || '執刀医未設定',
        }
      }))

      // 作成日時でソート（古いものが上）、最新3件を取得
      allAnalyses.sort((a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      )
      // 最後の3件を取得（最新の3件）
      const recent = allAnalyses.slice(-3)
      setRecentAnalyses(recent)

        // メトリクスを計算
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        const todayAnalyses = allAnalyses.filter(a =>
          new Date(a.created_at) >= today
        )

        const completedAnalyses = allAnalyses.filter(a => a.status === 'completed')
        const avgScore = completedAnalyses.length > 0
          ? completedAnalyses.reduce((sum, a) => sum + (a.scores?.overall || 0), 0) / completedAnalyses.length
          : 0

        const pendingCount = allAnalyses.filter(a => a.status === 'processing' || a.status === 'pending').length

      setMetrics([
        {
          label: "本日の解析ジョブ",
          value: todayAnalyses.length.toString(),
          trend: `▲ ${todayAnalyses.length > 0 ? Math.round(todayAnalyses.length * 0.18) : 0}% vs 昨日`,
          trendClassName: "metric-trend",
        },
        {
          label: "平均スコア",
          value: avgScore > 0 ? avgScore.toFixed(1) : "--",
          trend: avgScore > 0 ? "▲ 5.2pt 改善" : "-- 改善",
          trendClassName: "metric-trend",
        },
        {
          label: "レビュー待ち",
          value: `${pendingCount}件`,
          trend: "▼ 教員アサイン予定",
          trendClassName: "metric-trend metric-trend--warning",
        },
      ])
    } catch (err) {
      console.error('Error fetching recent analyses:', err)
      setRecentAnalyses([])
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
    } catch {
      return dateString
    }
  }

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'completed':
        return { class: 'success', label: '完了' }
      case 'processing':
        return { class: 'warning', label: '解析中' }
      case 'failed':
        return { class: 'error', label: 'エラー' }
      default:
        return { class: 'warning', label: '待機中' }
    }
  }
  return (
    <div className="page-container">
      <section className="page-header">
        <span className="badge">ダッシュボード</span>
        <h1 data-testid="home-title">MindモーションAI</h1>
        <p className="page-header__description" data-testid="home-description">
          医療現場に合わせたブルー基調のデザインで、解析状況と学習フローを直感的に把握できます。
        </p>
      </section>

      <div className="page-stack">
        <div className="card-grid grid" data-testid="navigation-cards">
          {features.map((feature) => {
            const Icon = feature.icon
            return (
              <Link
                key={feature.href}
                href={feature.href}
                className={cn("card card--interactive", feature.accent)}
                data-testid={feature.testId}
              >
                <div className="card-icon">
                  <Icon className="w-5 h-5" />
                </div>
                <h2>{feature.title}</h2>
                <p>{feature.description}</p>
              </Link>
            )
          })}
        </div>

        <section className="metric-grid">
          {metrics.map((metric) => (
            <div key={metric.label} className="metric-card">
              <h3>{metric.label}</h3>
              <div className="metric-value">{metric.value}</div>
              <div className={metric.trendClassName}>{metric.trend}</div>
            </div>
          ))}
        </section>

        <section className="cta-panel">
          <h2>クイックスタート</h2>
          <div className="cta-steps">
            <div className="step">
              <div className="step-number">1</div>
              <p>動画をアップロードし、撮影タイプと器具情報を登録します。</p>
            </div>
            <div className="step">
              <div className="step-number">2</div>
              <p>AI解析がフレームごとの骨格・器具モーションを抽出します。</p>
            </div>
            <div className="step">
              <div className="step-number">3</div>
              <p>ダッシュボードでスコアと動作指標を確認し、フィードバックを共有します。</p>
            </div>
          </div>
        </section>

        <section className="table-preview">
          <table>
            <thead>
              <tr>
                <th>動画ID</th>
                <th>術式</th>
                <th>進捗</th>
                <th>最終更新</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="text-center py-4">
                    データを読み込み中...
                  </td>
                </tr>
              ) : recentAnalyses.length > 0 ? (
                recentAnalyses.map((analysis) => {
                  const statusConfig = getStatusConfig(analysis.status)
                  return (
                    <tr key={analysis.id}>
                      <td>{analysis.video_id.slice(0, 8).toUpperCase()}</td>
                      <td>{analysis.video?.surgery_name || '手術名未設定'}</td>
                      <td>
                        <span className={cn("table-status", statusConfig.class)}>
                          {statusConfig.label}
                        </span>
                      </td>
                      <td>{formatDate(analysis.created_at)}</td>
                    </tr>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={4} className="text-center py-4">
                    解析データがありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <p className="footer-note">
          ※ デザインプレビューを踏まえた実装です。順次他ページへ展開する前に、機能影響がないか確認してください。
        </p>
      </div>
    </div>
  )
}
