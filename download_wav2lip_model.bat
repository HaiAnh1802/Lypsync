@echo off
chcp 65001 >nul
echo ===============================================
echo  Download wav2lip.pth - Sync-optimized model
echo ===============================================
echo.
echo Model wav2lip.pth cho sync chinh xac hon wav2lip_gan.pth
echo GFPGAN se xu ly visual sau, nen dung model nay.
echo.

set MODEL_DIR=%~dp0wav2lip\checkpoints
set MODEL_FILE=%MODEL_DIR%\wav2lip.pth
set MODEL_URL=https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip.pth

if exist "%MODEL_FILE%" (
    echo [OK] wav2lip.pth da ton tai: %MODEL_FILE%
    echo Khong can download lai.
    goto :done
)

echo [INFO] Dang download wav2lip.pth (~430MB)...
echo URL: %MODEL_URL%
echo.

:: Thu dung curl truoc (Windows 10+)
where curl >nul 2>&1
if %errorlevel% == 0 (
    curl -L -o "%MODEL_FILE%" "%MODEL_URL%"
    goto :check
)

:: Fallback: dung PowerShell
echo [INFO] Dung PowerShell de download...
powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%MODEL_URL%' -OutFile '%MODEL_FILE%' -UseBasicParsing }"

:check
if exist "%MODEL_FILE%" (
    echo.
    echo [SUCCESS] Download xong: %MODEL_FILE%
    echo He thong se tu dong dung wav2lip.pth khi chay tiep theo.
) else (
    echo.
    echo [ERROR] Download that bai!
    echo Vui long download thu cong tu:
    echo   %MODEL_URL%
    echo Dat file vao: %MODEL_DIR%\wav2lip.pth
)

:done
echo.
pause
