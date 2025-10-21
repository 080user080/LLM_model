@echo off
setlocal

:: === GitHub Auto Upload (без підтверджень) ===
set REPO_PATH=%~dp0
set COMMIT_MSG=auto-update
cd /d "%REPO_PATH%"

echo === Updating GitHub repository ===

:: Перевірка ініціалізації
git rev-parse --is-inside-work-tree >nul 2>&1 || (
    echo [ERROR] Це не git-репозиторій.
    exit /b
)

:: Оновлення з GitHub (без rebase для безпеки)
git pull --no-rebase

:: Додавання всіх змін
git add -A

:: Комміт з фіксованим повідомленням
git commit -m "%COMMIT_MSG%" >nul 2>&1

:: Відправка на GitHub
git push

echo === Done ===
