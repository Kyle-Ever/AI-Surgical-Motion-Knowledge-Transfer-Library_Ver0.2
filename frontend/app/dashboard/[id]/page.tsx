import DashboardClient from './DashboardClient'
import GazeDashboardClient from '@/components/GazeDashboardClient'
// import DashboardClient from './DashboardClientWithMock' // モックデータ付きバージョン

async function getAnalysisType(analysisId: string): Promise<string | null> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
    const response = await fetch(`${apiUrl}/analysis/${analysisId}`, {
      cache: 'no-store'
    })

    if (!response.ok) {
      console.error('Failed to fetch analysis type:', response.statusText)
      return null
    }

    const data = await response.json()
    return data.video?.video_type || null
  } catch (error) {
    console.error('Error fetching analysis type:', error)
    return null
  }
}

export default async function DashboardPage({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const videoType = await getAnalysisType(id)

  // 視線解析の場合は専用ダッシュボードを表示
  if (videoType === 'eye_gaze') {
    return <GazeDashboardClient analysisId={id} />
  }

  // それ以外は既存のダッシュボード
  return <DashboardClient analysisId={id} />
}