/**
 * Motion metrics calculation utilities.
 *
 * Extracted from MotionAnalysisPanel to eliminate duplication between
 * hand metrics, instrument metrics, and waste metrics calculations.
 */

export interface Position {
  x: number
  y: number
  timestamp?: number
}

export interface RealtimeMetrics {
  speed: number
  smoothness: number
  accuracy: number
}

/**
 * Calculate velocities from a series of positions.
 */
export function calculateVelocities(positions: Array<Position | null>): number[] {
  const velocities: number[] = []
  for (let i = 1; i < positions.length; i++) {
    if (positions[i] && positions[i - 1]) {
      const dx = positions[i]!.x - positions[i - 1]!.x
      const dy = positions[i]!.y - positions[i - 1]!.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      const dt = (positions[i]!.timestamp ?? 0) - (positions[i - 1]!.timestamp ?? 0)
      velocities.push(dt > 0 ? distance / dt : 0)
    }
  }
  return velocities
}

/**
 * Calculate smoothness score from velocities using coefficient of variation.
 * CV=0 → 100, CV=1 → ~69, CV=5 → ~38, CV=10 → ~10
 */
export function calculateSmoothnessScore(velocities: number[]): number {
  if (velocities.length === 0) return 0
  const mean = velocities.reduce((a, b) => a + b, 0) / velocities.length
  if (mean <= 0) return 100
  const stdDev = Math.sqrt(
    velocities.reduce((sum, v) => sum + ((v - mean) ** 2), 0) / velocities.length
  )
  const cv = stdDev / mean
  return cv > 0
    ? Math.max(0, Math.min(100, 100 * Math.exp(-cv / 3)))
    : 100
}

/**
 * Calculate path efficiency (straight-line distance / actual distance).
 * Mapped to 0-100 score with gentle curve.
 */
export function calculatePathEfficiency(positions: Array<{ x: number; y: number }>): number {
  if (positions.length < 2) return 0

  const start = positions[0]
  const end = positions[positions.length - 1]
  const straightDistance = Math.sqrt(
    (end.x - start.x) ** 2 + (end.y - start.y) ** 2
  )

  let actualDistance = 0
  for (let i = 1; i < positions.length; i++) {
    const dx = positions[i].x - positions[i - 1].x
    const dy = positions[i].y - positions[i - 1].y
    actualDistance += Math.sqrt(dx * dx + dy * dy)
  }

  if (actualDistance <= 0.001 || straightDistance <= 0.001) return 0

  const efficiency = straightDistance / actualDistance
  return Math.max(0, Math.min(100, Math.pow(efficiency, 0.3) * 100))
}

/**
 * Calculate all realtime metrics from positions.
 * Common logic used by hand, instrument, and waste metrics.
 */
export function calculateRealtimeMetricsFromPositions(
  positions: Array<Position | null>,
  speedDivisor: number = 20
): RealtimeMetrics {
  const validCount = positions.filter(p => p !== null).length
  if (validCount < 2) return { speed: 0, smoothness: 0, accuracy: 0 }

  const velocities = calculateVelocities(positions)
  const avgVelocity = velocities.length > 0
    ? velocities.reduce((a, b) => a + b, 0) / velocities.length
    : 0

  const smoothness = calculateSmoothnessScore(velocities)
  const validPositions = positions.filter(p => p !== null) as Array<{ x: number; y: number }>
  const accuracy = calculatePathEfficiency(validPositions)
  const speed = Math.min(Math.max(avgVelocity / speedDivisor, 0), 100)

  return { speed, smoothness, accuracy }
}
