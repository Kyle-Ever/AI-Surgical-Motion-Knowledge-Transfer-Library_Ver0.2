import AnalysisClient from './AnalysisClient'

export default async function AnalysisPage({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  return <AnalysisClient analysisId={id} />
}