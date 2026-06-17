"""
voice_clone.py – Voice Cloning bằng F5-TTS
============================================
Pipeline:
  1. Chuẩn hoá file audio mẫu (FFmpeg)
  2. F5-TTS infer giọng mẫu → tổng hợp text (chạy qua subprocess)
  3. Xuất dual format: 16kHz mono (Wav2Lip) + 44kHz stereo HQ

Lý do dùng subprocess thay vì import trực tiếp:
  - f5_tts.api khi import sẽ load Whisper + Vocos → cố kết nối HuggingFace → TREO
  - Subprocess chạy riêng với HF_HUB_OFFLINE=1, không ảnh hưởng app chính
"""

import os
import sys
import uuid
import subprocess
from pathlib import Path

# Đường dẫn model local trong project (ưu tiên dùng thay vì HF cache)
_HERE = Path(__file__).parent
LOCAL_MODEL_DIR  = _HERE / "models" / "f5tts"
LOCAL_MODEL_FILE = LOCAL_MODEL_DIR / "model_1250000.safetensors"
LOCAL_VOCAB_FILE = LOCAL_MODEL_DIR / "vocab.txt"
LOCAL_VOCOS_DIR  = LOCAL_MODEL_DIR / "vocos"

# Fix Unicode output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ─────────────────────────────────────────────
# Kiểm tra trạng thái
# ─────────────────────────────────────────────

def is_f5tts_available() -> bool:
    """Kiểm tra F5-TTS đã cài chưa."""
    try:
        import importlib.metadata
        importlib.metadata.version("f5-tts")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False
    except Exception:
        return False


def get_f5tts_status() -> dict:
    available = is_f5tts_available()
    return {
        "available": available,
        "message": "F5-TTS sẵn sàng" if available else "Chưa cài – chạy setup_voiceclone.bat",
        "engine": "f5_tts",
    }


# ─────────────────────────────────────────────
# Core: Clone voice pipeline
# ─────────────────────────────────────────────

def clone_voice_for_pipeline(
    text: str,
    reference_audio: str,
    output_dir: str = "temp",
) -> tuple[str, str]:
    """
    Clone giọng từ file audio mẫu và đọc text theo giọng đó.

    Args:
        text           : Nội dung text cần đọc
        reference_audio: File audio mẫu (WAV/MP3/M4A, 3–30s)
        output_dir     : Thư mục output

    Returns:
        (lipsync_path_16k, hq_path_44k)
    """
    if not is_f5tts_available():
        raise RuntimeError("F5-TTS chưa cài! Hãy chạy setup_voiceclone.bat trước.")

    import torch

    os.makedirs(output_dir, exist_ok=True)
    uid    = uuid.uuid4().hex[:8]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"[VoiceClone] Device: {device.upper()} | Engine: F5-TTS")
    print(f"[VoiceClone] Reference: {Path(reference_audio).name}")

    # ── Step 1: Chuẩn hoá reference audio ────────────────────────────
    ref_norm = os.path.join(output_dir, f"ref_{uid}_norm.wav")
    _normalize_reference(reference_audio, ref_norm)

    # ── Step 2: F5-TTS inference ──────────────────────────────────────
    if LOCAL_MODEL_FILE.exists() and LOCAL_MODEL_FILE.stat().st_size > 1_000_000_000:
        print(f"[VoiceClone] Dung local model: {LOCAL_MODEL_FILE.name}")
    else:
        print("[VoiceClone] Khong co local model -> F5-TTS se tu tai tu HuggingFace...")

    raw_output = os.path.join(output_dir, f"vc_{uid}_raw.wav")
    _run_f5tts(text, ref_norm, raw_output, device)

    # ── Step 3: Tạo 2 định dạng output ───────────────────────────────
    lipsync_path = os.path.join(output_dir, f"vc_{uid}_16k.wav")
    hq_path      = os.path.join(output_dir, f"vc_{uid}_44k.m4a")

    # 16kHz mono WAV cho Wav2Lip
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_output,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        lipsync_path
    ], check=True, capture_output=True)

    # 44100Hz AAC cho video HQ
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_output,
        "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        hq_path
    ], check=True, capture_output=True)

    # Dọn dẹp file trung gian
    for f in [ref_norm, raw_output]:
        if os.path.exists(f):
            os.remove(f)

    duration = _get_duration(lipsync_path)
    print(f"[VoiceClone] Xong: {duration:.1f}s | 16k={lipsync_path} | HQ={hq_path}")
    return lipsync_path, hq_path


# ─────────────────────────────────────────────
# F5-TTS inference qua subprocess
# ─────────────────────────────────────────────

def _run_f5tts(text: str, ref_audio: str, output_wav: str, device: str):
    """Chạy F5-TTS inference qua subprocess riêng biệt.

    Dùng subprocess thay vì import Python API trực tiếp để tránh:
    - Treo khi import: f5_tts.api kéo theo Whisper + Vocos → cố kết nối HuggingFace
    - App crash do CUDA OOM ảnh hưởng main process của uvicorn
    """
    # Tìm Python executable
    python_exe = str(_HERE / "venv_gpu" / "Scripts" / "python.exe")
    if not Path(python_exe).exists():
        python_exe = sys.executable

    has_local  = LOCAL_MODEL_FILE.exists() and LOCAL_MODEL_FILE.stat().st_size > 1_000_000_000
    vocos_path = str(LOCAL_VOCOS_DIR) if LOCAL_VOCOS_DIR.exists() else ""
    ckpt_arg   = str(LOCAL_MODEL_FILE) if has_local else ""
    vocab_arg  = str(LOCAL_VOCAB_FILE) if LOCAL_VOCAB_FILE.exists() else ""

    # Tạo script Python chạy trong subprocess
    script = f"""\
import os, sys
# Bat offline mode truoc khi import de tranh treo
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from f5_tts.api import F5TTS
import soundfile as sf

ckpt  = {repr(ckpt_arg)}
vocab = {repr(vocab_arg)}
vocos = {repr(vocos_path)} or None

print('[F5TTS] Loading model...')
tts = F5TTS(
    ckpt_file=ckpt,
    vocab_file=vocab,
    vocoder_local_path=vocos if vocos else None,
    device={repr(device)},
)
print('[F5TTS] Inference...')
wav, sr, _ = tts.infer(
    ref_file={repr(ref_audio)},
    ref_text=' ',
    gen_text={repr(text)},
    target_rms=0.1,
    cross_fade_duration=0.15,
    speed=1.0,
    remove_silence=True,
)
sf.write({repr(output_wav)}, wav, sr)
print('[F5TTS] Done:', {repr(output_wav)})
"""

    try:
        result = subprocess.run(
            [python_exe, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,  # 5 phút
        )
        # In stdout để dễ debug
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                print(f"[VoiceClone] {line}")
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "F5-TTS subprocess that bai").strip()
            print(f"[VoiceClone] ERROR stderr:\n{err[:1500]}")
            raise RuntimeError(f"F5-TTS loi (exit {result.returncode}): {err[:400]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("F5-TTS timeout sau 5 phut! Text qua dai hoac may qua cham.")
    except FileNotFoundError:
        raise RuntimeError(f"Khong tim thay Python: {python_exe}")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _normalize_reference(src: str, dst: str):
    """Chuẩn hoá reference: 22050Hz mono, tối đa 30s, trim silence."""
    subprocess.run([
        "ffmpeg", "-y", "-i", src,
        "-t", "30",
        "-ar", "22050", "-ac", "1",
        "-c:a", "pcm_s16le",
        "-af", (
            "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-40dB,"
            "areverse,"
            "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-40dB,"
            "areverse"
        ),
        dst
    ], check=True, capture_output=True)


def _get_duration(audio_path: str) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────
# Quick test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    print("=== Voice Clone – Kiểm tra hệ thống ===")
    status = get_f5tts_status()
    print(f"F5-TTS: {'OK' if status['available'] else 'CHUA CAI'} {status['message']}")
    print(f"Local model: {'CO' if LOCAL_MODEL_FILE.exists() else 'CHUA CO'} ({LOCAL_MODEL_FILE})")
    if not status["available"]:
        print("\nChay setup_voiceclone.bat de cai dat")
        sys.exit(1)
    print("\nHe thong san sang!")
