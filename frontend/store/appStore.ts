import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { AnalysisResult, VideoInfo } from '@/types/analysis'

// Video関連の状態
interface VideoState {
  videos: Array<{
    id: string
    filename: string
    uploaded_at: string
    file_size: number
    duration: number
    video_type: string
  }>
  currentVideo: string | null
  uploadProgress: number
  isUploading: boolean
  setVideos: (videos: VideoState['videos']) => void
  addVideo: (video: VideoState['videos'][0]) => void
  setCurrentVideo: (id: string | null) => void
  setUploadProgress: (progress: number) => void
  setIsUploading: (isUploading: boolean) => void
}

// Analysis関連の状態
interface AnalysisState {
  analyses: Record<string, AnalysisResult>
  currentAnalysis: string | null
  analysisProgress: Record<string, number>
  isAnalyzing: boolean
  setAnalyses: (analyses: Record<string, AnalysisResult>) => void
  addAnalysis: (analysis: AnalysisResult) => void
  updateAnalysis: (id: string, updates: Partial<AnalysisResult>) => void
  setCurrentAnalysis: (id: string | null) => void
  updateProgress: (id: string, progress: number) => void
  setIsAnalyzing: (isAnalyzing: boolean) => void
}

// UI関連の状態
interface UIState {
  sidebarOpen: boolean
  theme: 'light' | 'dark'
  notifications: Array<{
    id: string
    type: 'success' | 'error' | 'warning' | 'info'
    message: string
    timestamp: number
  }>
  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark') => void
  addNotification: (notification: Omit<UIState['notifications'][0], 'id' | 'timestamp'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
}

// WebSocket関連の状態
interface WebSocketState {
  connections: Record<string, boolean>
  messages: Record<string, any[]>
  setConnectionStatus: (id: string, connected: boolean) => void
  addMessage: (id: string, message: any) => void
  clearMessages: (id: string) => void
}

// 統合ストア
export const useAppStore = create<
  VideoState & AnalysisState & UIState & WebSocketState
>()(
  devtools(
    persist(
      (set, get) => ({
        // Video State
        videos: [],
        currentVideo: null,
        uploadProgress: 0,
        isUploading: false,
        setVideos: (videos) => set({ videos }),
        addVideo: (video) => set((state) => ({
          videos: [...state.videos, video]
        })),
        setCurrentVideo: (id) => set({ currentVideo: id }),
        setUploadProgress: (progress) => set({ uploadProgress: progress }),
        setIsUploading: (isUploading) => set({ isUploading }),

        // Analysis State
        analyses: {},
        currentAnalysis: null,
        analysisProgress: {},
        isAnalyzing: false,
        setAnalyses: (analyses) => set({ analyses }),
        addAnalysis: (analysis) => set((state) => ({
          analyses: { ...state.analyses, [analysis.id]: analysis }
        })),
        updateAnalysis: (id, updates) => set((state) => ({
          analyses: {
            ...state.analyses,
            [id]: { ...state.analyses[id], ...updates }
          }
        })),
        setCurrentAnalysis: (id) => set({ currentAnalysis: id }),
        updateProgress: (id, progress) => set((state) => ({
          analysisProgress: { ...state.analysisProgress, [id]: progress }
        })),
        setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),

        // UI State
        sidebarOpen: true,
        theme: 'light',
        notifications: [],
        toggleSidebar: () => set((state) => ({
          sidebarOpen: !state.sidebarOpen
        })),
        setTheme: (theme) => set({ theme }),
        addNotification: (notification) => set((state) => ({
          notifications: [
            ...state.notifications,
            {
              ...notification,
              id: Date.now().toString(),
              timestamp: Date.now()
            }
          ].slice(-10) // 最新10件のみ保持
        })),
        removeNotification: (id) => set((state) => ({
          notifications: state.notifications.filter(n => n.id !== id)
        })),
        clearNotifications: () => set({ notifications: [] }),

        // WebSocket State
        connections: {},
        messages: {},
        setConnectionStatus: (id, connected) => set((state) => ({
          connections: { ...state.connections, [id]: connected }
        })),
        addMessage: (id, message) => set((state) => ({
          messages: {
            ...state.messages,
            [id]: [...(state.messages[id] || []), message].slice(-100) // 最新100件のみ保持
          }
        })),
        clearMessages: (id) => set((state) => ({
          messages: { ...state.messages, [id]: [] }
        }))
      }),
      {
        name: 'app-store',
        partialize: (state) => ({
          // 永続化する状態を選択
          theme: state.theme,
          sidebarOpen: state.sidebarOpen
        })
      }
    )
  )
)

// セレクター関数
export const useCurrentVideo = () => {
  const currentVideo = useAppStore(state => state.currentVideo)
  const videos = useAppStore(state => state.videos)
  return videos.find(v => v.id === currentVideo)
}

export const useCurrentAnalysis = () => {
  const currentAnalysis = useAppStore(state => state.currentAnalysis)
  const analyses = useAppStore(state => state.analyses)
  return currentAnalysis ? analyses[currentAnalysis] : null
}

export const useAnalysisProgress = (analysisId: string) => {
  return useAppStore(state => state.analysisProgress[analysisId] || 0)
}

export const useConnectionStatus = (connectionId: string) => {
  return useAppStore(state => state.connections[connectionId] || false)
}