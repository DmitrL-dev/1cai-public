#!/usr/bin/env deno run --allow-read --allow-write --allow-run --allow-net

/**
 * Скрипт для запуска всех тестов с coverage reporting
 * Включает unit, integration и E2E тесты
 */

import { join } from "https://deno.land/std@0.224.0/path/mod.ts";
import { ensureDir } from "https://deno.land/std@0.224.0/fs/mod.ts";

interface TestResult {
  name: string;
  passed: boolean;
  duration: number;
  output?: string;
  error?: string;
}

class TestRunner {
  private results: TestResult[] = [];
  private coverageDir = ".deno/coverage";
  private reportDir = "coverage";

  async run() {
    console.log("🚀 Запуск полного тестового набора...\n");

    try {
      // Создаем необходимые директории
      await ensureDir(this.coverageDir);
      await ensureDir(this.reportDir);

      // Запускаем все тесты
      await this.runUnitTests();
      await this.runIntegrationTests();
      await this.runE2ETests();

      // Генерируем итоговый отчет
      await this.generateCoverageReport();

      // Выводим результаты
      this.printResults();

      // Возвращаем код выхода на основе результатов
      const allPassed = this.results.every(r => r.passed);
      Deno.exit(allPassed ? 0 : 1);
    } catch (error) {
      console.error("❌ Критическая ошибка при выполнении тестов:", error);
      Deno.exit(1);
    }
  }

  private async runCommand(
    name: string,
    command: string,
    args: string[] = [],
    env: Record<string, string> = {}
  ): Promise<TestResult> {
    const start = Date.now();
    console.log(`📋 ${name}...`);

    try {
      // Добавляем coverage переменные окружения
      const coverageEnv = {
        ...env,
        "DENO_COVERAGE": "1",
        "COVERAGE_DIR": this.coverageDir,
      };

      const process = new Deno.Command(command, {
        args,
        env: coverageEnv,
        stdout: "piped",
        stderr: "piped",
      });

      const { code, stdout, stderr } = await process.output();
      const duration = Date.now() - start;
      const output = new TextDecoder().decode(stdout);
      const errorOutput = new TextDecoder().decode(stderr);

      const passed = code === 0;
      
      if (output) console.log(output);
      if (errorOutput && !passed) console.error(errorOutput);

      const result: TestResult = {
        name,
        passed,
        duration,
        output: output || undefined,
        error: errorOutput || undefined,
      };

      this.results.push(result);
      console.log(`${passed ? "✅" : "❌"} ${name} завершен (${duration}ms)\n`);
      
      return result;
    } catch (error) {
      const duration = Date.now() - start;
      const result: TestResult = {
        name,
        passed: false,
        duration,
        error: error.message,
      };
      
      this.results.push(result);
      console.error(`❌ ${name} провален (${duration}ms):`, error.message, "\n");
      
      return result;
    }
  }

  private async runUnitTests() {
    await this.runCommand(
      "Unit тесты",
      "deno",
      [
        "test",
        "--allow-read",
        "--allow-net",
        "--allow-env",
        "--coverage=" + this.coverageDir,
        "--reporter=pretty",
        "src/**/*.test.{ts,tsx}",
      ]
    );
  }

  private async runIntegrationTests() {
    await this.runCommand(
      "Integration тесты",
      "deno",
      [
        "test",
        "--allow-read",
        "--allow-net",
        "--allow-env",
        "--allow-run",
        "--coverage=" + this.coverageDir,
        "--reporter=pretty",
        "tests/integration/**/*.test.{ts,tsx}",
      ]
    );
  }

  private async runE2ETests() {
    // Сначала собираем проект
    await this.runCommand(
      "Сборка для E2E тестов",
      "pnpm",
      ["build"]
    );

    // Запускаем preview сервер
    const serverProcess = new Deno.Command("pnpm", {
      args: ["preview", "--host", "--port", "4173"],
      env: {
        "PORT": "4173",
        "HOST": "0.0.0.0",
      },
      stdout: "piped",
      stderr: "piped",
    });

    console.log("🖥️ Запуск preview сервера для E2E тестов...");
    const server = serverProcess.spawn();
    
    // Ждем запуска сервера
    await new Promise(resolve => setTimeout(resolve, 5000));

    try {
      // Запускаем Playwright тесты
      await this.runCommand(
        "E2E тесты (Playwright)",
        "npx",
        [
          "playwright",
          "test",
          "--reporter=html",
          "--outputDir=" + this.reportDir + "/playwright",
        ],
        {
          "PLAYWRIGHT_BROWSERS_PATH": ".playwright",
        }
      );
    } finally {
      // Останавливаем сервер
      server.stdout.cancel();
      server.stderr.cancel();
      server.kill();
      console.log("🖥️ Preview сервер остановлен");
    }
  }

  private async generateCoverageReport() {
    console.log("📊 Генерация coverage отчета...");

    try {
      // Объединяем coverage данные
      await this.runCommand(
        "Объединение coverage данных",
        "deno",
        [
          "coverage",
          "merge",
          "--output=" + this.reportDir + "/coverage-final.json",
          this.coverageDir,
        ]
      );

      // Генерируем HTML отчет
      await this.runCommand(
        "Генерация HTML отчета",
        "deno",
        [
          "coverage",
          "html",
          "--output-dir=" + this.reportDir + "/html",
          this.reportDir + "/coverage-final.json",
        ]
      );

      // Генерируем LCOV отчет
      await this.runCommand(
        "Генерация LCOV отчета",
        "deno",
        [
          "coverage",
          "lcov",
          "--output=" + this.reportDir + "/coverage.lcov",
          this.reportDir + "/coverage-final.json",
        ]
      );

      console.log("✅ Coverage отчеты сгенерированы в " + this.reportDir + "/");
    } catch (error) {
      console.error("❌ Ошибка генерации coverage отчета:", error);
    }
  }

  private printResults() {
    console.log("\n" + "=".repeat(60));
    console.log("📋 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ");
    console.log("=".repeat(60));

    let totalPassed = 0;
    let totalDuration = 0;

    for (const result of this.results) {
      const status = result.passed ? "✅ ПРОЙДЕН" : "❌ ПРОВАЛЕН";
      const duration = `${result.duration}ms`;
      
      console.log(`${result.name}: ${status} (${duration})`);
      
      if (result.passed) totalPassed++;
      totalDuration += result.duration;

      if (result.error) {
        console.log(`   Ошибка: ${result.error}`);
      }
    }

    console.log("\n" + "-".repeat(60));
    console.log(`Общий результат: ${totalPassed}/${this.results.length} тестов пройдено`);
    console.log(`Общее время: ${totalDuration}ms`);
    console.log(`Coverage отчеты: ${this.reportDir}/`);
    console.log("-".repeat(60));

    if (totalPassed === this.results.length) {
      console.log("🎉 Все тесты успешно пройдены!");
    } else {
      console.log("⚠️ Некоторые тесты провалены. Проверьте отчет выше.");
    }
  }
}

// Запускаем тесты если скрипт выполнен напрямую
if (import.meta.main) {
  const runner = new TestRunner();
  runner.run();
}

export { TestRunner };
