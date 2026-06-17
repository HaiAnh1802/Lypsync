"""
musetalk_wrapper.py
Wrapper cho MuseTalk lip sync engine.
Chay MuseTalk qua subprocess dung venv_musetalk va YAML inference config.
"""

import os
import sys
import uuid
import subprocess
import shutil
import hashlib
from pathlib import Path

import yaml

# Thu muc goc project
BASE_DIR     = Path(__file__).parent.resolve()
MT_DIR       = BASE_DIR / "musetalk"
MT_VENV      = BASE_DIR / "venv_musetalk"
MT_PYTHON    = MT_VENV / "Scripts" / "python.exe"
MT_INFERENCE = MT_DIR / "scripts" / "realtime_inference.py"
MT_MODELS    = MT_DIR / "models"


def is_musetalk_available() -> bool:
    """Kiem tra MuseTalk da duoc cai chua."""
    if not MT_DIR.exists():
        return False
    if not MT_PYTHON.exists():
        return False
    if not MT_INFERENCE.exists():
        return False
    # Kiem tra model chinh
    musetalk_model = MT_MODELS / "musetalk" / "pytorch_model.bin"
    return musetalk_model.exists()


def _video_hash(video_path: str) -> str:
    """Tao hash ngan tu duong dan video de dung lam avatar_id."""
    return hashlib.md5(str(video_path).encode()).hexdigest()[:12]


def generate_musetalk(
    video_path: str,
    audio_path: str,
    output_dir: str = "outputs",
    batch_size: int = 8,
    use_float16: bool = True,
    bbox_shift: int = -7,      # -7 canh bbox len cao hon, bat mieng tot hon
    extra_margin: int = 0,     # 0 = cat sat mat, bot mo chin
    parsing_mode: str = "jaw", # jaw = blend vung ham tu nhien
) -> str:
    """
    Chay MuseTalk lip sync.

    Args:
        video_path  : Duong dan video goc (da loop)
        audio_path  : Duong dan audio (WAV)
        output_dir  : Thu muc xuat video
        batch_size  : Batch size inference
        use_float16 : (khong dung truc tiep, MuseTalk tu dung fp16)
        bbox_shift  : Dich chuyen bbox khuon mat

    Returns:
        Duong dan file video output
    """
    if not is_musetalk_available():
        raise RuntimeError(
            "MuseTalk chua duoc cai dat. Chay setup_musetalk.bat truoc."
        )

    video_path = str(Path(video_path).resolve())
    audio_path = str(Path(audio_path).resolve())
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    # --- Avatar ID dua tren hash video (tai su dung preprocessing) ---
    avatar_id  = "av_" + _video_hash(video_path)
    audio_key  = "audio_0"
    # MuseTalk names output after audio_key, NOT output_vid_name
    output_filename = audio_key + ".mp4"

    # --- Kiem tra avatar da ton tai chua ---
    avatar_dir  = MT_DIR / "results" / "v15" / "avatars" / avatar_id
    preparation = not avatar_dir.exists()  # False neu da co

    # --- Tao temp YAML config ---
    temp_yaml = MT_DIR / f"_temp_config_{uuid.uuid4().hex[:6]}.yaml"
    config = {
        avatar_id: {
            "preparation": preparation,
            "bbox_shift": bbox_shift,
            "video_path": video_path.replace("\\", "/"),
            "audio_clips": {
                audio_key: audio_path.replace("\\", "/"),
            },
        }
    }
    with open(temp_yaml, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # --- Expected output path (MuseTalk names it after audio_key) ---
    expected_output = avatar_dir / "vid_output" / output_filename

    # --- Build command ---
    cmd = [
        str(MT_PYTHON),
        str(MT_INFERENCE),
        "--version",        "v15",
        "--vae_type",       "sd-vae-ft-mse",
        "--unet_config",    str(MT_MODELS / "musetalk" / "musetalk.json"),
        "--unet_model_path",str(MT_MODELS / "musetalk" / "pytorch_model.bin"),
        # MuseTalk chi tuong thich voi whisper-tiny (384 dim)
        # Whisper-base tao ra 512 dim -> khong hop le voi UNet
        "--whisper_dir",    str(MT_MODELS / "whisper"),
        "--inference_config", str(temp_yaml),
        "--batch_size",     str(batch_size),
        "--bbox_shift",     str(bbox_shift),
        "--extra_margin",   str(extra_margin),
        "--parsing_mode",   parsing_mode,
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(MT_DIR)
    env["CUDA_VISIBLE_DEVICES"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"[MuseTalk] Starting inference | batch:{batch_size} | avatar:{avatar_id}")
    print(f"[MuseTalk] preparation={preparation} | video={video_path}")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(MT_DIR),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        # Xoa temp YAML du thanh cong hay that bai
        if temp_yaml.exists():
            temp_yaml.unlink()

    if proc.returncode != 0:
        raise RuntimeError(f"MuseTalk that bai (exit {proc.returncode})")

    # --- Tim output va copy sang output_dir ---
    if expected_output.exists():
        job_id = uuid.uuid4().hex[:8]
        final_output = os.path.join(output_dir, f"musetalk_{job_id}.mp4")

        # --- Sharpen lips via ffmpeg unsharp mask ---
        temp_copy = final_output.replace(".mp4", "_raw.mp4")
        shutil.copy2(str(expected_output), temp_copy)
        try:
            sharp_cmd = [
                "ffmpeg", "-y",
                "-i", temp_copy,
                "-vf", "unsharp=luma_msize_x=7:luma_msize_y=7:luma_amount=2.0:chroma_msize_x=3:chroma_msize_y=3:chroma_amount=0.5",
                "-c:v", "libx264", "-crf", "17", "-preset", "fast",
                "-c:a", "copy",
                final_output
            ]
            subprocess.run(sharp_cmd, check=True, capture_output=True)
            os.remove(temp_copy)
            print(f"[MuseTalk] Sharpened: {final_output}")
        except Exception as e:
            print(f"[MuseTalk] Sharpen failed ({e}), using raw output")
            shutil.move(temp_copy, final_output)

        return final_output

    raise RuntimeError(
        f"MuseTalk khong tao duoc output tai {expected_output}. "
        "Kiem tra log phia tren."
    )
