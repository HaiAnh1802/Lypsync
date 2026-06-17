@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   MuseTalk Setup Script
echo ============================================================
echo.

set "ROOT=%~dp0"
set "MT_DIR=%ROOT%musetalk"
set "VENV=%ROOT%venv_musetalk"

echo [1/5] Clone MuseTalk repo...
if exist "%MT_DIR%\.git" (
    echo     Already cloned, skipping.
) else (
    git clone https://github.com/TMElyralab/MuseTalk.git "%MT_DIR%"
    if errorlevel 1 (
        echo [ERROR] Clone failed. Check internet/git.
        pause & exit /b 1
    )
)

echo.
echo [2/5] Creating virtual environment venv_musetalk...
if exist "%VENV%\Scripts\python.exe" (
    echo     Already exists, skipping.
) else (
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] venv creation failed.
        pause & exit /b 1
    )
)

echo.
echo [3/5] Installing PyTorch and dependencies...

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo     Installing PyTorch CUDA 12.1...
"%VENV%\Scripts\pip.exe" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet

echo     Installing core dependencies...
"%VENV%\Scripts\pip.exe" install diffusers==0.30.2 accelerate==0.28.0 transformers==4.39.2 huggingface_hub>=0.23.0 --quiet
"%VENV%\Scripts\pip.exe" install opencv-python soundfile librosa einops omegaconf tqdm numpy pillow scipy --quiet
"%VENV%\Scripts\pip.exe" install openai-whisper --quiet

echo     Installing mmcv (for DWPose face detection)...
"%VENV%\Scripts\pip.exe" install mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.1/index.html --quiet
if errorlevel 1 (
    echo     mmcv cu121 failed, trying CPU version...
    "%VENV%\Scripts\pip.exe" install mmcv --quiet
)
"%VENV%\Scripts\pip.exe" install mmdet mmpose --quiet

echo.
echo [4/5] Downloading MuseTalk models (~1.5GB)...
echo     This may take 5-10 minutes...

"%VENV%\Scripts\python.exe" "%ROOT%download_musetalk_models.py"
if errorlevel 1 (
    echo [WARN] Auto-download failed.
    echo        Run manually: huggingface-cli download TMElyralab/MuseTalk --local-dir musetalk/
)

echo.
echo [5/5] Verifying installation...
"%VENV%\Scripts\python.exe" -c "import torch; print('PyTorch:', torch.__version__, '| CUDA:', torch.cuda.is_available())"
"%VENV%\Scripts\python.exe" -c "import diffusers; print('Diffusers OK')"

echo.
echo ============================================================
echo   MuseTalk setup complete!
echo   Restart server (run.bat) to use MuseTalk.
echo ============================================================
pause
