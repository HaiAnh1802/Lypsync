@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   Download viXTTS - Vietnamese Voice Cloning Model
echo   (~1.8GB) - Chi can chay 1 lan
echo =====================================================
echo.

:: Kiem tra venv_vixtts
if not exist "venv_vixtts\Scripts\python.exe" (
    echo [ERROR] venv_vixtts chua duoc setup!
    echo Chay setup_vixtts.bat truoc.
    pause
    exit /b 1
)

echo [INFO] Dang download model viXTTS...
echo [INFO] Vui long cho, co the mat 5-15 phut tuy toc do mang.
echo.

venv_vixtts\Scripts\python download_xtts_model.py

if %errorlevel% == 0 (
    echo.
    echo [SUCCESS] Download xong! Chay app binh thuong.
) else (
    echo.
    echo [ERROR] Download that bai. Kiem tra ket noi mang va thu lai.
)
pause
