import os
import sys
import subprocess
import uuid
import psutil
from pathlib import Path
from face_enhance import enhance_video, is_gfpgan_available
from codeformer_enhance import enhance_video_codeformer, is_codeformer_available, download_codeformer_model


WAV2LIP_DIR = os.path.join(os.path.dirname(__file__), "wav2lip")

# ─────────────────────────────────────────────
# Model paths: wav2lip.pth (sync tốt) và wav2lip_gan.pth (visual đẹp)
# Pipeline hiện tại đã có GFPGAN làm đẹp sau → nên dùng wav2lip.pth (sync chính xác hơn)
# ─────────────────────────────────────────────
MODEL_PATH_SYNC = os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip.pth")       # sync tốt
MODEL_PATH_GAN  = os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip_gan.pth")   # visual đẹp


def get_model_path() -> str:
    """
    Chọn model tối ưu:
    - Nếu có wav2lip.pth → dùng (sync chính xác hơn, GFPGAN lo phần visual)
    - Nếu không → fallback wav2lip_gan.pth
    """
    if os.path.exists(MODEL_PATH_SYNC):
        print(f"[LipSync] Model: wav2lip.pth (sync-optimized) ✓")
        return MODEL_PATH_SYNC
    print(f"[LipSync] Model: wav2lip_gan.pth (fallback) – download wav2lip.pth để sync tốt hơn")
    return MODEL_PATH_GAN


def is_wav2lip_available() -> bool:
    has_dir  = os.path.exists(WAV2LIP_DIR)
    has_sync = os.path.exists(MODEL_PATH_SYNC)
    has_gan  = os.path.exists(MODEL_PATH_GAN)
    return has_dir and (has_sync or has_gan)


# ─────────────────────────────────────────────
# Cấu hình giới hạn tài nguyên
# ─────────────────────────────────────────────

MAX_CPU_CORES = max(1, (os.cpu_count() or 4) // 2)
GPU_VRAM_FRACTION = float(os.environ.get("GPU_VRAM_FRACTION", "0.80"))
# GPU 4GB: giữ priority bình thường để không bị OS throttle
PROCESS_PRIORITY = 0  # NORMAL_PRIORITY_CLASS




def detect_device() -> str:
    """Phát hiện GPU hay CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024**2)
            print(f"[LipSync] GPU: {name} ({vram}MB VRAM) → CUDA mode")
            return "cuda"
    except Exception as e:
        print(f"[LipSync] Không load torch: {e}")
    print(f"[LipSync] Không có GPU → CPU mode ({MAX_CPU_CORES} cores)")
    return "cpu"


def generate(
    video_path: str,
    audio_path: str,
    output_dir: str = "outputs",
    use_gfpgan: bool = True,
    hq_audio_path: str = None,
) -> str:
    """
    Lip sync video với audio bằng Wav2Lip, sau đó GFPGAN sharpen mặt.

    Args:
        hq_audio_path: Nếu có, replace audio track trong video output
                       bằng file HQ (44kHz stereo) này thay vì audio 16kHz
                       mà Wav2Lip đã mux vào. Giúp video output có âm thanh
                       chất lượng cao hơn.
    """
    os.makedirs(output_dir, exist_ok=True)

    uid = uuid.uuid4().hex[:8]
    output_path = os.path.join(os.path.abspath(output_dir), f"lipsync_{uid}.mp4")

    if not is_wav2lip_available():
        raise RuntimeError("Wav2Lip chua duoc cai! Chay setup.bat truoc.")

    device = detect_device()

    env = os.environ.copy()
    env["OMP_NUM_THREADS"]      = str(MAX_CPU_CORES)
    env["MKL_NUM_THREADS"]      = str(MAX_CPU_CORES)
    env["OPENBLAS_NUM_THREADS"] = str(MAX_CPU_CORES)
    env["NUMEXPR_NUM_THREADS"]  = str(MAX_CPU_CORES)
    env["TORCH_NUM_THREADS"]    = str(MAX_CPU_CORES)

    if device == "cuda":
        # GTX 1050 Ti: 4GB VRAM
        # Wav2Lip model chỉ ~50MB → batch lớn không OOM
        # face_det_batch_size 16 → detect 16 frame/lần, nhanh 4x hơn
        # wav2lip_batch_size 128 → 4GB VRAM dư sức, đó là default của paper gốc
        env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:256"
        env["CUDA_VISIBLE_DEVICES"]     = "0"   # force GPU 0

        cmd = [
            sys.executable,
            os.path.join(WAV2LIP_DIR, "inference.py"),
            "--checkpoint_path", get_model_path(),  # tự chọn wav2lip.pth (sync) hoặc GAN (fallback)
            "--face",    os.path.abspath(video_path),
            "--audio",   os.path.abspath(audio_path),
            "--outfile",  output_path,
            "--resize_factor",      "1",    # Full resolution
            "--face_det_batch_size", "32",  # 32 frame/batch face detect
            "--wav2lip_batch_size",  "128", # 128: default paper gốc, an toàn với 4GB VRAM
            "--nosmooth",                    # Tắt smooth T=2 → loại bỏ lag 2 frame (~80ms)
                                             # GFPGAN xử lý visual artifact sau, không cần smooth box
            "--pads", "0", "20", "0", "0",  # Tăng pad dưới lên 20px: bao phủ toàn bộ cằm/môi
        ]
        print(f"[LipSync] GPU mode | face_batch:32 | wav2lip_batch:128 | smooth:T=2")

    else:
        cmd = [
            sys.executable,
            os.path.join(WAV2LIP_DIR, "inference.py"),
            "--checkpoint_path", get_model_path(),  # tự chọn wav2lip.pth (sync) hoặc GAN (fallback)
            "--face",    os.path.abspath(video_path),
            "--audio",   os.path.abspath(audio_path),
            "--outfile",  output_path,
            "--resize_factor",      "1",
            "--face_det_batch_size", "4",
            "--wav2lip_batch_size",  "8",
            "--nosmooth",                    # Tắt smooth → loại bỏ lag 2 frame (~80ms)
            "--pads", "0", "20", "0", "0",  # Tăng pad dưới lên 20px
        ]
        print(f"[LipSync] CPU mode | face_batch:4 | wav2lip_batch:8 | nosmooth:ON | Cores:{MAX_CPU_CORES}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=WAV2LIP_DIR,
        env=env,
        creationflags=PROCESS_PRIORITY,
    )

    try:
        p = psutil.Process(proc.pid)
        limited = list(range(os.cpu_count() or 4))[:MAX_CPU_CORES]
        p.cpu_affinity(limited)
        print(f"[LipSync] CPU affinity: {limited}")
    except Exception as e:
        print(f"[LipSync] Affinity: {e}")

    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        print(f"Loi Wav2Lip:\n{stderr}")
        raise RuntimeError(f"Wav2Lip that bai: {stderr[-500:]}")

    print(f"[LipSync] Xong ({device.upper()}): {output_path}")

    # ── Replace audio HQ (nếu có) ────────────────────────────────────
    # Wav2Lip mux audio 16kHz mono vào video → thay bằng bản 44kHz stereo
    if hq_audio_path and os.path.exists(hq_audio_path):
        hq_output = output_path.replace(".mp4", "_hq.mp4")
        try:
            hq_cmd = [
                "ffmpeg", "-y",
                "-i", output_path,        # video từ Wav2Lip (video OK, audio 16k)
                "-i", hq_audio_path,       # audio HQ 44kHz stereo
                "-c:v", "copy",            # copy video stream, không re-encode
                "-c:a", "aac",             # encode audio AAC
                "-b:a", "192k",
                "-map", "0:v:0",           # lấy video từ stream 0
                "-map", "1:a:0",           # lấy audio từ stream 1 (HQ)
                "-shortest",               # cắt theo track ngắn hơn
                hq_output
            ]
            subprocess.run(hq_cmd, check=True, capture_output=True)
            os.remove(output_path)         # xóa bản 16kHz cũ
            output_path = hq_output
            print(f"[LipSync] Audio HQ replaced: {output_path}")
        except Exception as e:
            print(f"[LipSync] Không replace được audio HQ (bỏ qua): {e}")

    # ── Face Enhancement: CodeFormer (tốt nhất) → GFPGAN (fallback) → bỏ qua ───────────
    if use_gfpgan:
        if is_codeformer_available():
            print("[LipSync] CodeFormer: bắt đầu enhance mặt (chất lượng cao)...")
            try:
                enhanced = enhance_video_codeformer(output_path, output_dir=output_dir)
                if enhanced != output_path:
                    os.remove(output_path)
                    print(f"[LipSync] CodeFormer xong: {enhanced}")
                    return enhanced
            except Exception as e:
                print(f"[LipSync] CodeFormer lỗi (thử GFPGAN): {e}")
                # Fallback sang GFPGAN
                if is_gfpgan_available():
                    try:
                        enhanced = enhance_video(output_path, output_dir=output_dir)
                        if enhanced != output_path:
                            os.remove(output_path)
                            return enhanced
                    except Exception as e2:
                        print(f"[LipSync] GFPGAN fallback lỗi: {e2}")

        elif is_gfpgan_available():
            print("[LipSync] GFPGAN: sharpen mặt (CodeFormer chưa cài)...")
            print("         Chạy setup_codeformer.bat để dùng CodeFormer (tốt hơn)")
            try:
                enhanced = enhance_video(output_path, output_dir=output_dir)
                if enhanced != output_path:
                    os.remove(output_path)
                    print(f"[LipSync] GFPGAN xong: {enhanced}")
                    return enhanced
            except Exception as e:
                print(f"[LipSync] GFPGAN lỗi (bỏ qua): {e}")

        else:
            print("[LipSync] Không có face enhancer nào → bỏ qua enhancement")
            print("         Chạy setup_codeformer.bat hoặc setup.bat")

    return output_path
