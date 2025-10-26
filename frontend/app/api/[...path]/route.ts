import { NextRequest, NextResponse } from 'next/server'

/**
 * Next.js API Route Proxy
 *
 * すべての /api/* リクエストをバックエンド（localhost:8001）にプロキシする
 * これにより、ngrok経由でもバックエンドAPIにアクセス可能になる
 *
 * 例:
 * - ブラウザ: https://your-domain.ngrok.io/api/v1/videos
 * - Next.js: http://localhost:8001/api/v1/videos にプロキシ
 * - バックエンド: レスポンスを返す
 * - ブラウザ: Next.js経由でレスポンスを受け取る
 */

// Next.js 15のRoute Segment Config
// リクエストボディサイズ制限を1GBに設定（動画アップロード対応）
export const maxDuration = 300 // 5分タイムアウト
export const dynamic = 'force-dynamic' // 常に動的レンダリング
export const runtime = 'nodejs' // Node.jsランタイム使用

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001'

export async function GET(request: NextRequest) {
  return proxyRequest(request, 'GET')
}

export async function POST(request: NextRequest) {
  return proxyRequest(request, 'POST')
}

export async function PUT(request: NextRequest) {
  return proxyRequest(request, 'PUT')
}

export async function DELETE(request: NextRequest) {
  return proxyRequest(request, 'DELETE')
}

export async function PATCH(request: NextRequest) {
  return proxyRequest(request, 'PATCH')
}

async function proxyRequest(request: NextRequest, method: string) {
  try {
    // URLパスを取得（/api/v1/videos など）
    const url = new URL(request.url)
    const path = url.pathname
    const search = url.search

    // バックエンドURLを構築
    const backendUrl = `${BACKEND_URL}${path}${search}`

    console.log(`[Proxy] ${method} ${path}${search} -> ${backendUrl}`)

    // リクエストヘッダーをコピー（必要なもののみ）
    const headers: Record<string, string> = {}
    request.headers.forEach((value, key) => {
      // Host, Connection などは除外
      if (!['host', 'connection', 'origin', 'referer'].includes(key.toLowerCase())) {
        headers[key] = value
      }
    })

    // リクエストボディを取得（POST/PUT/PATCH用）
    let body: BodyInit | undefined = undefined
    if (method !== 'GET' && method !== 'DELETE') {
      try {
        // multipart/form-data（ファイルアップロード）の場合は、
        // そのままストリームとして転送
        const contentType = request.headers.get('content-type') || ''
        if (contentType.includes('multipart/form-data')) {
          // FormDataをそのまま使用（Blobとして転送）
          body = await request.blob()
        } else {
          // JSON等のテキストデータ
          body = await request.text()
        }
      } catch (e) {
        console.error('[Proxy] Failed to read request body:', e)
        // ボディがない場合は無視
      }
    }

    // バックエンドにリクエストを転送（タイムアウトなし）
    const backendResponse = await fetch(backendUrl, {
      method,
      headers,
      body,
    })

    // レスポンスヘッダーをコピー
    const responseHeaders = new Headers()
    backendResponse.headers.forEach((value, key) => {
      responseHeaders.set(key, value)
    })

    // バックエンドのレスポンスをそのまま返す
    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    })
  } catch (error) {
    console.error('[Proxy Error]', error)
    return NextResponse.json(
      {
        detail: 'Backend proxy error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 502 }
    )
  }
}
