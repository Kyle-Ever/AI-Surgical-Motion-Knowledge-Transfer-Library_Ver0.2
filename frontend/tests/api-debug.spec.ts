import { test, expect } from '@playwright/test';

test.describe('API Debug Tests', () => {
  test('should list all available endpoints', async ({ page }) => {
    // Get OpenAPI spec
    const response = await page.request.get('http://localhost:8000/openapi.json');

    if (response.ok()) {
      const openapi = await response.json();
      const paths = Object.keys(openapi.paths || {});

      console.log('Available API endpoints:');
      paths.forEach(path => {
        const methods = Object.keys(openapi.paths[path]);
        methods.forEach(method => {
          console.log(`  ${method.toUpperCase()} ${path}`);
        });
      });

      // Check if /api/v1/analysis/completed exists
      const completedPath = '/api/v1/analysis/completed';
      if (paths.includes(completedPath)) {
        console.log(`✓ ${completedPath} endpoint is registered`);
      } else {
        console.log(`✗ ${completedPath} endpoint is NOT registered`);
        console.log('Analysis endpoints:', paths.filter(p => p.includes('/analysis')));
      }
    }
  });

  test('should test completed endpoint directly', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/api/v1/analysis/completed');

    console.log('Status:', response.status());
    console.log('Headers:', response.headers());

    const body = await response.text();
    console.log('Response body:', body);

    if (response.status() === 404) {
      // Try to understand why it's 404
      console.log('\n404 Error - Debugging:');

      // Test a known endpoint to verify API is working
      const healthResponse = await page.request.get('http://localhost:8000/api/v1/health');
      console.log('Health check status:', healthResponse.status());

      // Try to get one specific analysis
      const specificResponse = await page.request.get('http://localhost:8000/api/v1/analysis/dd82b7bb-770f-4fd2-9344-dea0240ea049');
      console.log('Specific analysis status:', specificResponse.status());

      if (specificResponse.ok()) {
        const data = await specificResponse.json();
        console.log('Specific analysis found:', data.id, data.status);
      }
    } else if (response.ok()) {
      const data = await response.json();
      console.log('Success! Found', data.length, 'completed analyses');
    }
  });

  test('should test export endpoint', async ({ page }) => {
    // First get a completed analysis ID
    const dbCheckResponse = await page.request.get('http://localhost:8000/api/v1/analysis/dd82b7bb-770f-4fd2-9344-dea0240ea049');

    if (dbCheckResponse.ok()) {
      const analysis = await dbCheckResponse.json();
      console.log('Testing export for analysis:', analysis.id);

      const exportResponse = await page.request.get(
        `http://localhost:8000/api/v1/analysis/${analysis.id}/export`
      );

      console.log('Export status:', exportResponse.status());
      console.log('Export content-type:', exportResponse.headers()['content-type']);

      if (exportResponse.ok()) {
        const content = await exportResponse.text();
        console.log('Export content (first 500 chars):', content.substring(0, 500));
      } else {
        console.log('Export error:', await exportResponse.text());
      }
    }
  });
});