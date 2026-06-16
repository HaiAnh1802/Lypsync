# -*- coding: utf-8 -*-
"""
VideoReTalking wrapper - alternative to Wav2Lip.
VideoReTalking (SIGGRAPH Asia 2022) animates the full face region for
more natural lip sync, with better temporal consistency.

Repo: https://github.com/OpenTalker/video-retalking
Setup: run setup_videoretalking.bat to download models (~2GB)

Inference command (same API as Wav2Lip):
    python inference.py --face video.mp4 --audio audio.wav --outfile output.mp4
"""

import os
import sys
import subprocess
import uuid
from pathlib import Path

VRT_DIR        = os.path.join(os.path.dirname(__file__), "video_retalking")
VRT_CHECKPOINTS = os.path.join(VRT_DIR, "checkpoints")
VRT_INFERENCE  = os.path.join(VRT_DIR, "inference.py")

# Key model files to verify installation
VRT_KEY_MODELS = [
    "30_net_gen.pth",
    "face3d_pretrain_epoch_20.pth",
    "GFPGANv1.3.pth",
]


def is_videoretalking_available() -> bool:
    """Check if VideoReTalking repo is cloned and ready."""
    return os.path.exists(VRT_INFERENCE) and os.path.exists(VRT_DIR)



def detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024**2)
            print(f"[VRT] GPU: {name} ({vram}MB VRAM)")
            return "cuda"
    except Exception:
        pass
    print("[VRT] No GPU -> CPU mode")
    return "cpu"


def generate_vrt(
    video_path: str,
    audio_path: str,
    output_dir: str = "outputs",
    hq_audio_path: str = None,
) -> str:
    """
    Run VideoReTalking lip sync.

    Args:
        video_path     : Input video (already looped to match audio duration)
        audio_path     : WAV audio (16kHz mono, as required by Wav2Lip/VRT)
        output_dir     : Output directory
        hq_audio_path  : Optional HQ audio to replace after VRT (44kHz stereo)

    Returns:
        Path to output video
    """
    if not is_videoretalking_available():
        raise RuntimeError(
            "VideoReTalking chua duoc cai! Chay setup_videoretalking.bat truoc."
        )

    os.makedirs(output_dir, exist_ok=True)
    uid         = uuid.uuid4().hex[:8]
    output_path = os.path.join(os.path.abspath(output_dir), f"vrt_{uid}.mp4")

    device = detect_device()

    # Install VRT requirements if not done yet
    _ensure_vrt_deps()

    cmd = [
        sys.executable,
        VRT_INFERENCE,
        "--face",    os.path.abspath(video_path),
        "--audio",   os.path.abspath(audio_path),
        "--outfile", output_path,
    ]

    # For 4GB VRAM (GTX 1050 Ti): LNet_batch_size=1 required - ENet needs ~1GB/item
    if device == "cuda":
        cmd += ["--LNet_batch_size", "1"]
    else:
        cmd += ["--LNet_batch_size", "1"]

    print(f"[VRT] Running VideoReTalking ({device.upper()})...")
    print(f"[VRT] Command: {' '.join(cmd[-4:])}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if device == "cuda":
        env["CUDA_VISIBLE_DEVICES"] = "0"
        # expandable_segments reduces fragmentation for 4GB cards
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:128"

    proc = subprocess.run(
        cmd,
        capture_output=False,   # show stdout/stderr live
        text=True,
        cwd=VRT_DIR,
        env=env,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"VideoReTalking that bai (exit {proc.returncode})")

    if not os.path.exists(output_path):
        raise RuntimeError(f"VideoReTalking khong tao duoc output: {output_path}")

    print(f"[VRT] Done: {output_path}")

    # ── CodeFormer post-processing ───────────────────────────────────────────
    # VRT processes faces at 256x256 internally → output looks blurry.
    # Run CodeFormer to restore sharpness on every frame.
    try:
        from codeformer_enhance import enhance_video_codeformer
        print("[VRT] Running CodeFormer sharpening on output...")
        cf_result = enhance_video_codeformer(
            input_path=output_path,
            output_dir=os.path.dirname(output_path),
            fidelity_weight=0.7,   # 0=max restoration, 1=max identity
            enhance_every_n=1,     # enhance every frame for best quality
        )
        if cf_result and os.path.exists(cf_result) and cf_result != output_path:
            os.remove(output_path)
            output_path = cf_result
            print(f"[VRT] CodeFormer sharpening done: {output_path}")
        else:
            print("[VRT] CodeFormer skipped")
    except Exception as e:
        print(f"[VRT] CodeFormer post-process failed (skipping): {e}")
    # ─────────────────────────────────────────────────────────────────────────


    # Replace audio HQ if provided
    if hq_audio_path and os.path.exists(hq_audio_path):
        hq_output = output_path.replace(".mp4", "_hq.mp4")
        try:
            hq_cmd = [
                "ffmpeg", "-y",
                "-i", output_path,
                "-i", hq_audio_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                hq_output
            ]
            subprocess.run(hq_cmd, check=True, capture_output=True)
            os.remove(output_path)
            output_path = hq_output
            print(f"[VRT] Audio HQ replaced: {output_path}")
        except Exception as e:
            print(f"[VRT] Audio replace failed (skipping): {e}")

    return output_path



def _ensure_vrt_deps():
    """Install VideoReTalking Python dependencies if not already installed."""
    req_file = os.path.join(VRT_DIR, "requirements.txt")
    if not os.path.exists(req_file):
        return

    # Quick check: if basicsr already installed (we installed it for CodeFormer)
    # most VRT deps are already present
    try:
        import dlib  # noqa
        return  # if dlib installed, assume VRT deps are done
    except ImportError:
        pass

    print("[VRT] Installing dependencies (one-time)...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
        check=False
    )
