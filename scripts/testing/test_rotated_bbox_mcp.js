// Playwright MCP テスト: 回転BBox検証
// Phase 2.5の実装が正しく動作しているかを確認

import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('🔍 Phase 2.5: 回転BBox実装テスト開始\n');

  try {
    // Step 1: 動画リストからINTERNAL動画を取得
    console.log('📹 Step 1: INTERNAL動画を検索中...');
    const videosResponse = await page.request.get('http://localhost:8000/api/v1/videos/');
    const videos = await videosResponse.json();

    const internalVideos = videos.filter(v => v.video_type === 'internal' || v.video_type === 'INTERNAL');

    if (internalVideos.length === 0) {
      console.log('❌ INTERNAL動画が見つかりません');
      await browser.close();
      return;
    }

    const targetVideo = internalVideos[0];
    console.log(`✅ INTERNAL動画発見: ${targetVideo.id}`);
    console.log(`   ファイル: ${targetVideo.file_path}`);

    // Step 2: 新規解析を開始
    console.log('\n🔄 Step 2: 新規解析を開始...');
    const analysisResponse = await page.request.post(
      `http://localhost:8000/api/v1/analysis/${targetVideo.id}/analyze`,
      {
        data: {
          video_id: targetVideo.id,
          instruments: [],
          sampling_rate: 1
        }
      }
    );

    if (!analysisResponse.ok()) {
      const errorText = await analysisResponse.text();
      console.log(`❌ 解析開始失敗: ${analysisResponse.status()}`);
      console.log(`   エラー: ${errorText}`);
      await browser.close();
      return;
    }

    const analysisData = await analysisResponse.json();
    const analysisId = analysisData.id;
    console.log(`✅ 解析開始成功: ${analysisId}`);

    // Step 3: 解析完了を待機（最大3分）
    console.log('\n⏳ Step 3: 解析完了を待機中...');
    let completed = false;
    let attempts = 0;
    const maxAttempts = 36; // 3分 (36 * 5秒)

    while (attempts < maxAttempts) {
      await page.waitForTimeout(5000); // 5秒待機
      attempts++;

      const statusResponse = await page.request.get(
        `http://localhost:8000/api/v1/analysis/${analysisId}/status`
      );
      const status = await statusResponse.json();

      process.stdout.write(`\r   進捗: ${status.progress || 0}% - ${status.current_step || 'processing'} (${attempts}/${maxAttempts})`);

      if (status.status === 'completed' || status.status === 'COMPLETED') {
        console.log('\n✅ 解析完了！');
        completed = true;
        break;
      }

      if (status.status === 'failed' || status.status === 'FAILED') {
        console.log(`\n❌ 解析失敗: ${status.error_message || 'Unknown error'}`);
        await browser.close();
        return;
      }
    }

    if (!completed) {
      console.log('\n⏭️  解析タイムアウト（3分経過）');
      await browser.close();
      return;
    }

    // Step 4: 解析結果を取得し、回転BBoxを検証
    console.log('\n🔍 Step 4: 回転BBoxデータを検証中...');
    const detailResponse = await page.request.get(
      `http://localhost:8000/api/v1/analysis/${analysisId}`
    );
    const data = await detailResponse.json();

    if (!data.instrument_data || data.instrument_data.length === 0) {
      console.log('❌ 器具データが見つかりません');
      await browser.close();
      return;
    }

    console.log(`✅ 器具データ取得: ${data.instrument_data.length} フレーム`);

    // 回転BBoxの検証
    let rotatedBboxCount = 0;
    let totalAreaReduction = 0;
    let areaReductionCount = 0;
    const samples = [];

    for (const frame of data.instrument_data) {
      if (!frame.instruments || frame.instruments.length === 0) continue;

      for (const instrument of frame.instruments) {
        if (instrument.rotated_bbox) {
          rotatedBboxCount++;

          // サンプルを最初の3件収集
          if (samples.length < 3) {
            samples.push({
              frame: frame.frame_number,
              rotated_bbox: instrument.rotated_bbox,
              rotation_angle: instrument.rotation_angle,
              area_reduction: instrument.area_reduction,
              bbox: instrument.bbox
            });
          }

          // 面積削減率の集計
          if (instrument.area_reduction !== undefined && instrument.area_reduction > 0) {
            totalAreaReduction += instrument.area_reduction;
            areaReductionCount++;
          }
        }
      }
    }

    // 検証結果の表示
    console.log('\n📊 検証結果:');
    console.log(`   回転BBox検出数: ${rotatedBboxCount} 個`);

    if (areaReductionCount > 0) {
      const avgReduction = totalAreaReduction / areaReductionCount;
      console.log(`   平均面積削減率: ${avgReduction.toFixed(1)}%`);
      console.log(`   (期待値: 30-50% for 斜め器具)`);
    }

    if (samples.length > 0) {
      console.log('\n🔬 サンプルデータ（最初の3件）:');
      samples.forEach((sample, idx) => {
        console.log(`   [${idx + 1}] Frame ${sample.frame}:`);
        console.log(`       回転角度: ${sample.rotation_angle?.toFixed(1)}°`);
        console.log(`       面積削減: ${sample.area_reduction?.toFixed(1)}%`);
        console.log(`       rect bbox: [${sample.bbox.join(', ')}]`);
        console.log(`       rotated bbox: ${JSON.stringify(sample.rotated_bbox)}`);
      });
    }

    if (rotatedBboxCount === 0) {
      console.log('\n❌ 回転BBoxが検出されませんでした');
      console.log('   実装に問題がある可能性があります');
    } else {
      console.log('\n✅ 回転BBox実装の検証成功！');
    }

    // Step 5: ダッシュボードで視覚的に確認
    console.log('\n🎨 Step 5: ダッシュボードで視覚的確認...');
    await page.goto(`http://localhost:3000/dashboard/${analysisId}`);
    await page.waitForLoadState('networkidle');

    // ビデオプレイヤーの表示を待機
    const videoPlayer = page.locator('video, canvas').first();
    await videoPlayer.waitFor({ state: 'visible', timeout: 10000 });
    console.log('✅ ダッシュボード読み込み完了');

    // フレーム描画を待機
    await page.waitForTimeout(3000);

    // スクリーンショット保存
    await page.screenshot({
      path: 'test-results/phase2.5-rotated-bbox-verification.png',
      fullPage: true
    });
    console.log('✅ スクリーンショット保存: test-results/phase2.5-rotated-bbox-verification.png');

    // キャンバス要素の確認
    const canvas = page.locator('canvas');
    const canvasCount = await canvas.count();

    if (canvasCount > 0) {
      console.log(`✅ キャンバス要素検出: ${canvasCount} 個`);
      const boundingBox = await canvas.first().boundingBox();
      if (boundingBox) {
        console.log(`   キャンバスサイズ: ${boundingBox.width}x${boundingBox.height}`);
      }
    }

    console.log('\n🎉 Phase 2.5: 回転BBox実装テスト完了！');
    console.log(`\n📋 解析ID: ${analysisId}`);
    console.log(`📊 ダッシュボードURL: http://localhost:3000/dashboard/${analysisId}`);

    // 30秒間ダッシュボードを表示して手動確認
    console.log('\n⏳ 30秒間ダッシュボードを表示します（手動確認用）...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('\n❌ エラー発生:', error.message);
    console.error(error.stack);
  } finally {
    await browser.close();
    console.log('\n✅ ブラウザを閉じました');
  }
})();
