@echo off
REM ============================================================================
REM 1C AI Stack - Quick Start Script (Windows)
REM ============================================================================

echo.
echo ============================================================
echo 1C AI Stack - Quick Start
echo ============================================================
echo.

REM Проверка Python
echo Checking dependencies...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.8+
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo [OK] %%i

REM Проверка Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js %%i

REM Проверка Docker (опционально)
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('docker --version') do echo [OK] %%i
) else (
    echo [WARNING] Docker not found (optional)
)

echo.
echo Creating configuration files...
if not exist .env (
    python setup.py
) else (
    echo [WARNING] .env already exists, skipping
)

echo.
echo Installing Python dependencies...
pip install -r requirements.txt
pip install -r requirements-stage1.txt

echo.
echo Installing Frontend dependencies...
cd frontend-portal
call npm install
cd ..

echo.
echo Creating directories...
if not exist knowledge_base mkdir knowledge_base
if not exist cache mkdir cache
if not exist logs mkdir logs

echo.
echo ============================================================
echo Setup complete!
echo.
echo [IMPORTANT] Fill in OAuth2 and Email credentials in .env
echo.
echo Starting services:
echo   1. Start databases:
echo      docker-compose up -d postgres redis
echo.
echo   2. Start backend:
echo      python -m uvicorn src.main:app --reload
echo.
echo   3. Start frontend:
echo      cd frontend-portal ^&^& npm run dev
echo.
echo See TESTING_VERIFICATION_GUIDE.md for details
echo ============================================================
pause
