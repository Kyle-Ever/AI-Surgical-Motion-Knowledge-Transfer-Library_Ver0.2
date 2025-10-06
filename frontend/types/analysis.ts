// Analysis related type definitions

export interface Coordinate {
  x: number
  y: number
  z?: number
}

export interface HandDetection {
  hand_type?: 'Left' | 'Right'
  landmarks: Record<string, Coordinate>
  palm_center?: Coordinate
  finger_angles?: Record<string, number>
  hand_openness?: number
}

export interface SkeletonData {
  frame: number
  frame_number?: number
  timestamp?: number
  hands: HandDetection[]
  landmarks?: Record<string, Coordinate>
  hand_type?: 'Left' | 'Right'
}

export interface InstrumentDetection {
  class: string
  confidence: number
  bbox: {
    x: number
    y: number
    width: number
    height: number
  }
  track_id?: number
}

export interface InstrumentData {
  frame: number
  frame_number?: number
  timestamp?: number
  detections: InstrumentDetection[]
}

export interface VelocityAnalysis {
  avg_velocity: number
  max_velocity: number
  velocity_variance: number
  time_series?: number[]
}

export interface TrajectoryAnalysis {
  total_distance: number
  smoothness: number
  path_efficiency: number
}

export interface StabilityAnalysis {
  tremor_level: number
  consistency: number
  precision: number
}

export interface EfficiencyAnalysis {
  time_efficiency: number
  motion_economy: number
  redundancy: number
}

export interface MotionAnalysis {
  速度解析: VelocityAnalysis
  軌跡解析: TrajectoryAnalysis
  安定性解析: StabilityAnalysis
  効率性解析: EfficiencyAnalysis
  metrics?: Record<string, any>
}

export interface Scores {
  速度スコア: number
  精度スコア: number
  安定性スコア: number
  効率性スコア: number
  total_score: number
}

export interface AnalysisResult {
  id: string
  video_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  skeleton_data: SkeletonData[]
  instrument_data: InstrumentData[]
  motion_analysis: MotionAnalysis
  scores: Scores
  total_frames: number
  progress: number
  error_message?: string
  completed_at?: string
  current_step?: string
}

export interface ComparisonFeedback {
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
}

export interface ComparisonResult {
  id?: string
  learner_analysis_id: string
  reference_analysis_id: string
  overall_score: number
  feedback: ComparisonFeedback
  metric_comparison: Record<string, number>
  dtw_distance?: number  // 追加
  created_at?: string
}

export interface VideoInfo {
  width: number
  height: number
  fps: number
  total_frames: number
  duration: number
}

// WebSocket status interface
export interface AnalysisStatus {
  analysisId?: string
  analysis_id?: string  // バックエンドの命名規則との互換性
  status: string
  overallProgress?: number
  overall_progress?: number  // バックエンドの命名規則との互換性
  currentStep?: string
  current_step?: string  // バックエンドの命名規則との互換性
  estimatedTimeRemaining?: number
  estimated_time_remaining?: number  // バックエンドの命名規則との互換性
  message?: string
}