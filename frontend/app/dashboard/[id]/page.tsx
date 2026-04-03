import DashboardClient from './DashboardClient'

export default async function DashboardPage({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  // IDをサニタイズ: UUID部分のみを抽出（スペースや日本語が含まれている場合に対応）
  // 例: "f88cc4cf-54a8-4696-b8dc-71aa8e751009　器具検出①" → "f88cc4cf-54a8-4696-b8dc-71aa8e751009"
  const sanitizedId = id.match(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/i)?.[0] || id

  return <DashboardClient analysisId={sanitizedId} />
}