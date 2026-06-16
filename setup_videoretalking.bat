@echo off
chcp 65001 >nul
echo ===============================================
echo  Setup VideoReTalking - Lip Sync Chat Luong Cao
echo ===============================================
echo.

call venv_gpu\Scripts\activate.bat

echo [1/4] Nang cap pip va setuptools (fix loi pkgutil.ImpImporter tren Python 3.12)...
python -m pip install --upgrade pip setuptools wheel
echo Xong!
echo.

echo [2/4] Cai Python dependencies...
pip install dlib face-alignment kornia --quiet
pip install -r video_retalking\requirements.txt --quiet
echo Xong!
echo.

echo [3/4] Download models VideoReTalking (~2GB)...
python download_vrt_models.py
if %ERRORLEVEL% neq 0 (
    echo [FAIL] Download that bai. Kiem tra ket noi mang.
    pause
    exit /b 1
)
echo.

echo [4/4] Kiem tra...
python -c "from videoretalking import is_videoretalking_available; print('[OK] VideoReTalking san sang!' if is_videoretalking_available() else '[WARN] Chua san sang')"

echo.
echo ===============================================
echo  Hoan thanh! Restart server va chon
echo  VideoReTalking trong giao dien.
echo ===============================================
pause
