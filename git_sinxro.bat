@echo off
setlocal

set REPO_PATH=%~dp0
set COMMIT_MSG=auto-update: %date% %time%
cd /d "%REPO_PATH%"

echo === Updating GitHub repository ===

:: 1. Перевірка статусу (чи є взагалі зміни)
git status --short | findstr /R "^" >nul
if %errorlevel% neq 0 (
    echo [INFO] Немає змін для оновлення.
    exit /b
)

:: 2. Оновлення
git pull --no-rebase

:: 3. Додавання та комміт (прибираємо >nul, щоб бачити помилки)
git add -A
git commit -m "%COMMIT_MSG%"

:: 4. Відправка (явно вказуємо поточну гілку)
git push origin HEAD

echo === Done ===