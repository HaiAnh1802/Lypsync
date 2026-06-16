import os
import uuid
import wave
import asyncio
import subprocess
from pathlib import Path
from gtts import gTTS


def text_to_audio(text: str, lang: str = "vi", output_dir: str = "temp") -> tuple[str, float]:
    """
    Chuyển text tiếng Việt thành audio MP3.
    
    Returns:
        (audio_path, duration_seconds)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    audio_filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
    audio_path = os.path.join(output_dir, audio_filename)
    
    # Tạo audio MP3 bằng gTTS
    mp3_path = audio_path.replace(".wav", ".mp3")
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(mp3_path)
    
    # Convert MP3 → WAV (Wav2Lip cần WAV)
    cmd = [
        "ffmpeg", "-y",
        "-i", mp3_path,
        "-ar", "16000",      # Sample rate 16kHz (Wav2Lip yêu cầu)
        "-ac", "1",          # Mono
        "-c:a", "pcm_s16le", # PCM format
        audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(mp3_path)  # Xóa file MP3 tạm
    
    # Lấy duration của audio
    duration = get_audio_duration(audio_path)
    
    print(f"[TTS] Xong: {len(text)} ky tu -> {duration:.1f}s audio")
    return audio_path, duration


def get_audio_duration(audio_path: str) -> float:
    """Lấy duration audio bằng ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def estimate_duration(text: str) -> float:
    """
    Ước tính thời lượng đọc text (giây).
    Tiếng Việt đọc khoảng 3-4 ký tự/giây (150-180 từ/phút).
    """
    words = len(text.split())
    # Tốc độ đọc trung bình: 160 từ/phút = 2.67 từ/giây
    estimated_seconds = words / 2.67
    return round(estimated_seconds, 1)


# ─────────────────────────────────────────────
# Gemini TTS – dùng độc lập (không cần Wav2Lip)
# ─────────────────────────────────────────────

def gemini_tts_direct(
    text: str,
    api_key: str,
    voice: str = "Kore",
    output_dir: str = "temp",
    for_lipsync: bool = False,
) -> str:
    """
    Tạo file audio WAV từ text bằng Gemini 2.5 Flash TTS API.

    Args:
        for_lipsync: Nếu True → xuất 16kHz mono (Wav2Lip yêu cầu).
                     Nếu False (mặc định) → xuất 44100Hz stereo (phát trên browser).

    Returns:
        Đường dẫn file WAV đã convert.
    """
    from google import genai
    from google.genai import types

    os.makedirs(output_dir, exist_ok=True)
    mode_label = "lipsync 16kHz mono" if for_lipsync else "browser 44100Hz stereo"
    print(f"[Gemini TTS] Đang tạo giọng '{voice}' ({mode_label}) cho {len(text)} ký tự...")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice
                    )
                )
            ),
        ),
    )

    # Raw PCM 16-bit 24kHz mono từ Gemini
    audio_data = response.candidates[0].content.parts[0].inline_data.data

    uid = uuid.uuid4().hex[:8]
    raw_path   = os.path.join(output_dir, f"gemini_{uid}_raw.wav")
    final_path = os.path.join(output_dir, f"gemini_{uid}.wav")

    # Lưu PCM raw → WAV 24kHz
    _save_pcm_as_wav(audio_data, raw_path, sample_rate=24000)

    if for_lipsync:
        # 16kHz mono – đúng spec của Wav2Lip, không cần resample nội bộ
        cmd = [
            "ffmpeg", "-y",
            "-i", raw_path,
            "-ar", "16000",       # 16kHz – Wav2Lip yêu cầu
            "-ac", "1",           # Mono
            "-c:a", "pcm_s16le",  # PCM 16-bit
            final_path
        ]
    else:
        # 44100Hz stereo – phát được trên browser
        cmd = [
            "ffmpeg", "-y",
            "-i", raw_path,
            "-ar", "44100",
            "-ac", "2",
            "-c:a", "pcm_s16le",
            final_path
        ]

    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(raw_path)

    duration = get_audio_duration(final_path)
    print(f"[Gemini TTS] Xong: {duration:.1f}s ({mode_label}) → {final_path}")
    return final_path


def convert_for_lipsync(audio_path: str, output_dir: str = "temp") -> str:
    """
    Convert bất kỳ file audio nào sang 16kHz mono PCM WAV cho Wav2Lip.
    Dùng khi audio đã có sẵn (gTTS, upload, v.v.) nhưng cần chuẩn hóa.

    Returns:
        Đường dẫn file WAV 16kHz mono mới.
    """
    os.makedirs(output_dir, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    out_path = os.path.join(output_dir, f"lipsync_audio_{uid}.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        out_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[TTS] Converted → 16kHz mono: {out_path}")
    return out_path


def gemini_tts_for_pipeline(
    text: str,
    api_key: str,
    voice: str = "Kore",
    output_dir: str = "temp",
) -> tuple[str, str]:
    """
    Tạo audio từ Gemini TTS, xuất 2 file trong 1 lần gọi API:
      - lipsync_path : 16kHz mono PCM WAV  → Wav2Lip inference
      - hq_path      : 44100Hz stereo AAC  → mux vào video output cuối

    Returns:
        (lipsync_path_16k, hq_path_44k)
    """
    from google import genai
    from google.genai import types

    os.makedirs(output_dir, exist_ok=True)
    print(f"[Gemini TTS] Tạo giọng '{voice}' (dual-output) cho {len(text)} ký tự...")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )

    # Raw PCM 16-bit 24kHz mono từ Gemini
    audio_data = response.candidates[0].content.parts[0].inline_data.data

    uid = uuid.uuid4().hex[:8]
    raw_path     = os.path.join(output_dir, f"gemini_{uid}_raw.wav")
    lipsync_path = os.path.join(output_dir, f"gemini_{uid}_16k.wav")
    hq_path      = os.path.join(output_dir, f"gemini_{uid}_44k.m4a")

    # Lưu PCM raw → WAV 24kHz
    _save_pcm_as_wav(audio_data, raw_path, sample_rate=24000)

    # Convert → 16kHz mono (cho Wav2Lip) với SoXR high-quality resampler
    # QUAN TRỌNG: KHÔNG dùng loudnorm → loudnorm thay đổi timing phase → mel desync
    # Chỉ resample thuần tú y giữ timing chính xác tuyệt đối
    # Thêm bandpass: highpass 80Hz (bỏ rumble) + lowpass 8000Hz (giữ dải giọng nói)
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-af", "highpass=f=80,lowpass=f=8000,aresample=resampler=soxr:precision=28",
        lipsync_path
    ], check=True, capture_output=True)

    # Convert → 44100Hz stereo AAC (cho video output cuối)
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        hq_path
    ], check=True, capture_output=True)

    os.remove(raw_path)

    duration = get_audio_duration(lipsync_path)
    print(f"[Gemini TTS] Xong: {duration:.1f}s | 16k={lipsync_path} | HQ={hq_path}")
    return lipsync_path, hq_path


def _save_pcm_as_wav(pcm_data: bytes, output_path: str, sample_rate: int = 24000):
    """Ghi raw PCM 16-bit bytes thành file WAV hợp lệ."""
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)        # Mono
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)


# ───────────────────────────────────────────────
# Edge TTS – Microsoft, free, không giới hạn, giọ́ng Việt rất tốt
# ───────────────────────────────────────────────

EDGE_VOICES = {
    "vi-VN-HoaiMyNeural":  "Hoài My – Nữ, rõ ràng, tự nhiên",
    "vi-VN-NamMinhNeural": "Nam Minh – Nam, ấm, chuyên nghiệp",
}


def edge_tts_for_pipeline(
    text: str,
    voice: str = "vi-VN-HoaiMyNeural",
    output_dir: str = "temp",
) -> tuple[str, str]:
    """
    Tạo audio từ Microsoft Edge TTS (free, không cần API key).
    Xuất 2 file:
      - lipsync_path : 16kHz mono PCM WAV  → Wav2Lip
      - hq_path      : 44100Hz stereo AAC  → video output

    Returns:
        (lipsync_path_16k, hq_path_44k)
    """
    import edge_tts

    os.makedirs(output_dir, exist_ok=True)
    uid      = uuid.uuid4().hex[:8]
    mp3_path     = os.path.join(output_dir, f"edge_{uid}_raw.mp3")
    lipsync_path = os.path.join(output_dir, f"edge_{uid}_16k.wav")
    hq_path      = os.path.join(output_dir, f"edge_{uid}_44k.m4a")

    print(f"[Edge TTS] Tao giong '{voice}' cho {len(text)} ky tu...")

    # Chạy async communicate() trong sync context
    async def _run():
        comm = edge_tts.Communicate(text, voice)
        await comm.save(mp3_path)

    asyncio.run(_run())

    # Convert MP3 → 16kHz mono WAV (Wav2Lip)
    # QUAN TRỌNG: KHÔNG dùng loudnorm → thay đổi timing → môi lệch chữ
    # Thêm bandpass: highpass 80Hz + lowpass 8000Hz → khử tiếng ồn, giữ dải giọng nói
    subprocess.run([
        "ffmpeg", "-y", "-i", mp3_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-af", "highpass=f=80,lowpass=f=8000,aresample=resampler=soxr:precision=28",
        lipsync_path
    ], check=True, capture_output=True)

    # Convert MP3 → 44100Hz stereo AAC (video output HQ)
    subprocess.run([
        "ffmpeg", "-y", "-i", mp3_path,
        "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        hq_path
    ], check=True, capture_output=True)

    os.remove(mp3_path)

    duration = get_audio_duration(lipsync_path)
    print(f"[Edge TTS] Xong: {duration:.1f}s | 16k={lipsync_path} | HQ={hq_path}")
    return lipsync_path, hq_path
