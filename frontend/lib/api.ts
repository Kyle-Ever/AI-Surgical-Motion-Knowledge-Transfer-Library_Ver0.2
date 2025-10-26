import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'

// Axios インスタンスを作成
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,  // 30秒タイムアウト（ngrok経由を考慮）
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
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001'

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
export const getCompletedAnalyses = async (
  limit: number = 50,
  includeDetails: boolean = false  // デフォルトで軽量データのみ取得
): Promise<AnalysisResult[]> => {
  // axiosを使用してタイムアウトとエラーハンドリングを改善
  // includeDetails=false で重いデータ（skeleton_data等）を除外し、高速化
  try {
    const response = await api.get('/analysis/completed', {
      params: {
        include_failed: true,
        limit: limit,
        include_details: includeDetails  // バックエンドに渡す
      },
      // includeDetails=true の場合は長めのタイムアウト
      timeout: includeDetails ? 60000 : 15000
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNABORTED') {
        throw new Error('リクエストがタイムアウトしました。もう一度お試しください。');
      } else if (error.response) {
        throw new Error(`サーバーエラー: ${error.response.status}`);
      } else if (error.request) {
        throw new Error('バックエンドに接続できません。サーバーが起動しているか確認してください。');
      }
    }
    throw error;
  }
};

// 採点結果を取得
export const getCompletedComparisons = async (): Promise<any[]> => {
  try {
    // 正しいエンドポイント: /scoring/comparisons
    const response = await api.get('/scoring/comparisons', {
      params: {
        status: 'completed' // フィルタでcompletedのみ取得
      },
      timeout: 10000
    });
    return response.data;
  } catch (error) {
    // エラーが発生しても空配列を返す（採点結果はオプショナル）
    console.warn('Failed to fetch comparisons:', error);
    return [];
  }
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