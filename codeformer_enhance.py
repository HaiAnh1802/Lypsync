# -*- coding: utf-8 -*-
# type: ignore
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

"""
CodeFormer Face Enhancement - replaces GFPGAN.
CodeFormer (NIPS 2022) gives more natural face restoration,
less plastic look, controllable via fidelity_weight (0=max enhance, 1=max fidelity).

Uses cloned repo at: codeformer_repo/
Setup: run setup_codeformer.bat to download model weights (~375MB)
"""

import os
import sys
import cv2
import subprocess
import uuid
import numpy as np

# ── Path setup: thêm CodeFormer repo vào Python path ──────────────────────
CODEFORMER_REPO   = os.path.join(os.path.dirname(__file__), "codeformer_repo")
CODEFORMER_MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models", "codeformer")
CODEFORMER_MODEL_PATH = os.path.join(CODEFORMER_MODEL_DIR, "codeformer.pth")
CODEFORMER_MODEL_URL  = "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth"
DETECTION_MODEL_DIR   = os.path.join(os.path.dirname(__file__), "models", "facelib")

if CODEFORMER_REPO not in sys.path and os.path.exists(CODEFORMER_REPO):
    # QUAN TRONG: KHONG insert(0) - se shadow installed basicsr bang codeformer_repo/basicsr/
    # Chi load arch file rieng le qua importlib khi can
    pass

# ── Singleton cache ─────────────────────────────────────────────────────────
_codeformer_net = None
_face_helper    = None


def is_codeformer_available() -> bool:
    """Kiểm tra CodeFormer repo + model + basicsr đã sẵn sàng chưa."""
    if not os.path.exists(CODEFORMER_REPO):
        return False
    if not os.path.exists(CODEFORMER_MODEL_PATH):
        return False
    try:
        import basicsr  # noqa
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper  # noqa
        return True
    except ImportError:
        return False


def download_codeformer_model():
    """Download model weights CodeFormer (~375MB)."""
    os.makedirs(CODEFORMER_MODEL_DIR, exist_ok=True)
    if os.path.exists(CODEFORMER_MODEL_PATH):
        size_mb = os.path.getsize(CODEFORMER_MODEL_PATH) / (1024 * 1024)
        print(f"[CodeFormer] Model đã có: {CODEFORMER_MODEL_PATH} ({size_mb:.0f}MB)")
        return

    print("[CodeFormer] Downloading model (~375MB)...")
    import urllib.request

    def reporthook(count, block_size, total_size):
        if total_size > 0 and count % 500 == 0:
            pct = min(100, count * block_size * 100 // total_size)
            print(f"[CodeFormer] Download... {pct}%")

    urllib.request.urlretrieve(CODEFORMER_MODEL_URL, CODEFORMER_MODEL_PATH, reporthook)
    print(f"[CodeFormer] Model downloaded: {CODEFORMER_MODEL_PATH}")


def _detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            print(f"[CodeFormer] GPU: {name} → CUDA")
            return "cuda"
    except Exception:
        pass
    print("[CodeFormer] No GPU -> CPU mode")
    return "cpu"


def _load_model_and_helper():
    """Load CodeFormer net + FaceRestoreHelper (singleton cache)."""
    global _codeformer_net, _face_helper

    if _codeformer_net is not None and _face_helper is not None:
        return _codeformer_net, _face_helper

    import torch
    from basicsr.utils import img2tensor, tensor2img
    from basicsr.utils.registry import ARCH_REGISTRY
    from facexlib.utils.face_restoration_helper import FaceRestoreHelper

    # Patch: copy arch files từ codeformer_repo vào installed basicsr
    # (CodeFormer cần vqgan_arch.py không có trong basicsr standard)
    import shutil
    import basicsr as _basicsr_pkg
    basicsr_arch_dir = os.path.join(os.path.dirname(_basicsr_pkg.__file__), "archs")
    repo_arch_dir    = os.path.join(CODEFORMER_REPO, "basicsr", "archs")

    for arch_file in ["vqgan_arch.py", "codeformer_arch.py"]:
        src = os.path.join(repo_arch_dir, arch_file)
        dst = os.path.join(basicsr_arch_dir, arch_file)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy(src, dst)
            print(f"[CodeFormer] Patched basicsr: copied {arch_file}")

    # Patch basicsr ARCH_REGISTRY: cho phep re-register (force=True)
    # Khi GFPGAN load truoc, mot so arch da duoc register (ResNetArcFace, v.v.)
    # CodeFormer import cung cac arch nay → crash "already registered"
    # Fix: patch registry.register de dung force=True mac dinh
    import basicsr.utils.registry as _reg_module
    _orig_register = _reg_module.Registry.register.__func__ if hasattr(
        _reg_module.Registry.register, '__func__') else _reg_module.Registry.register

    def _safe_register(self, obj=None, name=None, suffix=None, force=False):
        try:
            return _orig_register(self, obj=obj, name=name, suffix=suffix, force=True)
        except Exception:
            return obj if obj is not None else (lambda x: x)

    _reg_module.Registry.register = _safe_register

    # Import arch (sau khi patch registry)
    try:
        from basicsr.archs.codeformer_arch import CodeFormer as _cf  # noqa
    except (ImportError, Exception):
        import importlib.util
        arch_path = os.path.join(basicsr_arch_dir, "codeformer_arch.py")
        if os.path.exists(arch_path):
            spec = importlib.util.spec_from_file_location("basicsr.archs.codeformer_arch", arch_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

    device = _detect_device()
    print("[CodeFormer] Loading model (first time ~10s, then cached)...")

    net = ARCH_REGISTRY.get("CodeFormer")(
        dim_embd=512,
        codebook_size=1024,
        n_head=8,
        n_layers=9,
        connect_list=["32", "64", "128", "256"],
    ).to(device)

    ckpt = torch.load(CODEFORMER_MODEL_PATH, map_location=device)
    net.load_state_dict(ckpt["params_ema"])
    net.eval()
    _codeformer_net = net

    os.makedirs(DETECTION_MODEL_DIR, exist_ok=True)
    _face_helper = FaceRestoreHelper(
        upscale_factor=1,
        face_size=512,
        crop_ratio=(1, 1),
        det_model="retinaface_resnet50",
        save_ext="png",
        use_parse=True,
        device=device,
        model_rootpath=DETECTION_MODEL_DIR,
    )

    print(f"[CodeFormer] Model loaded on {device.upper()} and cached.")
    return _codeformer_net, _face_helper


def _enhance_frame(frame: np.ndarray, fidelity_weight: float = 0.7) -> np.ndarray:
    """
    Enhance 1 BGR frame bằng CodeFormer.
    fidelity_weight: 0=tối đa enhance, 1=giữ gốc. 0.7 là điểm cân bằng tốt.
    """
    import torch
    from basicsr.utils import img2tensor, tensor2img
    from torchvision.transforms.functional import normalize

    net, face_helper = _load_model_and_helper()
    device = next(net.parameters()).device

    face_helper.clean_all()
    face_helper.read_image(frame)

    num_faces = face_helper.get_face_landmarks_5(
        only_center_face=False,
        resize=640,
        eye_dist_threshold=5,
    )

    if num_faces == 0:
        return frame

    face_helper.align_warp_face()

    for cropped_face in face_helper.cropped_faces:
        face_t = img2tensor(cropped_face / 255.0, bgr2rgb=True, float32=True)
        normalize(face_t, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5), inplace=True)
        face_t = face_t.unsqueeze(0).to(device)

        try:
            with torch.no_grad():
                output = net(face_t, w=fidelity_weight, adain=True)[0]
                restored = tensor2img(output, rgb2bgr=True, min_max=(-1, 1))
        except RuntimeError as e:
            print(f"[CodeFormer] enhance lỗi: {e}")
            restored = cropped_face

        # add_restored_face() nhan TUNG face rieng le (numpy array)
        # KHONG truyen ca list - se gay loi warpAffine "src is not a numpy array"
        face_helper.add_restored_face(restored.astype("uint8"))

    face_helper.get_inverse_affine(None)
    return face_helper.paste_faces_to_input_image()


def enhance_video_codeformer(
    input_path: str,
    output_dir: str = None,
    fidelity_weight: float = 0.7,
    enhance_every_n: int = None,
) -> str:
    """
    Enhance toàn bộ video bằng CodeFormer (streaming mode, ít RAM).

    Args:
        fidelity_weight : 0.0 = đẹp nhất, 1.0 = giữ gốc nhất. 0.7 = cân bằng.
        enhance_every_n : Enhance 1 trong N frame (None = tự chọn theo GPU/CPU)
    """
    if not is_codeformer_available():
        print("[CodeFormer] Không khả dụng → bỏ qua")
        return input_path

    # Tự chọn every_n theo GPU/CPU
    if enhance_every_n is None:
        try:
            import torch
            enhance_every_n = 2 if torch.cuda.is_available() else 3
        except Exception:
            enhance_every_n = 3

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    os.makedirs(output_dir, exist_ok=True)

    uid         = uuid.uuid4().hex[:8]
    output_path = os.path.join(output_dir, f"cf_{uid}.mp4")
    temp_video  = output_path.replace(".mp4", "_tmp.mp4")

    # Đọc thông tin video
    cap    = cv2.VideoCapture(input_path)
    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    print(f"[CodeFormer] Bắt đầu | {total} frames | every_n={enhance_every_n} | fidelity={fidelity_weight}")

    # Preload model
    _load_model_and_helper()

    writer = cv2.VideoWriter(
        temp_video,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps, (width, height)
    )

    cap       = cv2.VideoCapture(input_path)
    frame_idx = 0
    prev_enhanced = None  # cache frame enhanced gần nhất

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % enhance_every_n == 0:
            try:
                out = _enhance_frame(frame, fidelity_weight)
                prev_enhanced = out
            except Exception as e:
                print(f"[CodeFormer] Frame {frame_idx} lỗi: {e}")
                out = frame
        else:
            # Dùng lại frame enhanced gần nhất (temporal coherence)
            out = prev_enhanced if prev_enhanced is not None else frame

        writer.write(out)
        frame_idx += 1

        if frame_idx % 100 == 0:
            pct = int(frame_idx * 100 / total) if total > 0 else 0
            print(f"[CodeFormer]  {frame_idx}/{total} ({pct}%)...")

    cap.release()
    writer.release()

    # Ghép audio gốc + encode H.264
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_video,
        "-i", input_path,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(temp_video)

    print(f"[CodeFormer] ✓ Xong: {output_path}")
    return output_path
