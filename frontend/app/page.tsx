"use client"

import Link from "next/link"
import { FileVideo, Library, Award, History } from "lucide-react"
import { cn } from "@/lib/utils"

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

const metrics = [
  {
    label: "本日の解析ジョブ",
    value: "12",
    trend: "▲ 18% vs 昨日",
    trendClassName: "metric-trend",
  },
  {
    label: "平均スコア",
    value: "82.6",
    trend: "▲ 5.2pt 改善",
    trendClassName: "metric-trend",
  },
  {
    label: "レビュー待ち",
    value: "3件",
    trend: "▼ 教員アサイン予定",
    trendClassName: "metric-trend metric-trend--warning",
  },
]

const jobs = [
  {
    id: "VID-2034",
    procedure: "腹腔鏡下胆嚢摘出",
    status: "success" as const,
    statusLabel: "完了",
    updatedAt: "2025-09-17 09:20",
  },
  {
    id: "VID-2035",
    procedure: "冠動脈バイパス",
    status: "warning" as const,
    statusLabel: "解析中",
    updatedAt: "2025-09-17 09:05",
  },
  {
    id: "VID-2036",
    procedure: "腹腔鏡下結腸切除",
    status: "error" as const,
    statusLabel: "エラー",
    updatedAt: "2025-09-17 08:47",
  },
]

export default function HomePage() {
  return (
    <div className="page-container">
      <section className="page-header">
        <span className="badge">ダッシュボード</span>
        <h1 data-testid="home-title">AI手技モーション伝承ライブラリ</h1>
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
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.id}</td>
                  <td>{job.procedure}</td>
                  <td>
                    <span className={cn("table-status", job.status)}>{job.statusLabel}</span>
                  </td>
                  <td>{job.updatedAt}</td>
                </tr>
              ))}
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
