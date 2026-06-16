@echo off
REM Автоматический запуск всех оптимизаций парсера (Windows)
REM Использование: run_optimization.bat [quick|full|benchmark|parse|dataset]

echo ======================================
echo 🚀 1C Parser Optimization Runner
echo ======================================

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден!
    exit /b 1
)
echo [INFO] ✅ Python найден

REM Проверка Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker не найден!
    exit /b 1
)
echo [INFO] ✅ Docker найден

REM Режим работы
set MODE=%1
if "%MODE%"=="" set MODE=quick

if "%MODE%"=="quick" goto QUICK
if "%MODE%"=="full" goto FULL
if "%MODE%"=="benchmark" goto BENCHMARK
if "%MODE%"=="parse" goto PARSE
if "%MODE%"=="dataset" goto DATASET

echo Usage: %0 [quick^|full^|benchmark^|parse^|dataset]
exit /b 1

:QUICK
echo [INFO] Режим: Быстрый тест
echo.
echo [INFO] Установка зависимостей...
pip install -q -r requirements-parser-optimization.txt

echo.
echo [INFO] Запуск Docker сервисов...
docker-compose -f docker-compose.parser.yml up -d

echo.
echo [INFO] Ожидание готовности сервисов...
timeout /t 10 /nobreak >nul

echo.
echo [INFO] Запуск тестов...
python scripts\test_parser_optimization.py --quick
goto END

:FULL
echo [INFO] Режим: Полная оптимизация
pip install -q -r requirements-parser-optimization.txt
docker-compose -f docker-compose.parser.yml up -d
timeout /t 10 /nobreak >nul

python scripts\test_parser_optimization.py --quick
echo.
python scripts\parsers\parser_integration.py
echo.
python scripts\dataset\massive_ast_dataset_builder.py
goto END

:BENCHMARK
echo [INFO] Режим: Benchmark
docker-compose -f docker-compose.parser.yml up -d
timeout /t 10 /nobreak >nul
python scripts\test_parser_optimization.py --benchmark
goto END

:PARSE
echo [INFO] Режим: Только парсинг
docker-compose -f docker-compose.parser.yml up -d
timeout /t 10 /nobreak >nul
python scripts\parsers\parser_integration.py
goto END

:DATASET
echo [INFO] Режим: Создание dataset
docker-compose -f docker-compose.parser.yml up -d
timeout /t 10 /nobreak >nul
python scripts\dataset\massive_ast_dataset_builder.py
goto END

:END
echo.
echo ======================================
echo [INFO] ✅ Готово!
echo ======================================
echo.
echo Следующие шаги:
echo   1. Проверьте результаты выше
echo   2. Для полного pipeline: run_optimization.bat full
echo   3. Для benchmark: run_optimization.bat benchmark
echo.
echo Документация: QUICK_START_OPTIMIZATION.md


