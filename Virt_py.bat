@echo off
cd /d D:\Python\TEXT\LLM_model

REM --- Шлях до Python 3.10 ---
set PYTHON_PATH=C:\Users\User\AppData\Local\Programs\Python\Python310\python.exe

REM --- Назва віртуального середовища ---
set VENV_NAME=venv

REM --- Якщо середовище не існує, створюємо ---
if not exist "%VENV_NAME%\Scripts\activate.bat" (
    echo Створення віртуального середовища %VENV_NAME%...
    "%PYTHON_PATH%" -m venv %VENV_NAME%
)

REM --- Активація середовища ---
echo Активація середовища...
call %VENV_NAME%\Scripts\activate.bat

REM --- Консоль залишається відкритою ---
cmd /K
