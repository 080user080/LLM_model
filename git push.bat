@echo off
cd /d D:\Python\TEXT\LLM_model

echo Додаю всі зміни...
git add -A

echo Коміт...
set /p msg=Введи повідомлення коміту: 
if "%msg%"=="" set msg=update

git commit -m "%msg%"

echo Пуш в main...
git push origin main

pause