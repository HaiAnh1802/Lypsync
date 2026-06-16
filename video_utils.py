import os
import math
import subprocess
import tempfile
import uuid
from pathlib import Path


def get_duration(file_path: str) -> float:
    """Lấy duration (giây) của video hoặc audio bằng ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def loop_video(video_path: str, target_duration: float, output_dir: str = "temp") -> str:
    """
    Tự động loop video đến khi đủ target_duration giây.
    
    Ví dụ: video 10s, target 60s → loop 6 lần → output 60s
    """
    os.makedirs(output_dir, exist_ok=True)
    
    video_duration = get_duration(video_path)
    loops_needed = math.ceil(target_duration / video_duration)
    
    output_path = os.path.join(output_dir, f"looped_{uuid.uuid4().hex[:8]}.mp4")
    
    if loops_needed <= 1:
        # Không cần loop, trim nếu dài hơn
        # QUAN TRỌNG: -vf fps=25 → chuẩn hóa về 25fps (Wav2Lip train ở 25fps)
        # Nếu video gốc 30/60fps mà không normalize → môi lệch nhạc ~17-20%
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-t", str(target_duration),
            "-vf", "fps=25",           # Normalize FPS về 25 (bắt buộc cho Wav2Lip)
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-an",  # Bỏ audio gốc
            output_path
        ]
    else:
        # Loop video nhiều lần rồi trim đúng duration
        # QUAN TRỌNG: -vf fps=25 → Wav2Lip yêu cầu 25fps để mel chunk sync đúng
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops_needed - 1),
            "-i", video_path,
            "-t", str(target_duration),
            "-vf", "fps=25",           # Normalize FPS về 25 (bắt buộc)
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-an",  # Bỏ audio gốc
            output_path
        ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    
    print(f"✅ Video gốc {video_duration:.1f}s → Loop {loops_needed}x → Output {target_duration:.1f}s")
    return output_path


def merge_audio_video(video_path: str, audio_path: str, output_dir: str = "outputs") -> str:
    """Ghép audio vào video (không re-encode video)."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"final_{uuid.uuid4().hex[:8]}.mp4")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def check_ffmpeg() -> bool:
    """Kiểm tra FFmpeg đã cài chưa."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
