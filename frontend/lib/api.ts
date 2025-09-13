import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// Axios インスタンスを作成
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// リクエストインターセプター
api.interceptors.request.use(
  (config) => {
    // 必要に応じてトークンを追加（将来的な認証用）
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// レスポンスインターセプター
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response) {
      // サーバーからエラーレスポンスが返ってきた場合
      console.error('API Error:', error.response.data)
      
      // エラーメッセージの統一処理
      const message = error.response.data?.detail || 
                     error.response.data?.message || 
                     'エラーが発生しました'
      
      // エラーオブジェクトにメッセージを追加
      error.message = message
    } else if (error.request) {
      // リクエストは送信されたがレスポンスがない
      console.error('Network Error:', error.request)
      error.message = 'ネットワークエラーが発生しました'
    } else {
      // リクエスト設定時のエラー
      console.error('Request Error:', error.message)
    }
    
    return Promise.reject(error)
  }
)

// API エンドポイント
export const endpoints = {
  // 動画関連
  videos: {
    upload: '/videos/upload',
    get: (id: string) => `/videos/${id}`,
    list: '/videos',
  },
  
  // 解析関連
  analysis: {
    start: (videoId: string) => `/analysis/${videoId}/analyze`,
    status: (analysisId: string) => `/analysis/${analysisId}/status`,
    result: (analysisId: string) => `/analysis/${analysisId}`,
    export: (analysisId: string) => `/analysis/${analysisId}/export`,
  },
  
  // ライブラリ関連
  library: {
    list: '/library',
    get: (id: string) => `/library/${id}`,
    save: '/library',
  },
}

// WebSocket URL
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'

export const wsEndpoints = {
  analysis: (analysisId: string) => `${WS_BASE_URL}/analysis/${analysisId}`,
}