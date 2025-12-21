@echo off
setlocal

:: Шлях до вашої папки
set REPO_PATH=%~dp0
cd /d "%REPO_PATH%"

echo === Sending changes to GitHub main ===

:: 1. Додаємо всі файли
git add -A

:: 2. Створюємо комміт (мітка часу)
git commit -m "update %date% %time%"

:: 3. Відправляємо локальний код прямо в main на GitHub
:: Використовуємо HEAD:main, щоб відправити поточну гілку в main на сервері
git push origin HEAD:main

echo === Done! Check GitHub main branch ===
