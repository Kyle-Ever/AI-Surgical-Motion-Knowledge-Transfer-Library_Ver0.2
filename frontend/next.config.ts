import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  eslint: {
    // Warning: This allows production builds to successfully complete even if
    // your project has ESLint errors.
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    ignoreBuildErrors: true,
  },
  // API Routes設定: 動画アップロード対応（1GB制限）
  experimental: {
    serverActions: {
      bodySizeLimit: '1gb', // Server Actionsのボディサイズ制限
    },
  },
  // APIルートのボディサイズ制限を設定
  // Note: Next.js 15では、APIルートのボディサイズはデフォルト1MBに制限されている
  // 動画アップロードを許可するため、制限を1GBに拡張
  serverRuntimeConfig: {
    maxBodySize: '1gb',
  },
};

export default nextConfig;
