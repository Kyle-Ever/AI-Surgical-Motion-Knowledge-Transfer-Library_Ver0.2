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
    upload: '/api/v1/videos/upload',
    get: (id: string) => `/api/v1/videos/${id}`,
    list: '/api/v1/videos',
  },

  // 解析関連
  analysis: {
    start: (videoId: string) => `/api/v1/analysis/${videoId}/analyze`,
    status: (analysisId: string) => `/api/v1/analysis/${analysisId}/status`,
    result: (analysisId: string) => `/api/v1/analysis/${analysisId}`,
    export: (analysisId: string) => `/api/v1/analysis/${analysisId}/export`,
  },

  // ライブラリ関連
  library: {
    list: '/api/v1/library',
    get: (id: string) => `/api/v1/library/${id}`,
    save: '/api/v1/library',
  },
}

// WebSocket URL
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export const wsEndpoints = {
  analysis: (analysisId: string) => `${WS_BASE_URL}/ws/analysis/${analysisId}`,
}

// 型定義
export interface AnalysisResult {
  id: string;
  video_id: string;
  video_type: string;
  status: string;
  skeleton_data?: any;
  instrument_data?: any;
  motion_analysis?: any;
  scores?: any;
  avg_velocity?: number;
  max_velocity?: number;
  total_distance?: number;
  total_frames?: number;
  created_at: string;
  completed_at?: string;
  video?: {
    id: string;
    filename: string;
    original_filename: string;
    video_type: string;
    duration: number;
    fps: number;
    width: number;
    height: number;
    file_size: number;
    created_at: string;
  };
}

// ライブラリ関連の関数
export const getCompletedAnalyses = async (): Promise<AnalysisResult[]> => {
  const response = await fetch(`${API_BASE_URL}/analysis/completed`);
  if (!response.ok) {
    throw new Error('Failed to fetch completed analyses');
  }
  return response.json();
};

export const exportAnalysisData = async (analysisId: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/export`);
  if (!response.ok) {
    throw new Error('Failed to export analysis data');
  }

  // CSVファイルとしてダウンロード
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `analysis_${analysisId}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};