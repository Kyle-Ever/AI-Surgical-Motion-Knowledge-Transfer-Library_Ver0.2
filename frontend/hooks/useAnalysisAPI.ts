// 分析APIを呼び出すカスタムフック
import { useState, useEffect } from 'react';
import axios from 'axios';

interface AnalysisData {
  id: string;
  video_id: string;
  skeleton_data?: any[];
  motion_metrics?: any;
  overall_score?: number;
  speed_score?: number;
  smoothness_score?: number;
  stability_score?: number;
  status?: string;
}

export const useAnalysisAPI = (videoId: string | null | undefined) => {
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // 動画に対して分析を開始
  const startAnalysis = async (videoId: string): Promise<string | null> => {
    try {
      const response = await axios.post(
        `http://localhost:8000/api/v1/analysis/${videoId}/analyze`,
        {
          instruments: [],
          sampling_rate: 1
        }
      );
      return response.data.id;
    } catch (error) {
      console.error('Failed to start analysis:', error);
      return null;
    }
  };

  // 分析ステータスを確認
  const checkAnalysisStatus = async (analysisId: string): Promise<AnalysisData | null> => {
    try {
      const response = await axios.get(
        `http://localhost:8000/api/v1/analysis/${analysisId}`
      );
      return response.data;
    } catch (error) {
      console.error('Failed to check analysis status:', error);
      return null;
    }
  };

  // 分析が完了するまで待つ
  const waitForCompletion = async (analysisId: string, maxWaitTime: number = 60000): Promise<AnalysisData | null> => {
    const startTime = Date.now();
    const pollInterval = 2000;

    while (Date.now() - startTime < maxWaitTime) {
      const analysis = await checkAnalysisStatus(analysisId);

      if (analysis?.status === 'completed') {
        return analysis;
      }

      if (analysis?.status === 'failed') {
        throw new Error('Analysis failed');
      }

      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }

    throw new Error('Analysis timeout');
  };

  useEffect(() => {
    if (!videoId) {
      console.log('useAnalysisAPI: No videoId provided');
      return;
    }

    console.log('useAnalysisAPI: Starting analysis for video:', videoId);

    const runAnalysis = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // まず既存の完了した分析結果を確認（エンドポイントが存在しない場合は新規分析）
        let existingResponse = null;
        try {
          // 動画の最新の分析結果を取得
          const analysesResponse = await axios.get(
            `http://localhost:8000/api/v1/analysis/completed?include_failed=false`
          );
          const analyses = analysesResponse.data;
          existingResponse = analyses.find((a: any) => a.video_id === videoId && a.status === 'completed');
        } catch (err) {
          console.log('既存の分析結果を検索中...');
        }

        if (existingResponse?.status === 'completed') {
          console.log('useAnalysisAPI: Found existing analysis:', existingResponse.id);
          setAnalysis(existingResponse);
        } else {
          // 新しい分析を開始
          console.log('useAnalysisAPI: Starting new analysis for video:', videoId);
          const analysisId = await startAnalysis(videoId);
          if (analysisId) {
            console.log('useAnalysisAPI: Analysis started with ID:', analysisId);
            const result = await waitForCompletion(analysisId);
            if (result) {
              console.log('useAnalysisAPI: Analysis completed:', result);
              setAnalysis(result);
            }
          } else {
            console.log('useAnalysisAPI: Failed to start analysis');
          }
        }
      } catch (err) {
        setError(err as Error);
        console.error('Analysis error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    runAnalysis();
  }, [videoId]);

  return { analysis, isLoading, error };
};

// 比較用に2つの動画を分析
export const useDualAnalysis = (refVideoId?: string, evalVideoId?: string) => {
  const refAnalysis = useAnalysisAPI(refVideoId);
  const evalAnalysis = useAnalysisAPI(evalVideoId);

  return {
    referenceAnalysis: refAnalysis.analysis,
    evaluationAnalysis: evalAnalysis.analysis,
    isLoading: refAnalysis.isLoading || evalAnalysis.isLoading,
    error: refAnalysis.error || evalAnalysis.error
  };
};