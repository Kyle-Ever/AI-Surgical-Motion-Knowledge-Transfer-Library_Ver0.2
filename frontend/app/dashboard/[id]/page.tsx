import DashboardClient from './DashboardClient'
// import DashboardClient from './DashboardClientWithMock' // モックデータ付きバージョン

export default async function DashboardPage({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  return <DashboardClient analysisId={id} />
}