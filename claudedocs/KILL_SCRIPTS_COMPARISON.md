# プロセス終了スクリプト比較

## 2つのスクリプトの違い

### 1️⃣ `kill_all_servers.bat` - **通常使用（推奨）**

**用途:** 開発サーバーの通常終了

**動作:**
- Port 3000, 8000, 8001を使用しているプロセスのみ終了
- 全てのNode.jsプロセスを終了
- 全てのPythonプロセスを終了
- バックエンドロックファイル削除

**特徴:**
- ✅ 確認なしで即座に実行
- ✅ 素早い終了
- ✅ 通常のトラブル対応に最適

**使用タイミング:**
- サーバーが応答しなくなった
- ポート使用中エラーが出た
- 通常の再起動前

---

### 2️⃣ `kill_all_processes.bat` - **完全終了（慎重に使用）**

**用途:** 全てのPython/Node.jsプロセスを確実に終了

**動作:**
- **実行前に確認プロンプト表示**
- Port 3000, 8000, 8001のプロセス終了
- **全てのNode.jsプロセスを強制終了**
- **全てのPythonプロセスを強制終了**
- バックエンドロックファイル削除
- **終了後の状態確認と結果表示**

**特徴:**
- ⚠️ 実行前に確認を要求
- ⚠️ 他のPython/Node.jsアプリにも影響
- ✅ 詳細な進捗表示
- ✅ 終了後の状態確認
- ✅ 問題が残っている場合は警告

**使用タイミング:**
- `kill_all_servers.bat`で解決しない場合
- プロセスが完全にハングした
- 確実にクリーンな状態にしたい
- 他のPython/Node.jsアプリが実行中でないことを確認済み

---

## 📊 機能比較表

| 機能 | kill_all_servers.bat | kill_all_processes.bat |
|------|---------------------|----------------------|
| 実行前確認 | なし（即実行） | あり（Y/N確認） |
| ポート別終了 | ✅ Port 3000, 8000, 8001 | ✅ Port 3000, 8000, 8001 |
| Node.js全終了 | ✅ | ✅ |
| Python全終了 | ✅ | ✅ |
| ロックファイル削除 | ✅ | ✅ |
| 詳細進捗表示 | ❌ | ✅ 6段階表示 |
| 終了後確認 | ❌ | ✅ 最終状態チェック |
| エラー時の対処提示 | ❌ | ✅ 対処方法表示 |
| 他アプリへの影響警告 | ❌ | ✅ 事前警告 |

---

## 🎯 使用フローチャート

```
サーバーを止めたい
    ↓
┌───────────────────────┐
│ 通常の再起動？        │
└───────────────────────┘
    ↓ YES              ↓ NO
kill_all_servers.bat   問題がある？
    ↓                     ↓ YES
再起動                  kill_all_servers.bat
    ↓                     ↓
  完了                  解決した？
                          ↓ NO
                    kill_all_processes.bat
                          ↓
                      最終手段
```

---

## 📝 使用例

### ケース1: 通常の再起動
```bash
# 素早くサーバーを止めて再起動
kill_all_servers.bat
start_both_experimental.bat
```

### ケース2: ポートエラーが出た
```bash
# まずは通常の方法で
kill_all_servers.bat

# まだポートエラーが出る場合
kill_all_processes.bat
# → Y で確認
# → 完全終了を待つ
# → 再起動
start_both_experimental.bat
```

### ケース3: プロセスがハング
```bash
# 通常終了を試す
kill_all_servers.bat

# 効果なし？
kill_all_processes.bat
# → Y で確認
# → 完全終了を待つ

# それでもダメなら管理者権限で実行
# 右クリック → 管理者として実行
kill_all_processes.bat
```

---

## ⚠️ 注意事項

### `kill_all_servers.bat`
- ✅ 日常的に使用可能
- ✅ 副作用なし（プロジェクト内のみ影響）
- ✅ 確認不要で素早い

### `kill_all_processes.bat`
- ⚠️ 他のPython/Node.jsアプリも終了
- ⚠️ 保存していないデータが失われる可能性
- ⚠️ 実行前に他のアプリを確認
- ✅ 確実に全て終了
- ✅ 詳細なフィードバック

---

## 🔧 トラブルシューティング

### 「プロセスが見つかりません」エラー
→ 既に終了しています。再起動可能です。

### 「アクセスが拒否されました」エラー
→ 管理者権限で実行してください：
1. バッチファイルを右クリック
2. 「管理者として実行」を選択

### 終了後もポートが使用中
```bash
# 2-3秒待ってから確認
timeout /t 3 /nobreak
netstat -ano | findstr :3000
netstat -ano | findstr :8001

# まだ使用中なら、表示されたPIDを手動で終了
taskkill /F /PID <PID番号>
```

---

## 📂 ファイル配置

```
プロジェクトルート/
├── kill_all_servers.bat      # 通常使用
├── kill_all_processes.bat    # 完全終了
├── start_both_experimental.bat
└── start_backend_experimental.bat
```

---

## 🎯 推奨使用パターン

**日常開発:**
```bash
# 開始
start_both_experimental.bat

# 作業...

# 終了
kill_all_servers.bat
```

**トラブル時:**
```bash
# まず通常終了
kill_all_servers.bat

# 効果なし？完全終了
kill_all_processes.bat

# 再起動
start_both_experimental.bat
```

**完全リセット:**
```bash
# 確実にクリーンな状態に
kill_all_processes.bat
# → Y で確認
# → 完了を待つ

# 2秒待機
timeout /t 2 /nobreak

# 再起動
start_both_experimental.bat
```

---

**まとめ:**
- 🟢 **通常**: `kill_all_servers.bat` を使用
- 🔴 **トラブル時**: `kill_all_processes.bat` を使用
- 🎯 **迷ったら**: まず `kill_all_servers.bat` を試す
