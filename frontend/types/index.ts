export interface Video {
  id: string
  filename: string
  originalFilename: string
  videoType: 'internal' | 'external'
  surgeryName?: string
  surgeryDate?: string
  surgeonName?: string
  memo?: string
  createdAt: Date
  updatedAt: Date
}

export interface AnalysisResult {
  id: string
  videoId: string
  status: 'processing' | 'completed' | 'failed'
  coordinateData?: any
  velocityData?: any
  angleData?: any
  avgVelocity?: number
  totalDistance?: number
  totalFrames?: number
  createdAt: Date
}

export interface Instrument {
  id: string
  videoId: string
  name: string
  annotationData: any
  modelData?: any
  createdAt: Date
}

export interface ProcessingStep {
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  message?: string
}

export interface AnalysisStatus {
  analysisId: string
  videoId: string
  overallProgress: number
  steps: ProcessingStep[]
  estimatedTimeRemaining?: number
}