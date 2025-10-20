# 🐛 バグ修正: start_both_experimental.bat

## 問題

`start_both_experimental.bat`を実行してもフロントエンドが起動しない。

## 原因

42行目で削除済みの`start_frontend.bat`を呼び出していた：

```batch
start "Frontend Server (Experimental Mode)" cmd /k "%SCRIPT_DIR%start_frontend.bat"
```

バッチファイル整理時に`start_frontend.bat`を削除したが、`start_both_experimental.bat`内の参照を更新し忘れていた。

## 修正内容

直接`npm run dev`を実行するように変更：

**Before（修正前）:**
```batch
start "Frontend Server (Experimental Mode)" cmd /k "%SCRIPT_DIR%start_frontend.bat"
```

**After（修正後）:**
```batch
start "Frontend Server (Experimental Mode)" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"
```

## 動作確認

```bash
# 1. バッチファイルを実行
start_both_experimental.bat

# 2. 2つのウィンドウが開くことを確認
#    - Experimental Backend Server (Port 8001)
#    - Frontend Server (Experimental Mode)

# 3. フロントエンドの起動を確認
#    "ready - started server on 0.0.0.0:3000" が表示されることを確認

# 4. ブラウザでアクセス
#    http://localhost:3000
```

## 影響範囲

- ✅ `start_both_experimental.bat` - 修正済み
- ✅ `start_backend_experimental.bat` - 影響なし（バックエンドのみ起動）
- ✅ `kill_all_servers.bat` - 影響なし（停止のみ）

## 検証済み

- [x] バッチファイルの構文チェック
- [x] 参照先ファイルの確認（存在しないファイルへの参照がないか）
- [x] ドキュメントの整合性確認

## 再発防止策

今後のバッチファイル整理時は：
1. 削除対象ファイルの依存関係を確認
2. `grep -r "削除ファイル名" *.bat` で参照箇所を検索
3. 参照箇所を修正してから削除

---

**修正日時**: 2025-10-18 01:05
**修正者**: Claude Code
