import { FullConfig } from '@playwright/test';
import { execSync } from 'child_process';
import { mkdirSync } from 'fs';

async function globalSetup(config: FullConfig) {
  console.log('🧪 Playwright Global Setup');
  
  // Создаем директории для результатов тестов
  const dirs = [
    './coverage/playwright',
    './coverage/playwright/screenshots',
    './coverage/playwright/videos',
    './coverage/playwright/har',
  ];
  
  dirs.forEach(dir => {
    try {
      mkdirSync(dir, { recursive: true });
    } catch (error) {
      console.warn(`Не удалось создать директорию ${dir}:`, error);
    }
  });

  // Устанавливаем браузеры Playwright если нужно
  try {
    const browserCount = execSync('npx playwright list', { encoding: 'utf-8' });
    console.log('Доступные браузеры:', browserCount);
  } catch (error) {
    console.log('Устанавливаем браузеры Playwright...');
    execSync('npx playwright install --with-deps', { stdio: 'inherit' });
  }

  // Проверяем что сервер запущен
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    await page.goto('http://localhost:4173');
    console.log('✅ Сервер разработки доступен');
  } catch (error) {
    console.warn('⚠️  Сервер разработки недоступен, будет запущен автоматически');
  } finally {
    await browser.close();
  }

  // Очищаем старые coverage данные
  try {
    execSync('rm -rf ./coverage/playwright/*', { stdio: 'ignore' });
  } catch (error) {
    console.warn('Не удалось очистить старые результаты:', error);
  }

  console.log('✅ Global Setup завершен');
}

export default globalSetup;
