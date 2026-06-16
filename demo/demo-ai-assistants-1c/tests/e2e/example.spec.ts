/**
 * E2E тесты с Playwright для проверки пользовательских сценариев
 */

import { test, expect } from '@playwright/test';

test.describe('Главная страница', () => {
  test('должна загружаться корректно', async ({ page }) => {
    await page.goto('/');
    
    // Проверяем заголовок страницы
    await expect(page).toHaveTitle(/Demo AI Assistants/);
    
    // Проверяем основные элементы интерфейса
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();
    
    // Проверяем что кнопки главного меню присутствуют
    await expect(page.locator('button:has-text("Демо")')).toBeVisible();
    await expect(page.locator('button:has-text("Живое демо")')).toBeVisible();
  });

  test('должна корректно отвечать на навигацию', async ({ page }) => {
    await page.goto('/');
    
    // Кликаем на кнопку "Демо"
    await page.click('button:has-text("Демо")');
    
    // Проверяем что URL изменился
    await expect(page).toHaveURL(/.*demo/);
    
    // Проверяем что страница демо загрузилась
    await expect(page.locator('h1')).toContainText('Демо');
  });
});

test.describe('Генерация изображений', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/demo');
  });

  test('пользователь может сгенерировать изображение', async ({ page }) => {
    // Заполняем поле промпта
    const promptInput = page.locator('textarea[name="prompt"], input[name="prompt"], textarea:has-text("опишите")');
    await promptInput.fill('Красивый закат над морем с пальмами');
    
    // Выбираем параметры генерации если они есть
    const imageCountSelect = page.locator('select[name="imageCount"], select:has-text("количество")');
    if (await imageCountSelect.isVisible()) {
      await imageCountSelect.selectOption('1');
    }

    // Нажимаем кнопку генерации
    const generateButton = page.locator('button:has-text("Генерировать"), button[type="submit"]');
    await generateButton.click();
    
    // Проверяем что появился индикатор загрузки
    await expect(page.locator('.loading, [data-testid="loading"], .spinner')).toBeVisible();
    
    // Ждем завершения генерации (таймаут 30 секунд)
    await expect(page.locator('img, canvas, [data-testid="generated-image"]'))
      .toBeVisible({ timeout: 30000 });
  });

  test('должна показывать ошибки при некорректном вводе', async ({ page }) => {
    // Попытка генерации с пустым промптом
    const generateButton = page.locator('button:has-text("Генерировать")');
    await generateButton.click();
    
    // Проверяем что появилось сообщение об ошибке
    await expect(page.locator('.error, .alert-error, [data-testid="error"]')).toBeVisible();
    
    // Проверяем текст ошибки
    const errorMessage = page.locator('.error, .alert-error');
    await expect(errorMessage).toContainText(/не|empty|обязательн/i);
  });
});

test.describe('Живое демо', () => {
  test('страница живого демо должна работать', async ({ page }) => {
    await page.goto('/live-demo');
    
    // Проверяем основные элементы
    await expect(page.locator('h1')).toContainText('Живое демо');
    
    // Проверяем элементы интерфейса для живого демо
    await expect(page.locator('video, [data-testid="camera-preview"]')).toBeVisible();
    await expect(page.locator('button:has-text("Начать")')).toBeVisible();
  });

  test('можно начать запись видео', async ({ page }) => {
    await page.goto('/live-demo');
    
    // Кликаем кнопку "Начать"
    await page.click('button:has-text("Начать")');
    
    // Проверяем что появились элементы управления
    await expect(page.locator('button:has-text("Стоп")')).toBeVisible();
    
    // Ждем немного для инициализации
    await page.waitForTimeout(1000);
    
    // Кликаем кнопку "Стоп"
    await page.click('button:has-text("Стоп")');
    
    // Проверяем что процесс остановился
    await expect(page.locator('button:has-text("Начать")')).toBeVisible();
  });
});

test.describe('Валидация страницы', () => {
  test('страница валидации должна загружаться', async ({ page }) => {
    await page.goto('/validation');
    
    await expect(page.locator('h1')).toContainText('Валидация');
    await expect(page.locator('form, [data-testid="validation-form"]')).toBeVisible();
  });

  test('валидация форм должна работать', async ({ page }) => {
    await page.goto('/validation');
    
    // Заполняем форму с корректными данными
    const nameInput = page.locator('input[name="name"], input:has-text("имя")');
    const emailInput = page.locator('input[name="email"], input:has-text("email")');
    
    if (await nameInput.isVisible()) {
      await nameInput.fill('Тест Пользователь');
    }
    
    if (await emailInput.isVisible()) {
      await emailInput.fill('test@example.com');
    }
    
    // Отправляем форму
    await page.click('button[type="submit"], button:has-text("Отправить")');
    
    // Проверяем успешную валидацию
    await expect(page.locator('.success, .alert-success, [data-testid="success"]'))
      .toBeVisible({ timeout: 5000 });
  });
});

test.describe('Адаптивность', () => {
  test('сайт должен быть адаптивным', async ({ page }) => {
    await page.goto('/');
    
    // Проверяем мобильную версию
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Проверяем что гамбургер меню появилось
    await expect(page.locator('[data-testid="mobile-menu"], .mobile-menu-toggle, .hamburger')).toBeVisible();
    
    // Проверяем десктопную версию
    await page.setViewportSize({ width: 1920, height: 1080 });
    
    // Гамбургер меню должно исчезнуть
    await expect(page.locator('nav, .desktop-nav')).toBeVisible();
  });
});

test.describe('Производительность', () => {
  test('страницы должны загружаться быстро', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    
    // Ждем полной загрузки страницы
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // Время загрузки должно быть меньше 3 секунд
    expect(loadTime).toBeLessThan(3000);
    
    console.log(`Страница загрузилась за ${loadTime}ms`);
  });

  test('генерация изображений не должна блокировать UI', async ({ page }) => {
    await page.goto('/demo');
    
    // Начинаем генерацию
    const promptInput = page.locator('textarea[name="prompt"]');
    await promptInput.fill('Тестовое изображение');
    
    const generateButton = page.locator('button:has-text("Генерировать")');
    await generateButton.click();
    
    // Проверяем что UI остается отзывчивым
    await expect(page.locator('body')).toBeVisible();
    
    // Можем взаимодействовать с другими элементами
    const navigationLinks = page.locator('nav a, nav button');
    if (await navigationLinks.isVisible()) {
      await navigationLinks.first().hover();
    }
    
    // Ждем завершения генерации
    await expect(page.locator('img')).toBeVisible({ timeout: 30000 });
  });
});

test.describe('Обработка ошибок', () => {
  test('должна корректно показывать страницу 404', async ({ page }) => {
    await page.goto('/non-existent-page');
    
    // Проверяем что мы на странице 404
    await expect(page).toHaveTitle(/404|Not Found/i);
    await expect(page.locator('h1')).toContainText(/404|Not Found|не найден/i);
  });

  test('должна показывать ошибки сети', async ({ page }) => {
    // Перехватываем сетевые запросы
    await page.route('**/api/**', route => {
      route.abort('internetdisconnected');
    });
    
    await page.goto('/demo');
    
    // Попытка генерации должна показать ошибку сети
    const promptInput = page.locator('textarea[name="prompt"]');
    await promptInput.fill('Тест ошибки сети');
    
    const generateButton = page.locator('button:has-text("Генерировать")');
    await generateButton.click();
    
    // Ждем появления ошибки
    await expect(page.locator('.error, .alert-error, [data-testid="error"]'))
      .toBeVisible({ timeout: 10000 });
  });
});

test.describe('Доступность', () => {
  test('страницы должны быть доступны', async ({ page }) => {
    await page.goto('/');
    
    // Проверяем наличие aria-label у важных элементов
    const interactiveElements = page.locator('button, a, input, textarea, select');
    const count = await interactiveElements.count();
    
    for (let i = 0; i < count; i++) {
      const element = interactiveElements.nth(i);
      const ariaLabel = await element.getAttribute('aria-label');
      const text = await element.textContent();
      
      // Каждый интерактивный элемент должен иметь aria-label или текст
      expect(ariaLabel || text).toBeTruthy();
    }
  });

  test('должна работать навигация с клавиатуры', async ({ page }) => {
    await page.goto('/');
    
    // Используем Tab для навигации
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Проверяем что фокус перемещается
    const focusedElement = await page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});
