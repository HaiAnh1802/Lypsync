@echo off
chcp 65001 >nul
echo ============================================
echo   LipSync AI - Setup Voice Clone (F5-TTS)
echo ============================================
echo.

REM Them FFmpeg vao PATH
set "FFMPEG_BIN=C:\Users\anhbun\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"
set "PATH=%PATH%;%FFMPEG_BIN%"

REM === Kiem tra venv ===
echo [1/4] Kiem tra venv...
if exist "venv_gpu\Scripts\activate.bat" (
    call venv_gpu\Scripts\activate.bat
    set "PYTHON=venv_gpu\Scripts\python.exe"
    set "PIP=venv_gpu\Scripts\pip.exe"
    echo OK: Dang dung venv_gpu
) else (
    set "PYTHON=python"
    set "PIP=pip"
    echo CANH BAO: Khong tim thay venv_gpu
)
echo.

REM === Nang cap pip ===
echo [2/4] Nang cap pip / setuptools / wheel...
%PIP% install --upgrade pip setuptools wheel
echo OK
echo.

REM === Cai F5-TTS ===
echo [3/4] Cai F5-TTS va soundfile...
%PIP% install f5-tts soundfile
if errorlevel 1 (
    echo.
    echo LOI: Khong the cai F5-TTS!
    echo Kiem tra ket noi mang roi thu lai.
    pause & exit /b 1
)
echo OK: F5-TTS da cai xong
echo.

REM === Download model vao project ===
echo [4/4] Tai model F5-TTS vao models/f5tts/ ...
echo (Qua trinh nay chi xay ra 1 lan duy nhat, mat khoang 5-10 phut)
echo.
%PYTHON% download_f5tts_model.py
if errorlevel 1 (
    echo.
    echo LOI: Khong the tai model!
    echo Kiem tra ket noi internet roi chay lai setup_voiceclone.bat.
    pause & exit /b 1
)
echo.

echo ============================================
echo   Setup hoan tat!
echo.
echo   Model da luu vao: models/f5tts/
echo   App se dung local model, KHONG can internet.
echo.
echo   Chay run.bat de khoi dong app.
echo ============================================
pause
