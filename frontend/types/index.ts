// Barrel file - re-export all types from domain-specific files
export * from './analysis'

export interface ProcessingStep {
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  message?: string
}
