# Скрипт восстановления и завершения рефакторинга
# Запустить из директории C:\1cAI

Write-Host "=== Восстановление оригинальных файлов из бэкапа ===" -ForegroundColor Green

# Шаг 1: Сохранить backward compat файлы во временную директорию
Write-Host "Шаг 1: Сохранение backward compat файлов..." -ForegroundColor Yellow
$tempDir = "C:\1cAI\temp_backward_compat"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
Copy-Item "C:\1cAI\src\api\*.py" $tempDir -Force

# Шаг 2: Восстановить оригинальные файлы из бэкапа
Write-Host "Шаг 2: Восстановление оригинальных файлов из бэкапа..." -ForegroundColor Yellow
Copy-Item "C:\1cAIbackup\src\api\*.py" "C:\1cAI\src\api\" -Force

Write-Host "Готово! Оригинальные файлы восстановлены." -ForegroundColor Green
Write-Host ""
Write-Host "Следующие шаги:" -ForegroundColor Cyan
Write-Host "1. Я скопирую код в модули (src/modules/*/api/routes.py)"
Write-Host "2. Верну backward compat файлы из $tempDir"
Write-Host "3. Удалю временную директорию"
Write-Host ""
Write-Host "Запустите этот скрипт и дайте мне знать, когда будет готово!" -ForegroundColor Green
