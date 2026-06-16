@echo off
echo ====================================
echo   LipSync AI - Dang khoi dong...
echo ====================================
echo.

REM Them FFmpeg vao PATH
set "FFMPEG_BIN=C:\Users\anhbun\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"
set "PATH=%PATH%;%FFMPEG_BIN%"

REM Uu tien dung venv_gpu (Python 3.12 + CUDA) neu co
if exist "venv_gpu\Scripts\python.exe" (
    echo [GPU] Dung venv_gpu Python 3.12 + CUDA
    set "PYTHON=venv_gpu\Scripts\python.exe"
    set "PIP=venv_gpu\Scripts\pip.exe"
) else (
    echo [CPU] Khong tim thay venv_gpu, dung Python mac dinh
    set "PYTHON=python"
    set "PIP=pip"
)

REM Kiem tra CUDA
%PYTHON% -c "import torch; gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Khong co GPU'; print('[Device]', gpu)"

echo.
echo Truy cap: http://localhost:8000
echo Nhan Ctrl+C de dung
echo.
%PYTHON% app.py
pause
