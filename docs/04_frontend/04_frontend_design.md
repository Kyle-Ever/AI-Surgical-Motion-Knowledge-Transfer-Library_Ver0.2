# フロントエンド設計書 - AI Surgical Motion Knowledge Transfer Library

## 目次
1. [アーキテクチャ概要](#アーキテクチャ概要)
2. [ディレクトリ構造](#ディレクトリ構造)
3. [コンポーネント設計](#コンポーネント設計)
4. [状態管理](#状態管理)
5. [ルーティング設計](#ルーティング設計)
6. [型定義](#型定義)
7. [スタイリング](#スタイリング)
8. [パフォーマンス最適化](#パフォーマンス最適化)

## アーキテクチャ概要

### 技術スタック
```yaml
フレームワーク: Next.js 15.5.2
言語: TypeScript
状態管理: Zustand v5.0.8
スタイリング: Tailwind CSS v4
UIライブラリ: Radix UI, Headless UI
チャート: Chart.js v4.5.0, Recharts v3.2.1
3D: Three.js + @react-three/fiber
テスト: Playwright v1.55.0
```

### 設計原則
1. **コンポーネント駆動開発**: 再利用可能な小さな単位から構築
2. **型安全性**: TypeScriptによる完全な型定義
3. **パフォーマンスファースト**: Code Splitting、Lazy Loading
4. **アクセシビリティ**: WCAG 2.1準拠

## ディレクトリ構造

```
frontend/
├── app/                      # Next.js App Router
│   ├── (auth)/              # 認証が必要なルート
│   ├── api/                 # API Routes
│   ├── layout.tsx           # ルートレイアウト
│   ├── page.tsx             # ホームページ
│   └── global.css           # グローバルスタイル
├── components/              # 再利用可能なコンポーネント
│   ├── ui/                  # 基本UIコンポーネント
│   ├── features/            # 機能別コンポーネント
│   └── layouts/             # レイアウトコンポーネント
├── hooks/                   # カスタムフック
├── lib/                     # ユーティリティ関数
├── stores/                  # Zustand ストア
├── types/                   # TypeScript型定義
├── utils/                   # ヘルパー関数
└── public/                  # 静的ファイル
```

## コンポーネント設計

### コンポーネント分類

#### 1. UIコンポーネント（`components/ui/`）
```typescript
// 責務: プレゼンテーションのみ、ビジネスロジックを含まない
// 例: Button, Card, Modal, Input

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}

// 使用例
<Button variant="primary" size="md" onClick={handleClick}>
  アップロード
</Button>
```

#### 2. 機能コンポーネント（`components/features/`）
```typescript
// 責務: 特定の機能を実装、ビジネスロジックを含む
// 例: VideoUploader, AnalysisChart, ScoreCard

interface VideoUploaderProps {
  onUploadComplete: (videoId: number) => void;
  maxFileSize?: number;
  acceptedFormats?: string[];
}

// 内部でAPIコール、状態管理、エラーハンドリングを実装
```

#### 3. レイアウトコンポーネント（`components/layouts/`）
```typescript
// 責務: ページレイアウトの管理
// 例: Header, Footer, Sidebar, MainLayout

interface MainLayoutProps {
  children: React.ReactNode;
  sidebar?: boolean;
}
```

### コンポーネント設計原則

#### Props設計
```typescript
// ✅ Good: 明確で必要最小限
interface VideoPlayerProps {
  videoId: number;
  autoPlay?: boolean;
  onTimeUpdate?: (time: number) => void;
}

// ❌ Bad: 過度に複雑
interface VideoPlayerProps {
  video: Video;
  settings: PlayerSettings;
  callbacks: PlayerCallbacks;
  // ...多数のprops
}
```

#### コンポーネントの責任範囲
```typescript
// ✅ Good: 単一責任
const VideoUploadButton = ({ onUpload }) => {
  // アップロードのみを担当
};

// ❌ Bad: 複数の責任
const VideoManager = () => {
  // アップロード、削除、編集、分析すべてを担当
};
```

## 状態管理

### Zustandストア設計
```typescript
// stores/videoStore.ts
interface VideoStore {
  // State
  videos: Video[];
  selectedVideo: Video | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setVideos: (videos: Video[]) => void;
  selectVideo: (video: Video) => void;
  addVideo: (video: Video) => void;
  updateVideo: (id: number, updates: Partial<Video>) => void;
  deleteVideo: (id: number) => void;
  fetchVideos: () => Promise<void>;
}

// 使用例
const useVideoStore = create<VideoStore>((set, get) => ({
  videos: [],
  selectedVideo: null,
  isLoading: false,
  error: null,

  setVideos: (videos) => set({ videos }),
  selectVideo: (video) => set({ selectedVideo: video }),

  fetchVideos: async () => {
    set({ isLoading: true, error: null });
    try {
      const videos = await api.getVideos();
      set({ videos, isLoading: false });
    } catch (error) {
      set({ error: error.message, isLoading: false });
    }
  },
}));
```

### 状態管理の原則
1. **グローバル状態は最小限**: 本当に共有が必要なもののみ
2. **ローカル状態を優先**: コンポーネント内で完結するものはuseState
3. **派生状態は計算**: 保存せずに計算で求める

## ルーティング設計

### ページ構造
```
app/
├── page.tsx                      # / - ホーム
├── videos/
│   ├── page.tsx                  # /videos - 動画一覧
│   └── [id]/
│       └── page.tsx              # /videos/[id] - 動画詳細
├── analysis/
│   ├── page.tsx                  # /analysis - 分析一覧
│   └── [id]/
│       └── page.tsx              # /analysis/[id] - 分析結果
├── scoring/
│   ├── page.tsx                  # /scoring - スコアリング
│   ├── comparison/
│   │   └── page.tsx              # /scoring/comparison - 比較画面
│   └── result/
│       └── [id]/
│           └── page.tsx          # /scoring/result/[id] - 結果
└── library/
    └── page.tsx                  # /library - ライブラリ
```

### 動的ルーティング
```typescript
// app/videos/[id]/page.tsx
interface PageProps {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
}

export default async function VideoDetailPage({ params }: PageProps) {
  const video = await getVideo(params.id);
  return <VideoDetail video={video} />;
}
```

## 型定義

### ドメインモデル
```typescript
// types/models.ts

export interface Video {
  id: number;
  filename: string;
  originalFilename: string;
  fileSize: number;
  duration: number;
  fps: number;
  width: number;
  height: number;
  status: VideoStatus;
  createdAt: string;
  updatedAt: string;
}

export type VideoStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface Analysis {
  id: number;
  videoId: number;
  detectionType: DetectionType;
  status: AnalysisStatus;
  metricsData?: MetricsData;
  feedback?: Feedback;
  createdAt: string;
}

export type DetectionType = 'external' | 'internal' | 'hybrid';
export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface MetricsData {
  speed: number;
  smoothness: number;
  stability: number;
  efficiency: number;
}

export interface Feedback {
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}
```

### APIレスポンス型
```typescript
// types/api.ts

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta?: ApiMeta;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

export interface ApiMeta {
  timestamp: string;
  version: string;
  page?: number;
  totalPages?: number;
  total?: number;
}

// 使用例
type VideoListResponse = ApiResponse<Video[]>;
type VideoUploadResponse = ApiResponse<{ videoId: number; message: string }>;
```

### フォーム型
```typescript
// types/forms.ts

export interface VideoUploadForm {
  file: File;
}

export interface AnalysisConfigForm {
  detectionType: DetectionType;
  analysisType: 'full' | 'quick';
}

export interface ComparisonForm {
  learnerVideoId: number;
  referenceVideoId: number;
}
```

## スタイリング

### Tailwind CSS設定
```javascript
// tailwind.config.js
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          900: '#1e3a8a',
        },
        success: {
          500: '#10b981',
        },
        warning: {
          500: '#f59e0b',
        },
        danger: {
          500: '#ef4444',
        },
      },
      animation: {
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-in',
      },
    },
  },
  plugins: [],
};
```

### コンポーネントスタイリング
```typescript
// Utility-First with組み合わせ
const Button = ({ variant = 'primary', size = 'md', children }) => {
  const baseClasses = 'rounded-md font-medium transition-colors focus:outline-none focus:ring-2';

  const variantClasses = {
    primary: 'bg-primary-500 text-white hover:bg-primary-600',
    secondary: 'bg-gray-200 text-gray-700 hover:bg-gray-300',
    danger: 'bg-danger-500 text-white hover:bg-danger-600',
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]}`}
    >
      {children}
    </button>
  );
};
```

## パフォーマンス最適化

### Code Splitting
```typescript
// 動的インポート
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <Skeleton />,
  ssr: false,
});
```

### 画像最適化
```typescript
import Image from 'next/image';

<Image
  src="/video-thumbnail.jpg"
  alt="Video thumbnail"
  width={320}
  height={180}
  loading="lazy"
  placeholder="blur"
/>
```

### メモ化
```typescript
// React.memo
const ExpensiveComponent = React.memo(({ data }) => {
  // レンダリングコストが高いコンポーネント
}, (prevProps, nextProps) => {
  return prevProps.data.id === nextProps.data.id;
});

// useMemo
const expensiveCalculation = useMemo(() => {
  return calculateMetrics(analysisData);
}, [analysisData]);

// useCallback
const handleSubmit = useCallback((data) => {
  submitForm(data);
}, []);
```

### WebSocket最適化
```typescript
// hooks/useWebSocket.ts
export const useWebSocket = (url: string) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<any>(null);

  useEffect(() => {
    const ws = new WebSocket(url);

    ws.onmessage = (event) => {
      setLastMessage(JSON.parse(event.data));
    };

    setSocket(ws);

    return () => {
      ws.close();
    };
  }, [url]);

  const sendMessage = useCallback((message: any) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }, [socket]);

  return { lastMessage, sendMessage };
};
```

## テスト戦略

### E2Eテスト（Playwright）
```typescript
// tests/upload.spec.ts
test('動画アップロードフロー', async ({ page }) => {
  await page.goto('/');

  // ファイル選択
  await page.setInputFiles('input[type="file"]', 'test-video.mp4');

  // アップロードボタンクリック
  await page.click('button:has-text("アップロード")');

  // 成功メッセージ確認
  await expect(page.locator('text=アップロードが完了しました')).toBeVisible();
});
```

## アクセシビリティ

### WCAG 2.1準拠
```typescript
// ✅ Good: アクセシブルなボタン
<button
  aria-label="動画をアップロード"
  aria-busy={isUploading}
  disabled={isUploading}
>
  {isUploading ? 'アップロード中...' : 'アップロード'}
</button>

// ✅ Good: フォーカス管理
<input
  ref={inputRef}
  aria-invalid={!!error}
  aria-describedby={error ? 'error-message' : undefined}
/>
{error && <span id="error-message" role="alert">{error}</span>}
```

---
*最終更新: 2024年9月27日*
*このドキュメントはClaude Codeとの協働開発を前提に作成されています*