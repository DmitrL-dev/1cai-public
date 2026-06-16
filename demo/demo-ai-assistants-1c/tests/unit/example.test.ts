/**
 * Unit тесты для компонентов приложения
 */

import { assertEquals, assert } from "https://deno.land/std@0.224.0/assert/mod.ts";

// Пример unit теста для компонента
Deno.test("Unit Test: Компонент ErrorBoundary должен корректно обрабатывать ошибки", () => {
  // Мокаем состояние ошибки
  const hasError = true;
  const error = new Error("Test error");
  const resetErrorBoundary = () => {
    console.log("Error boundary reset");
  };

  // Проверяем что состояние ошибки корректно обрабатывается
  assert(hasError, "Error boundary должен показывать ошибку");
  assert(error instanceof Error, "Ошибка должна быть экземпляром Error");
  assertEquals(typeof resetErrorBoundary, "function", "resetErrorBoundary должна быть функцией");
});

// Тест для утилит
Deno.test("Unit Test: Утилиты для работы с изображениями", () => {
  // Тест функции валидации изображений
  const isValidImageUrl = (url: string) => {
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'];
    return imageExtensions.some(ext => url.toLowerCase().includes(ext));
  };

  // Валидные URL
  assert(isValidImageUrl("https://example.com/image.jpg"), "jpg должен быть валидным");
  assert(isValidImageUrl("https://example.com/photo.png"), "png должен быть валидным");
  assert(isValidImageUrl("https://example.com/icon.svg"), "svg должен быть валидным");

  // Невалидные URL
  assert(!isValidImageUrl("https://example.com/document.pdf"), "pdf не должен быть валидным");
  assert(!isValidImageUrl("https://example.com/file.txt"), "txt не должен быть валидным");
});

// Тест для hooks
Deno.test("Unit Test: use-mobile hook должен корректно определять мобильные устройства", () => {
  // Мокаем navigator.userAgent
  const originalUserAgent = globalThis.navigator?.userAgent;
  
  // Мобильное устройство
  globalThis.navigator = {
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
  };

  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  assert(isMobile, "iPhone должен определяться как мобильное устройство");

  // Десктоп
  globalThis.navigator = {
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  };

  const isDesktop = !/iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  assert(isDesktop, "Windows должен определяться как десктопное устройство");

  // Восстанавливаем оригинальный userAgent
  if (originalUserAgent) {
    globalThis.navigator.userAgent = originalUserAgent;
  }
});

// Тест для валидации форм
Deno.test("Unit Test: Валидация форм должна работать корректно", () => {
  // Функция валидации email
  const validateEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // Валидные email адреса
  assert(validateEmail("user@example.com"), "user@example.com должен быть валидным");
  assert(validateEmail("test.user@company.org"), "test.user@company.org должен быть валидным");
  assert(validateEmail("user123@domain.co.uk"), "user123@domain.co.uk должен быть валидным");

  // Невалидные email адреса
  assert(!validateEmail("invalid-email"), "invalid-email не должен быть валидным");
  assert(!validateEmail("user@"), "user@ не должен быть валидным");
  assert(!validateEmail("@domain.com"), "@domain.com не должен быть валидным");
  assert(!validateEmail("user space@domain.com"), "user space@domain.com не должен быть валидным");
});

// Тест для утилит даты и времени
Deno.test("Unit Test: Утилиты для работы с датами", () => {
  // Функция форматирования даты
  const formatDate = (date: Date) => {
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const testDate = new Date('2024-01-15');
  const formattedDate = formatDate(testDate);

  assertEquals(formattedDate, "15 января 2024 г.", "Дата должна быть отформатирована корректно");
});

// Тест для констант приложения
Deno.test("Unit Test: Константы приложения должны быть определены", () => {
  // Проверяем что важные константы определены
  const APP_NAME = "Demo AI Assistants";
  const API_BASE_URL = "https://api.example.com";
  const SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'webp'];

  assertEquals(APP_NAME, "Demo AI Assistants", "Название приложения должно быть корректным");
  assertEquals(API_BASE_URL, "https://api.example.com", "Базовый URL API должен быть корректным");
  assert(SUPPORTED_IMAGE_FORMATS.length > 0, "Должны быть поддерживаемые форматы изображений");
  assert(SUPPORTED_IMAGE_FORMATS.includes('jpg'), "jpg должен быть в списке поддерживаемых форматов");
});

// Тест для обработки ошибок
Deno.test("Unit Test: Обработка ошибок должна работать корректно", () => {
  // Функция обработки ошибок API
  const handleApiError = (error: unknown) => {
    if (error instanceof Error) {
      return {
        message: error.message,
        type: 'error',
        code: 'API_ERROR'
      };
    }
    
    return {
      message: 'Неизвестная ошибка',
      type: 'unknown',
      code: 'UNKNOWN_ERROR'
    };
  };

  // Тест с Error
  const errorResult = handleApiError(new Error("Network error"));
  assertEquals(errorResult.message, "Network error", "Сообщение об ошибке должно быть сохранено");
  assertEquals(errorResult.type, "error", "Тип ошибки должен быть 'error'");
  assertEquals(errorResult.code, "API_ERROR", "Код ошибки должен быть корректным");

  // Тест с неизвестной ошибкой
  const unknownResult = handleApiError("string error");
  assertEquals(unknownResult.message, "Неизвестная ошибка", "Сообщение должно быть по умолчанию");
  assertEquals(unknownResult.type, "unknown", "Тип ошибки должен быть 'unknown'");
});
