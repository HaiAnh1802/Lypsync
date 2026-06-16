@echo off
chcp 65001 >nul
echo ============================================
echo   LipSync AI – Setup Voice Clone (F5-TTS)
echo ============================================
echo.

REM === Kiem tra venv ===
echo [1/3] Kiem tra venv...
if exist "venv_gpu\Scripts\activate.bat" (
    call venv_gpu\Scripts\activate.bat
    echo OK: Dang dung venv_gpu
) else (
    echo CANH BAO: Khong tim thay venv_gpu
)
echo.

REM === Nang cap pip + setuptools (fix Python 3.12) ===
echo [2/3] Nang cap pip / setuptools / wheel...
python -m pip install --upgrade pip setuptools wheel
echo OK
echo.

REM === Cai F5-TTS ===
echo [3/3] Cai F5-TTS va soundfile...
pip install f5-tts soundfile
if errorlevel 1 (
    echo.
    echo LOI: Khong the cai F5-TTS!
    echo Kiem tra ket noi mang roi thu lai.
    pause & exit /b 1
)
echo OK: F5-TTS da cai xong
echo.

REM === Test ===
python -c "from f5_tts.api import F5TTS; print('OK: F5-TTS san sang!')"
if errorlevel 1 (
    echo CANH BAO: F5-TTS cai nhung chua test duoc - co the OK sau khi restart
)
echo.

echo ============================================
echo   Setup hoan tat!
echo.
echo   Lan dau chay Voice Clone se tu dong
echo   download model ~1.5GB (1 lan duy nhat).
echo   Sau do tat ca se rat nhanh.
echo.
echo   Chay run.bat de khoi dong app.
echo ============================================
pause
