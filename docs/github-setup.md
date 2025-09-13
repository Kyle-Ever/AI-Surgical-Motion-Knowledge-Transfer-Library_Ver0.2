# GitHub連携セットアップガイド

## 1. 前提条件
- Git がインストール済み
- GitHub CLI (gh) がインストール済み
- GitHubアカウントを持っている

## 2. GitHub CLI認証設定

### 2.1 認証開始
```bash
gh auth login
```

### 2.2 認証手順
1. **GitHub.com** を選択
2. **HTTPS** を選択（推奨）
3. **Y** でGit認証情報の使用を許可
4. 認証方法を選択:
   - **Login with a web browser** (推奨): ブラウザで認証
   - **Paste an authentication token**: Personal Access Token使用

### 2.3 ブラウザ認証の場合
1. 表示される8文字のコードをメモ
2. Enterキーを押してブラウザを開く
3. GitHubにログインしてコードを入力
4. 権限を承認

### 2.4 認証確認
```bash
gh auth status
```
正常な場合:
```
✓ Logged in to github.com as [username]
```

## 3. リモートリポジトリ設定

### 3.1 新規リポジトリ作成（GitHub上に存在しない場合）
```bash
# プライベートリポジトリ作成
gh repo create ai-surgical-motion-library --private

# パブリックリポジトリ作成
gh repo create ai-surgical-motion-library --public
```

### 3.2 既存リポジトリに接続
```bash
# リモート追加（URLを実際のものに置き換え）
git remote add origin https://github.com/[username]/ai-surgical-motion-library.git

# 確認
git remote -v
```

### 3.3 初回プッシュ
```bash
# メインブランチの設定
git branch -M main

# 初回プッシュ（上流ブランチ設定）
git push -u origin main
```

## 4. バッチファイルの使い方

### 4.1 `git-push.bat` - 簡易プッシュ
```bash
# 実行
git-push.bat

# 手順:
1. 現在の状態が表示される
2. コミットメッセージを入力
3. 自動でadd→commit→push実行
```

### 4.2 `git-push-safe.bat` - 安全プッシュ
```bash
# 実行
git-push-safe.bat

# 手順:
1. GitHub認証チェック
2. 変更内容の確認
3. Y/Nで続行確認
4. コミットメッセージ入力
5. プッシュ実行
```

## 5. トラブルシューティング

### 問題: 認証エラー
```
error: failed to authenticate
```
**解決法:**
```bash
gh auth logout
gh auth login
```

### 問題: リモートが見つからない
```
fatal: 'origin' does not appear to be a git repository
```
**解決法:**
```bash
git remote add origin https://github.com/[username]/[repo].git
```

### 問題: プッシュ権限エラー
```
remote: Permission to [repo] denied
```
**解決法:**
1. リポジトリの権限確認
2. Personal Access Tokenの権限確認:
   ```bash
   gh auth refresh -s write:packages,repo
   ```

### 問題: ブランチ不一致
```
error: failed to push some refs
```
**解決法:**
```bash
# リモートの変更を取得
git pull origin main --rebase

# 再度プッシュ
git push origin main
```

## 6. 推奨ワークフロー

1. **作業開始前**: 最新を取得
   ```bash
   git pull origin main
   ```

2. **作業完了後**: バッチファイルでプッシュ
   ```bash
   git-push-safe.bat
   ```

3. **定期的な同期**: 他の開発者の変更を取り込む
   ```bash
   git fetch origin
   git merge origin/main
   ```

## 7. セキュリティ注意事項

- Personal Access Tokenは安全に保管
- 認証情報をコミットしない
- `.env`ファイルは`.gitignore`に含める
- 定期的にトークンを更新

## 8. 便利なGitHub CLIコマンド

```bash
# PRの作成
gh pr create --title "タイトル" --body "説明"

# イシューの確認
gh issue list

# リポジトリ情報
gh repo view

# ワークフローの確認
gh workflow list
```