# 🌐 ngrokセットアップガイド

## 📋 概要

ngrokを使用することで、ローカルで動作しているアプリケーションをインターネット経由でアクセス可能にできます。

## 🚀 初回セットアップ（5分）

### ステップ1: ngrokのダウンロード

1. https://ngrok.com/download にアクセス
2. Windowsバージョンをダウンロード
3. ZIPファイルを展開
4. `ngrok.exe` を以下のいずれかに配置:
   - プロジェクトのルートディレクトリ
   - または、PATHが通っているフォルダ（例: `C:\Windows\System32`）

### ステップ2: アカウント作成（推奨）

**無料アカウントのメリット:**
- ✅ 固定URL（毎回同じURLを使える）
- ✅ 無制限の実行時間（24時間以上OK）
- ✅ セッション管理
- ❌ カスタムドメインは有料プラン（$8/月）が必要

**アカウント作成手順:**
1. https://ngrok.com/signup にアクセス
2. 無料アカウント作成（Google/GitHubログイン可）
3. ダッシュボードから **authtoken** を取得

### ステップ3: authtokenの設定

```bash
# ターミナルで実行（初回のみ）
ngrok config add-authtoken <your-authtoken-here>
```

**例:**
```bash
ngrok config add-authtoken 2abc_def123XYZ456789abcdefghijklmnopqrstuvwxyz
```

### ステップ4: 起動テスト

```bash
# プロジェクトルートで実行
start_both_experimental_with_ngrok.bat
```

**成功すると:**
- 3つのウィンドウが開く（Backend, Frontend, ngrok）
- ngrokウィンドウに公開URLが表示される

## 📖 使用方法

### 基本的な使用

```bash
# 1. バッチファイルで起動
start_both_experimental_with_ngrok.bat

# 2. ngrokウィンドウで公開URLを確認
# 例: https://abc123.ngrok-free.app

# 3. そのURLをブラウザで開くか、他の人に共有
```

### ngrok管理画面

起動後、http://localhost:4040 にアクセスすると:
- リアルタイムリクエスト表示
- レスポンスの詳細
- リクエストの再送（リプレイ）機能

## 🎯 固定URLの使用（アカウント登録時）

### 固定ドメインの取得

1. https://dashboard.ngrok.com/cloud-edge/domains にアクセス
2. "New Domain" をクリック
3. 希望のサブドメインを入力（例: `my-surgery-demo`）
4. 無料プランでは `my-surgery-demo.ngrok-free.app` が取得可能

### バッチファイルの編集

`start_both_experimental_with_ngrok.bat` を編集:

```batch
# 変更前（ランダムURL）
start "ngrok Tunnel (Port 3000)" cmd /k "ngrok http 3000"

# 変更後（固定URL）
start "ngrok Tunnel (Port 3000)" cmd /k "ngrok http --domain=my-surgery-demo.ngrok-free.app 3000"
```

**メリット:**
- 毎回同じURLが使える
- URLをブックマーク可能
- URLを事前に共有可能

## 🔧 トラブルシューティング

### エラー: "ngrok is not recognized"

**原因:** ngrok.exeがPATHに含まれていない

**解決方法:**
1. `ngrok.exe` をプロジェクトルートに配置
2. または、環境変数PATHにngrokのフォルダを追加

### エラー: "Authentication token required"

**原因:** authtokenが設定されていない

**解決方法:**
```bash
ngrok config add-authtoken <your-token>
```

### エラー: "Tunnel session aborted"

**原因:** ネットワーク接続の問題

**解決方法:**
1. インターネット接続を確認
2. ngrokプロセスを再起動
3. `kill_all_servers.bat` → `start_both_experimental_with_ngrok.bat`

### エラー: "Port already in use"

**原因:** 別のngrokプロセスが実行中

**解決方法:**
```bash
# すべてのngrokプロセスを終了
taskkill /F /IM ngrok.exe

# 再起動
start_both_experimental_with_ngrok.bat
```

### 警告: "You are about to visit..."

**原因:** ngrokの無料プラン警告画面

**解決方法:**
- これは正常です（無料プランの仕様）
- "Visit Site" をクリックして続行
- 有料プラン（$8/月）で警告を非表示にできます

## 📊 プラン比較

| 機能 | 無料（匿名） | 無料（登録） | Personal ($8/月) |
|------|--------------|--------------|------------------|
| 実行時間 | 2時間 | **無制限** | 無制限 |
| URL | ランダム | ランダムまたは固定1個 | カスタムドメイン |
| 警告画面 | あり | あり | なし |
| 同時トンネル | 1 | 1 | 3 |

## 💡 ベストプラクティス

### デモンストレーション用

```bash
# 1. 事前に固定URLを取得
# 2. バッチファイルで固定URL設定
# 3. デモ前に起動テスト
# 4. ngrok管理画面（localhost:4040）でトラフィック監視
```

### 開発・テスト用

```bash
# 1. ランダムURLでOK（設定不要）
# 2. モバイル端末でテスト時に便利
# 3. チームメンバーとの一時的な共有
```

### セキュリティ注意事項

- ⚠️ ngrokは **パブリックURL** を作成します
- ⚠️ 機密情報を含むアプリは公開しないこと
- ⚠️ 開発/テスト環境のみで使用
- ⚠️ 本番環境では使用しない
- ✅ 使用後は必ずサーバーを停止

## 🔗 参考リンク

- [ngrok公式サイト](https://ngrok.com)
- [ngrokドキュメント](https://ngrok.com/docs)
- [ngrokダッシュボード](https://dashboard.ngrok.com)
- [ngrokプライシング](https://ngrok.com/pricing)

---

**🎯 クイックスタート: 5分で公開アクセス**

```bash
# 1. ngrokダウンロード → プロジェクトルートに配置
# 2. アカウント作成 → authtokenを設定
# 3. start_both_experimental_with_ngrok.bat を実行
# 4. ngrokウィンドウのURLを共有
```
