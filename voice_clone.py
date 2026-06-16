"""
voice_clone.py – Voice Cloning bằng F5-TTS
============================================
Pipeline:
  1. Chuẩn hoá file audio mẫu (FFmpeg)
  2. F5-TTS infer giọng mẫu → tổng hợp text
  3. Xuất dual format: 16kHz mono (Wav2Lip) + 44kHz stereo HQ

Yêu cầu:
    pip install f5-tts
    Model ~1.5GB tự download lần đầu chạy
"""

import os
import uuid
import subprocess
from pathlib import Path


# ─────────────────────────────────────────────
# Kiểm tra trạng thái
# ─────────────────────────────────────────────

def is_f5tts_available() -> bool:
    """Kiểm tra F5-TTS đã cài chưa."""
    try:
        import importlib.util
        return importlib.util.find_spec("f5_tts") is not None
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
    print(f"[VoiceClone] Đang clone giọng (lần đầu sẽ tải model ~1.5GB)...")
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
# F5-TTS inference
# ─────────────────────────────────────────────

def _run_f5tts(text: str, ref_audio: str, output_wav: str, device: str):
    """Chạy F5-TTS inference."""
    try:
        from f5_tts.api import F5TTS
        tts = F5TTS(device=device)
        wav, sr, _ = tts.infer(
            ref_file=ref_audio,
            ref_text="",        # để F5-TTS tự nhận dạng
            gen_text=text,
            target_rms=0.1,
            cross_fade_duration=0.15,
            speed=1.0,
            remove_silence=True,
        )
        import soundfile as sf
        sf.write(output_wav, wav, sr)
    except ImportError:
        raise RuntimeError("F5-TTS chưa cài! Chạy setup_voiceclone.bat trước.")


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
    print(f"F5-TTS: {'✅' if status['available'] else '❌'} {status['message']}")
    if not status["available"]:
        print("\nChạy setup_voiceclone.bat để cài đặt")
        sys.exit(1)
    print("\n✅ Hệ thống sẵn sàng!")
