import { FullConfig } from '@playwright/test';
import { execSync } from 'child_process';

async function globalTeardown(config: FullConfig) {
  console.log('🧪 Playwright Global Teardown');
  
  try {
    // Собираем coverage данные если они есть
    if (process.env.CI) {
      try {
        execSync('npx nyc report --reporter=lcov', { stdio: 'inherit' });
      } catch (error) {
        console.warn('Не удалось сгенерировать coverage отчет:', error);
      }
    }

    // Архивируем результаты тестов
    try {
      execSync('tar -czf coverage/playwright/test-results.tar.gz coverage/playwright/', { stdio: 'ignore' });
    } catch (error) {
      console.warn('Не удалось создать архив результатов:', error);
    }

    // Генерируем summary отчет
    try {
      const summary = generateTestSummary();
      console.log('\n' + '='.repeat(60));
      console.log('📊 E2E ТЕСТ SUMMARY');
      console.log('='.repeat(60));
      console.log(summary);
      console.log('='.repeat(60));
    } catch (error) {
      console.warn('Не удалось создать summary:', error);
    }

  } catch (error) {
    console.error('Ошибка при global teardown:', error);
  }

  console.log('✅ Global Teardown завершен');
}

function generateTestSummary(): string {
  try {
    const { readFileSync, existsSync } = require('fs');
    
    if (!existsSync('./coverage/playwright/results.json')) {
      return '❌ Результаты тестов не найдены';
    }

    const resultsData = JSON.parse(readFileSync('./coverage/playwright/results.json', 'utf8'));
    
    let summary = '';
    
    // Общая статистика
    const totalTests = resultsData.stats?.tests || 0;
    const passedTests = resultsData.stats?.passes || 0;
    const failedTests = resultsData.stats?.failures || 0;
    const skippedTests = resultsData.stats?.pending || 0;
    
    summary += `Всего тестов: ${totalTests}\n`;
    summary += `Пройдено: ${passedTests} ✅\n`;
    summary += `Провалено: ${failedTests} ❌\n`;
    summary += `Пропущено: ${skippedTests} ⏭️\n\n`;
    
    // Статистика по браузерам
    if (resultsData.suites && resultsData.suites.length > 0) {
      summary += 'Статистика по браузерам:\n';
      
      for (const suite of resultsData.suites) {
        if (suite.suites) {
          for (const browserSuite of suite.suites) {
            const browserTests = browserSuite.tests || [];
            const browserPassed = browserTests.filter((t: any) => t.status === 'passed').length;
            const browserFailed = browserTests.filter((t: any) => t.status === 'failed').length;
            
            summary += `  ${browserSuite.title}: ${browserPassed}/${browserTests.length} ✅\n`;
          }
        }
      }
    }

    // Список проваленных тестов
    if (failedTests > 0) {
      summary += '\nПроваленные тесты:\n';
      
      const failures: any[] = [];
      
      for (const suite of resultsData.suites || []) {
        for (const browserSuite of suite.suites || []) {
          for (const test of browserSuite.tests || []) {
            if (test.status === 'failed') {
              failures.push({
                browser: browserSuite.title,
                test: test.title,
                error: test.err?.message || 'Unknown error'
              });
            }
          }
        }
      }

      failures.forEach((failure, index) => {
        summary += `  ${index + 1}. [${failure.browser}] ${failure.test}\n`;
        summary += `     ❌ ${failure.error}\n\n`;
      });
    }

    // Рекомендации
    summary += '\nРекомендации:\n';
    
    if (failedTests > totalTests * 0.1) {
      summary += '  ⚠️ Большое количество проваленных тестов. Рекомендуется:\n';
      summary += '     - Проверить стабильность тестов\n';
      summary += '     - Увеличить таймауты\n';
      summary += '     - Проверить зависимости\n\n';
    }
    
    if (passedTests === totalTests) {
      summary += '  🎉 Все тесты пройдены! Отличная работа!\n';
    } else if (passedTests > totalTests * 0.8) {
      summary += '  ✅ Большинство тестов пройдено. Проверьте проваленные тесты.\n';
    } else {
      summary += '  ❌ Много тестов провалено. Требуется серьезная доработка.\n';
    }

    return summary;
  } catch (error) {
    return `Ошибка при генерации summary: ${error}`;
  }
}

export default globalTeardown;
