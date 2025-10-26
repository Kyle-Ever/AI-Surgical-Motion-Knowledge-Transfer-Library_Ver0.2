import { test, expect } from '@playwright/test';

/**
 * E2Eテスト: 自動器具検出機能
 *
 * テストシナリオ:
 * 1. 動画をアップロード
 * 2. 器具選択画面で自動検出が実行される
 * 3. 検出された器具がハイライト表示される
 * 4. 器具をクリックしてマスク生成
 * 5. 器具名が自動設定され、追加できる
 */

test.describe('自動器具検出機能', () => {
  const API_URL = 'http://localhost:8000/api/v1';
  let uploadedVideoId: string;

  test.beforeAll(async () => {
    // テスト用の動画をアップロード
    const fs = require('fs');
    const path = require('path');

    // テスト用動画のパスを確認
    const testVideoPath = path.join(__dirname, '../../backend_experimental/data/uploads');
    console.log('Test video directory:', testVideoPath);
  });

  test('動画アップロードから自動検出まで', async ({ page }) => {
    // 1. アップロードページに移動
    await page.goto('http://localhost:3000/upload');
    await expect(page.locator('h1')).toContainText('動画をアップロード');

    // 2. ファイル選択
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    // テスト用動画をアップロード (既存の動画を使用)
    const testVideoPath = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\data\\uploads\\7a0faaa0-6085-400f-ad0f-8e292cfb53eb.mp4';

    await fileInput.setInputFiles(testVideoPath);

    // 3. アップロードボタンをクリック
    const uploadButton = page.locator('button:has-text("アップロード")');
    await uploadButton.click();

    // 4. アップロード成功を待つ
    await expect(page.locator('text=アップロード完了')).toBeVisible({ timeout: 30000 });

    // 5. 解析タイプ選択画面に遷移
    await expect(page.locator('h1')).toContainText('解析タイプを選択', { timeout: 5000 });

    // 6. "外景 + 器具トラッキング" を選択
    const externalWithInstrumentsButton = page.locator('button:has-text("外景 + 器具トラッキング")');
    await externalWithInstrumentsButton.click();

    // 7. 器具選択画面に遷移
    await expect(page.locator('h2')).toContainText('器具をクリックまたはボックスで選択', { timeout: 10000 });

    // 8. 自動検出モードがデフォルトでアクティブ
    const autoDetectButton = page.locator('button:has-text("自動検出")');
    await expect(autoDetectButton).toHaveClass(/bg-green-600/);

    // 9. 検出中メッセージが表示される
    await expect(page.locator('text=器具を自動検出中')).toBeVisible({ timeout: 5000 });

    // 10. 検出完了を待つ
    await expect(page.locator('text=個の器具が検出されました')).toBeVisible({ timeout: 30000 });

    // 11. キャンバスが表示される
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();

    console.log('✅ 自動検出が完了しました');
  });

  test('検出された器具をクリックしてマスク生成', async ({ page }) => {
    // 前のテストで器具選択画面まで進んでいると仮定
    await page.goto('http://localhost:3000/upload');

    // アップロードプロセスを実行
    const fileInput = page.locator('input[type="file"]');
    const testVideoPath = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\data\\uploads\\7a0faaa0-6085-400f-ad0f-8e292cfb53eb.mp4';
    await fileInput.setInputFiles(testVideoPath);

    const uploadButton = page.locator('button:has-text("アップロード")');
    await uploadButton.click();

    await expect(page.locator('text=アップロード完了')).toBeVisible({ timeout: 30000 });

    const externalWithInstrumentsButton = page.locator('button:has-text("外景 + 器具トラッキング")');
    await externalWithInstrumentsButton.click();

    await expect(page.locator('h2')).toContainText('器具をクリックまたはボックスで選択', { timeout: 10000 });

    // 自動検出完了を待つ
    await expect(page.locator('text=個の器具が検出されました')).toBeVisible({ timeout: 30000 });

    // キャンバス内の中央をクリック (検出された器具があると仮定)
    const canvas = page.locator('canvas');
    const box = await canvas.boundingBox();

    if (box) {
      // キャンバスの中央をクリック
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);

      // セグメント処理を待つ
      await page.waitForTimeout(3000);

      // 器具名入力欄が表示される
      const nameInput = page.locator('input[placeholder="器具名を入力"]');
      await expect(nameInput).toBeVisible({ timeout: 10000 });

      // 器具名が自動設定されているか確認
      const nameValue = await nameInput.inputValue();
      expect(nameValue.length).toBeGreaterThan(0);
      console.log('✅ 自動設定された器具名:', nameValue);

      // 追加ボタンをクリック
      const addButton = page.locator('button:has-text("追加")');
      await expect(addButton).toBeEnabled();
      await addButton.click();

      // 選択した器具リストに追加される
      await expect(page.locator('text=選択した器具')).toBeVisible({ timeout: 5000 });

      console.log('✅ 器具の選択とマスク生成が成功しました');
    }
  });

  test('手動モードへの切り替え', async ({ page }) => {
    await page.goto('http://localhost:3000/upload');

    // アップロードプロセス
    const fileInput = page.locator('input[type="file"]');
    const testVideoPath = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\data\\uploads\\7a0faaa0-6085-400f-ad0f-8e292cfb53eb.mp4';
    await fileInput.setInputFiles(testVideoPath);

    const uploadButton = page.locator('button:has-text("アップロード")');
    await uploadButton.click();

    await expect(page.locator('text=アップロード完了')).toBeVisible({ timeout: 30000 });

    const externalWithInstrumentsButton = page.locator('button:has-text("外景 + 器具トラッキング")');
    await externalWithInstrumentsButton.click();

    await expect(page.locator('h2')).toContainText('器具をクリックまたはボックスで選択', { timeout: 10000 });

    // 自動検出完了を待つ
    await expect(page.locator('text=個の器具が検出されました')).toBeVisible({ timeout: 30000 });

    // ポイント選択モードに切り替え
    const pointButton = page.locator('button:has-text("ポイント選択")');
    await pointButton.click();

    // ポイント選択モードがアクティブ
    await expect(pointButton).toHaveClass(/bg-blue-600/);

    // インストラクションが変わる
    await expect(page.locator('text=器具をクリックして選択')).toBeVisible();

    // ボックス選択モードに切り替え
    const boxButton = page.locator('button:has-text("ボックス選択")');
    await boxButton.click();

    // ボックス選択モードがアクティブ
    await expect(boxButton).toHaveClass(/bg-blue-600/);

    // インストラクションが変わる
    await expect(page.locator('text=ドラッグして器具を囲むボックスを描画')).toBeVisible();

    console.log('✅ 手動モードへの切り替えが正常に動作しました');
  });

  test('自動検出APIエンドポイントの直接テスト', async ({ request }) => {
    // 既存の動画IDを使用
    const videoId = '7a0faaa0-6085-400f-ad0f-8e292cfb53eb';

    // 自動検出APIを呼び出し
    const response = await request.post(`${API_URL}/videos/${videoId}/detect-instruments`, {
      data: {
        frame_number: 0
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    console.log('検出結果:', JSON.stringify(data, null, 2));

    // レスポンス構造を検証
    expect(data).toHaveProperty('video_id');
    expect(data).toHaveProperty('frame_number');
    expect(data).toHaveProperty('instruments');
    expect(data).toHaveProperty('model_info');

    // 器具が検出されているか確認
    expect(Array.isArray(data.instruments)).toBeTruthy();

    if (data.instruments.length > 0) {
      const instrument = data.instruments[0];

      // 各器具の構造を検証
      expect(instrument).toHaveProperty('id');
      expect(instrument).toHaveProperty('bbox');
      expect(instrument).toHaveProperty('confidence');
      expect(instrument).toHaveProperty('class_name');
      expect(instrument).toHaveProperty('suggested_name');
      expect(instrument).toHaveProperty('center');

      // bbox形式を検証
      expect(Array.isArray(instrument.bbox)).toBeTruthy();
      expect(instrument.bbox.length).toBe(4);

      console.log('✅ API検証成功:', {
        検出数: data.instruments.length,
        器具例: instrument.suggested_name,
        信頼度: instrument.confidence
      });
    }
  });

  test('検出からマスク生成APIの直接テスト', async ({ request }) => {
    const videoId = '7a0faaa0-6085-400f-ad0f-8e292cfb53eb';

    // 1. まず検出を実行
    const detectResponse = await request.post(`${API_URL}/videos/${videoId}/detect-instruments`, {
      data: { frame_number: 0 }
    });

    expect(detectResponse.ok()).toBeTruthy();
    const detectData = await detectResponse.json();

    if (detectData.instruments.length > 0) {
      const firstInstrument = detectData.instruments[0];

      // 2. 検出結果からマスク生成
      const segmentResponse = await request.post(`${API_URL}/videos/${videoId}/segment-from-detection`, {
        data: {
          bbox: firstInstrument.bbox,
          detection_id: firstInstrument.id,
          frame_number: 0
        }
      });

      expect(segmentResponse.ok()).toBeTruthy();
      const segmentData = await segmentResponse.json();

      // レスポンス構造を検証
      expect(segmentData).toHaveProperty('mask');
      expect(segmentData).toHaveProperty('visualization');
      expect(segmentData).toHaveProperty('bbox');
      expect(segmentData).toHaveProperty('score');
      expect(segmentData).toHaveProperty('area');
      expect(segmentData).toHaveProperty('detection_id');

      // マスクがBase64形式であることを確認
      expect(typeof segmentData.mask).toBe('string');
      expect(segmentData.mask.length).toBeGreaterThan(0);

      console.log('✅ マスク生成API検証成功:', {
        検出器具: firstInstrument.suggested_name,
        マスクサイズ: segmentData.mask.length,
        スコア: segmentData.score,
        面積: segmentData.area
      });
    }
  });
});
