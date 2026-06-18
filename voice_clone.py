"""
Voice Cloning module dùng viXTTS (Vietnamese XTTS v2 fine-tuned).
Chạy vixtts_runner.py qua subprocess với Python 3.11 (venv_vixtts).
Không ảnh hưởng đến venv_gpu chính (Python 3.12).
"""
import os
import uuid
import subprocess
from pathlib import Path

BASE_DIR       = Path(__file__).parent.resolve()
MODEL_DIR      = BASE_DIR / "models" / "vixtts"
VIXTTS_PYTHON  = BASE_DIR / "venv_vixtts" / "Scripts" / "python.exe"
VIXTTS_RUNNER  = BASE_DIR / "vixtts_runner.py"

SUPPORTED_LANGUAGES = {
    'vi', 'en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr', 'ru',
    'nl', 'cs', 'ar', 'zh-cn', 'hu', 'ko', 'ja', 'hi'
}


def is_xtts_available() -> bool:
    """Kiểm tra viXTTS model và venv_vixtts đã sẵn sàng chưa."""
    required = ["model.pth", "config.json", "vocab.json"]
    model_ok = all((MODEL_DIR / f).exists() for f in required)
    venv_ok  = VIXTTS_PYTHON.exists()
    return model_ok and venv_ok


def _run_vixtts(text: str, speaker_wav: str, language: str, output_path: str):
    """
    Gọi vixtts_runner.py qua subprocess với Python 3.11 (venv_vixtts).
    Raises RuntimeError nếu thất bại.
    """
    if not VIXTTS_PYTHON.exists():
        raise RuntimeError(
            "venv_vixtts chưa được setup!\n"
            "Chạy: setup_vixtts.bat để cài đặt."
        )
    if not (MODEL_DIR / "model.pth").exists():
        raise RuntimeError(
            "viXTTS model chưa download!\n"
            "Chạy: download_xtts_model.bat để download."
        )

    # Fallback ngôn ngữ không hỗ trợ
    if language not in SUPPORTED_LANGUAGES:
        print(f"[viXTTS] WARNING: '{language}' không hỗ trợ. Fallback sang 'vi'.")
        language = 'vi'

    print(f"[viXTTS] Gọi runner (Python 3.11) cho {len(text)} ký tự (lang={language})...")

    result = subprocess.run(
        [
            str(VIXTTS_PYTHON), str(VIXTTS_RUNNER),
            "--text",        text,
            "--speaker_wav", speaker_wav,
            "--language",    language,
            "--output",      output_path,
        ],
        capture_output=False,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )

    if result.returncode != 0:
        raise RuntimeError(f"viXTTS runner thất bại (exit code {result.returncode})")

    if not os.path.exists(output_path):
        raise RuntimeError("viXTTS runner không tạo được file output!")


def xtts_clone_direct(
    text: str,
    speaker_wav: str,
    output_dir: str = "temp",
    language: str = "vi",
) -> str:
    """
    Clone giọng theo mẫu – dùng cho preview (tab Voice Clone).
    Returns: đường dẫn file WAV 44100Hz stereo.
    """
    os.makedirs(output_dir, exist_ok=True)
    uid        = uuid.uuid4().hex[:8]
    raw_path   = os.path.join(output_dir, f"vixtts_{uid}_raw.wav")
    final_path = os.path.join(output_dir, f"vixtts_{uid}.wav")

    _run_vixtts(text, speaker_wav, language, raw_path)

    # Convert → 44100Hz stereo (browser playback)
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        final_path
    ], check=True, capture_output=True)
    os.remove(raw_path)

    print(f"[viXTTS] Preview xong: {final_path}")
    return final_path


def xtts_clone_for_pipeline(
    text: str,
    speaker_wav: str,
    output_dir: str = "temp",
    language: str = "vi",
) -> tuple[str, str]:
    """
    Clone giọng – dùng trong pipeline Lip Sync.
    Returns: (lipsync_16k_path, hq_44k_path)
    """
    os.makedirs(output_dir, exist_ok=True)
    uid          = uuid.uuid4().hex[:8]
    raw_path     = os.path.join(output_dir, f"vixtts_{uid}_raw.wav")
    lipsync_path = os.path.join(output_dir, f"vixtts_{uid}_16k.wav")
    hq_path      = os.path.join(output_dir, f"vixtts_{uid}_44k.m4a")

    _run_vixtts(text, speaker_wav, language, raw_path)

    # Convert → 16kHz mono (Wav2Lip)
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-af", "highpass=f=80,lowpass=f=8000,aresample=resampler=soxr:precision=28",
        lipsync_path
    ], check=True, capture_output=True)

    # Convert → 44100Hz stereo AAC (video output HQ)
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        hq_path
    ], check=True, capture_output=True)

    os.remove(raw_path)

    from tts import get_audio_duration
    duration = get_audio_duration(lipsync_path)
    print(f"[viXTTS] Pipeline xong: {duration:.1f}s | 16k={lipsync_path}")
    return lipsync_path, hq_path
