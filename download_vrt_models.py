"""
Download VideoReTalking model checkpoints.
- Most models: GitHub releases v0.0.1
- GPEN-BFR-512.pth + RetinaFace-R50.pth: Google Drive (via gdown)
"""
import urllib.request
import os
import sys
import subprocess

CKPT = os.path.join(os.path.dirname(__file__), "video_retalking", "checkpoints")
os.makedirs(CKPT, exist_ok=True)

# Models available on GitHub releases
github_models = [
    ("DNet.pt",                          "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/DNet.pt"),
    ("LNet.pth",                         "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/LNet.pth"),
    ("ENet.pth",                         "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/ENet.pth"),
    ("30_net_gen.pth",                   "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/30_net_gen.pth"),
    ("BFM.zip",                          "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/BFM.zip"),
    ("expression.mat",                   "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/expression.mat"),
    ("face3d_pretrain_epoch_20.pth",     "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/face3d_pretrain_epoch_20.pth"),
    ("GFPGANv1.3.pth",                   "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/GFPGANv1.3.pth"),
    ("ParseNet-latest.pth",              "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/ParseNet-latest.pth"),
    ("shape_predictor_68_face_landmarks.dat",
                                         "https://github.com/OpenTalker/video-retalking/releases/download/v0.0.1/shape_predictor_68_face_landmarks.dat"),
]

# Models only on HuggingFace mirror (camenduru/video-retalking)
# These are NOT on GitHub releases - must use HuggingFace
hf_models = [
    ("GPEN-BFR-512.pth",   "https://huggingface.co/camenduru/video-retalking/resolve/main/GPEN-BFR-512.pth"),
    ("RetinaFace-R50.pth", "https://huggingface.co/camenduru/video-retalking/resolve/main/RetinaFace-R50.pth"),
]


def reporthook(count, block_size, total_size):
    if total_size > 0 and count % 200 == 0:
        pct = min(100, count * block_size * 100 // total_size)
        mb = count * block_size / (1024 * 1024)
        print(f"  {pct}% ({mb:.1f}MB)", flush=True)


def ensure_gdown():
    try:
        import gdown  # noqa
        return True
    except ImportError:
        print("Installing gdown...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "gdown", "--quiet"], check=False)
        return result.returncode == 0


failed = []

# --- GitHub models ---
for name, url in github_models:
    dst = os.path.join(CKPT, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        print(f"[OK] {name} ({size_mb:.0f}MB) - already exists")
        continue
    print(f"Downloading {name} ...")
    try:
        urllib.request.urlretrieve(url, dst, reporthook)
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        print(f"[OK] {name} ({size_mb:.0f}MB)")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        failed.append(name)

# --- Google Drive models (need gdown) ---
print("\nDownloading HuggingFace models (GPEN + RetinaFace)...")
for name, url in hf_models:
    dst = os.path.join(CKPT, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 1_000_000:
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        print(f"[OK] {name} ({size_mb:.0f}MB) - already exists")
        continue
    print(f"Downloading {name} from HuggingFace...")
    try:
        urllib.request.urlretrieve(url, dst, reporthook)
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        print(f"[OK] {name} ({size_mb:.0f}MB)")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        failed.append(name)

print()
if failed:
    print(f"WARNING: {len(failed)} models failed: {failed}")
    print("Download manually from:")
    print("  https://huggingface.co/camenduru/video-retalking/tree/main")
    sys.exit(1)
else:
    print("All models downloaded successfully!")

# --- Extract BFM.zip if not already done ---
bfm_zip = os.path.join(CKPT, "BFM.zip")
bfm_dir = os.path.join(CKPT, "BFM")
key_file = os.path.join(bfm_dir, "similarity_Lm3D_all.mat")
if os.path.exists(bfm_zip) and not os.path.exists(key_file):
    print("\nExtracting BFM.zip ...")
    import zipfile
    with zipfile.ZipFile(bfm_zip, 'r') as zf:
        zf.extractall(bfm_dir)
    print(f"[OK] BFM extracted to: {bfm_dir}")
elif os.path.exists(key_file):
    print(f"[OK] BFM already extracted")

print(f"\nLocation: {CKPT}")
