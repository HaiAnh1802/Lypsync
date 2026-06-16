@echo off
echo ====================================
echo   LipSync App - Setup Script
echo ====================================
echo.

REM === BUOC 1: Kiem tra Python ===
echo [1/6] Kiem tra Python...
python --version
if errorlevel 1 (
    echo LOI: Chua cai Python! Vao https://python.org de cai
    pause
    exit /b 1
)
echo OK: Python da co san
echo.

REM === BUOC 2: Cai FFmpeg ===
echo [2/6] Cai FFmpeg qua winget...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo Dang cai FFmpeg...
    winget install --id Gyan.FFmpeg -e --silent
    echo OK: FFmpeg da cai xong
) else (
    echo OK: FFmpeg da co san
)
echo.

REM === BUOC 3: Cai Python packages ===
echo [3/6] Cai Python packages...
pip install -r requirements.txt
echo OK: Packages da cai xong
echo.

REM === BUOC 4: Clone Wav2Lip ===
echo [4/6] Download Wav2Lip...
if not exist "wav2lip" (
    git clone https://github.com/Rudrabha/Wav2Lip.git wav2lip
    echo OK: Wav2Lip da clone
) else (
    echo OK: Wav2Lip da co san
)
echo.

REM === BUOC 5: Download model weights ===
echo [5/6] Download Wav2Lip model weights (~400MB)...
if not exist "wav2lip\checkpoints\wav2lip_gan.pth" (
    mkdir wav2lip\checkpoints 2>nul
    echo Dang download model...
    python -c "import requests; r = requests.get('https://iiitaphyd-my.sharepoint.com/personal/radrabha_m_research_iiit_ac_in/_layouts/15/download.aspx?share=EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z65UdEvpCh-MIYNw', stream=True); open('wav2lip/checkpoints/wav2lip_gan.pth', 'wb').write(r.content)"
    echo OK: Model weights da download
) else (
    echo OK: Model weights da co san
)
echo.

REM === BUOC 6: Tao thu muc uploads/outputs ===
echo [6/6] Tao thu muc luu tru...
mkdir uploads 2>nul
mkdir outputs 2>nul
mkdir temp 2>nul
mkdir static 2>nul
echo OK: Thu muc da tao
echo.

echo ====================================
echo   Setup hoan tat! 
echo   Chay: run.bat de khoi dong app
echo ====================================
pause
