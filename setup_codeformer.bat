@echo off
chcp 65001 >nul
echo ===============================================
echo  Setup CodeFormer - Face Enhancement cao cap
echo ===============================================
echo.
echo CodeFormer (NIPS 2022) tu nhien hon GFPGAN,
echo it plastic look hon, ket qua chuyen nghiep hon.
echo.

call venv_gpu\Scripts\activate.bat

echo [1/4] Cai basicsr + facexlib (co the mat 2-3 phut)...
pip install basicsr facexlib --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Cai basicsr that bai!
    pause
    exit /b 1
)

echo [2/4] Cai CodeFormer package...
pip install git+https://github.com/sczhou/CodeFormer.git --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Git install that bai, thu cach khac...
    pip install "codeformer-pytorch" --quiet
)

echo [3/4] Download model CodeFormer (~375MB)...
python -c "from codeformer_enhance import download_codeformer_model; download_codeformer_model()"
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Tu dong download that bai. Download thu cong:
    echo URL: https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth
    echo Dat file vao: models\codeformer\codeformer.pth
)

echo [4/4] Kiem tra CodeFormer...
python -c "from codeformer_enhance import is_codeformer_available; ok=is_codeformer_available(); print('[OK] CodeFormer san sang!' if ok else '[WARN] Chua san sang - kiem tra lai')"

echo.
echo ===============================================
echo  Hoan thanh! Restart server de ap dung.
echo ===============================================
pause
