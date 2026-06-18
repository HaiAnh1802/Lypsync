@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   Setup viXTTS - Vietnamese Voice Cloning
echo   Dung Python 3.11 (venv_vixtts)
echo =====================================================
echo.

:: Kiem tra venv_vixtts
if not exist "venv_vixtts\Scripts\python.exe" (
    echo [ERROR] Khong tim thay venv_vixtts!
    echo Tao venv: py -3.11 -m venv venv_vixtts
    pause
    exit /b 1
)

echo [1/3] Nang cap pip...
venv_vixtts\Scripts\python -m pip install --upgrade pip --quiet

echo [2/3] Cai viXTTS fork (Python 3.11)...
echo [INFO] Dang clone repo tu GitHub, vui long cho (~2-5 phut)...
venv_vixtts\Scripts\pip install git+https://github.com/thinhlpg/TTS.git@add-vietnamese-xtts --quiet

if %errorlevel% neq 0 (
    echo [ERROR] Cai viXTTS that bai!
    pause
    exit /b 1
)

echo [3/3] Cai cac thu vien phu...
venv_vixtts\Scripts\pip install huggingface_hub soundfile --quiet

echo.
echo [SUCCESS] Setup xong!
echo.
echo Buoc tiep theo: Chay download_xtts_model.bat de download model (~1.8GB)
echo.
pause
