@echo off
chcp 65001 > nul
setlocal

echo ========================================
echo    1C MCP HTTP Server
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Убедитесь, что Python установлен и добавлен в PATH.
    pause
    exit /b 1
)

echo ✅ Python найден: 
python --version

REM Переход в директорию скрипта
cd /d "%~dp0"

REM Активация виртуального окружения, если оно существует
if exist "venv\Scripts\activate.bat" (
    echo 🐍 Активация виртуального окружения...
    call venv\Scripts\activate.bat
)

echo.
echo 🚀 Запуск HTTP сервера...
echo ⏹️  Для остановки нажмите Ctrl+C
echo.
echo 📡 Сервер будет доступен на http://127.0.0.1:8000
echo    🏠 Главная страница: http://127.0.0.1:8000/
echo    ❤️  Health check: http://127.0.0.1:8000/health
echo    ℹ️  Server info: http://127.0.0.1:8000/info
echo    🔌 SSE для MCP: http://127.0.0.1:8000/sse
echo    🚀 Streamable HTTP для MCP: http://127.0.0.1:8000/mcp
echo.

REM Запуск сервера
python -m src.py_server http

echo.
echo ⏹️  Сервер остановлен
pause 