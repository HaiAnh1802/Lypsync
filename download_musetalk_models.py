import os
import sys

# Fix encoding on Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path

BASE_DIR  = Path(__file__).parent.resolve()
MT_DIR    = BASE_DIR / "musetalk"
MODEL_DIR = MT_DIR / "models"

def download():
    try:
        from huggingface_hub import snapshot_download, hf_hub_download
    except ImportError:
        print("[ERROR] Need huggingface_hub: pip install huggingface_hub")
        return False

    print("[MuseTalk] Downloading models (~1.5GB total)...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. TMElyralab/MuseTalk (main repo: musetalk + whisper + dwpose + face-parse-bisent) ---
    print("\n[1/4] Downloading TMElyralab/MuseTalk repo...")
    try:
        snapshot_download(
            repo_id="TMElyralab/MuseTalk",
            local_dir=str(MODEL_DIR),
            local_dir_use_symlinks=False,
        )
        print("  [OK] MuseTalk main repo")
    except Exception as e:
        print(f"  [WARN] {e}")

    # --- 2. SD-VAE weights ---
    print("\n[2/4] Downloading SD VAE (stabilityai/sd-vae-ft-mse)...")
    vae_dir = MODEL_DIR / "sd-vae-ft-mse"
    vae_dir.mkdir(exist_ok=True)
    for fname in ["config.json", "diffusion_pytorch_model.bin"]:
        dest = vae_dir / fname
        if dest.exists():
            print(f"  [SKIP] {fname}")
            continue
        try:
            hf_hub_download(
                repo_id="stabilityai/sd-vae-ft-mse",
                filename=fname,
                local_dir=str(vae_dir),
                local_dir_use_symlinks=False,
            )
            print(f"  [OK] {fname}")
        except Exception as e:
            print(f"  [WARN] {fname}: {e}")

    # --- 3. Whisper tiny ---
    print("\n[3/4] Downloading Whisper tiny (openai/whisper-tiny)...")
    whisper_dir = MODEL_DIR / "whisper"
    whisper_dir.mkdir(exist_ok=True)
    for fname in ["config.json", "pytorch_model.bin", "preprocessor_config.json"]:
        dest = whisper_dir / fname
        if dest.exists():
            print(f"  [SKIP] {fname}")
            continue
        try:
            hf_hub_download(
                repo_id="openai/whisper-tiny",
                filename=fname,
                local_dir=str(whisper_dir),
                local_dir_use_symlinks=False,
            )
            print(f"  [OK] {fname}")
        except Exception as e:
            print(f"  [WARN] {fname}: {e}")

    # --- 4. DWPose ---
    print("\n[4/4] Downloading DWPose (yzd-v/DWPose)...")
    dwpose_dir = MODEL_DIR / "dwpose"
    dwpose_dir.mkdir(exist_ok=True)
    dwpose_file = dwpose_dir / "dw-ll_ucoco_384.pth"
    if dwpose_file.exists():
        print("  [SKIP] dw-ll_ucoco_384.pth")
    else:
        try:
            hf_hub_download(
                repo_id="yzd-v/DWPose",
                filename="dw-ll_ucoco_384.pth",
                local_dir=str(dwpose_dir),
                local_dir_use_symlinks=False,
            )
            print("  [OK] dw-ll_ucoco_384.pth")
        except Exception as e:
            print(f"  [WARN] dw-ll_ucoco_384.pth: {e}")

    # --- Check main model ---
    musetalk_model = MODEL_DIR / "musetalk" / "pytorch_model.bin"
    if musetalk_model.exists():
        print("\n[MuseTalk] Models ready!")
        return True
    else:
        print("\n[MuseTalk] Main model missing! Manual download:")
        print("  cd musetalk && download_weights.bat")
        return False


if __name__ == "__main__":
    success = download()
    exit(0 if success else 1)
