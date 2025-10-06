import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('器具先端検出機能', () => {
  test('先端点が検出され、フレームごとに移動すること', async ({ page }) => {
    // テスト用動画のパス
    const videoPath = path.join(process.cwd(), '..', 'backend', 'data', 'uploads', 'test_video.mp4');

    // 1. アップロードページに移動
    await page.goto('http://localhost:3000/upload');
    await page.waitForLoadState('networkidle');

    // 2. 動画をアップロード
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(videoPath);

    // アップロード完了を待つ
    await page.waitForSelector('text=アップロード完了', { timeout: 30000 });

    // 3. 解析設定ページに移動
    await page.click('text=解析を開始');
    await page.waitForLoadState('networkidle');

    // 4. 解析タイプを選択（external_with_instruments または internal）
    await page.selectOption('select[name="videoType"]', 'external_with_instruments');

    // 5. 器具を選択（最初の器具にマスクを設定）
    await page.click('text=器具を選択');

    // マスク選択モード（簡略化のため、ポイント選択を使用）
    await page.click('button:has-text("ポイント選択")');

    // 動画プレイヤー上でクリック（器具の位置）
    const videoPlayer = page.locator('video');
    const box = await videoPlayer.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    }

    await page.click('text=選択完了');

    // 6. 解析を開始
    await page.click('button:has-text("解析開始")');

    // 解析完了を待つ（最大5分）
    await page.waitForSelector('text=解析完了', { timeout: 300000 });

    // 7. ダッシュボードに移動
    const dashboardUrl = page.url().replace('/analysis/', '/dashboard/');
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');

    // 8. APIレスポンスから先端点データを確認
    const response = await page.evaluate(async () => {
      const analysisId = window.location.pathname.split('/').pop();
      const res = await fetch(`http://localhost:8000/api/v1/analysis/${analysisId}`);
      return await res.json();
    });

    // 9. 先端点が存在することを確認
    expect(response.instrument_data).toBeDefined();
    expect(response.instrument_data.length).toBeGreaterThan(0);

    const firstFrame = response.instrument_data[0];
    expect(firstFrame.detections).toBeDefined();
    expect(firstFrame.detections.length).toBeGreaterThan(0);

    const firstDetection = firstFrame.detections[0];

    // 先端点フィールドが存在すること
    expect(firstDetection.tip_point).toBeDefined();
    expect(firstDetection.tip_point).not.toBeNull();
    expect(firstDetection.tip_confidence).toBeDefined();
    expect(firstDetection.tip_confidence).toBeGreaterThan(0);

    // 先端点が配列形式 [x, y] であること
    expect(Array.isArray(firstDetection.tip_point)).toBe(true);
    expect(firstDetection.tip_point.length).toBe(2);
    expect(typeof firstDetection.tip_point[0]).toBe('number');
    expect(typeof firstDetection.tip_point[1]).toBe('number');

    // 10. 先端点が各フレームで移動していることを確認
    if (response.instrument_data.length >= 10) {
      const tip_points = response.instrument_data
        .slice(0, 10)
        .map(frame => frame.detections[0]?.tip_point)
        .filter(tip => tip !== null && tip !== undefined);

      expect(tip_points.length).toBeGreaterThan(5);

      // 先端点が全て同じ座標ではないことを確認（固定バグの回帰テスト）
      const uniqueTips = new Set(tip_points.map(tip => `${tip[0]},${tip[1]}`));
      expect(uniqueTips.size).toBeGreaterThan(1);

      console.log('先端点のサンプル:', tip_points.slice(0, 5));
    }

    // 11. BBoxも各フレームで変化していることを確認
    const bboxes = response.instrument_data
      .slice(0, 10)
      .map(frame => frame.detections[0]?.bbox)
      .filter(bbox => bbox !== null && bbox !== undefined);

    const uniqueBboxes = new Set(bboxes.map(bbox => bbox.join(',')));
    expect(uniqueBboxes.size).toBeGreaterThan(1);

    console.log('テスト成功: 先端点が正しく検出され、各フレームで移動しています');
  });

  test('先端点がBBox内に存在すること', async ({ page }) => {
    // 既存の解析結果を使用
    const analysisId = '0531fd59-0b53-4602-bac5-6a7c97fe376b'; // 既知の解析ID

    // APIから結果を取得
    const response = await page.evaluate(async (id) => {
      const res = await fetch(`http://localhost:8000/api/v1/analysis/${id}`);
      return await res.json();
    }, analysisId);

    // 各フレームで先端点がBBox内にあることを確認
    for (const frame of response.instrument_data.slice(0, 20)) {
      for (const detection of frame.detections) {
        if (detection.tip_point && detection.bbox) {
          const [tip_x, tip_y] = detection.tip_point;
          const [x1, y1, x2, y2] = detection.bbox;

          // 先端点がBBox内にあるか確認
          expect(tip_x).toBeGreaterThanOrEqual(x1);
          expect(tip_x).toBeLessThanOrEqual(x2);
          expect(tip_y).toBeGreaterThanOrEqual(y1);
          expect(tip_y).toBeLessThanOrEqual(y2);
        }
      }
    }

    console.log('テスト成功: すべての先端点がBBox内に存在します');
  });
});
