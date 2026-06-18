"""
Download viXTTS model (Vietnamese voice cloning) từ HuggingFace.
Thay thế XTTS v2 base vì base không hỗ trợ tiếng Việt.
Chỉ cần chạy 1 lần.
"""
import os
import sys
import shutil

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path

BASE_DIR  = Path(__file__).parent.resolve()
MODEL_DIR = BASE_DIR / "models" / "vixtts"
OLD_MODEL_DIR = BASE_DIR / "models" / "xtts_v2"

REPO_ID = "capleaf/viXTTS"

REQUIRED_FILES = [
    "model.pth",
    "config.json",
    "vocab.json",
]


def check_already_downloaded() -> bool:
    if not MODEL_DIR.exists():
        return False
    missing = [f for f in REQUIRED_FILES if not (MODEL_DIR / f).exists()]
    if missing:
        print(f"[viXTTS] Thiếu files: {missing}")
        return False
    size_mb = sum((MODEL_DIR / f).stat().st_size for f in REQUIRED_FILES if (MODEL_DIR / f).exists()) / (1024*1024)
    print(f"[viXTTS] Model OK ({size_mb:.0f}MB)")
    return True


def delete_old_xtts():
    """Xóa model XTTS v2 cũ để giải phóng dung lượng."""
    if OLD_MODEL_DIR.exists():
        print(f"\n[INFO] Xóa model XTTS v2 cũ tại: {OLD_MODEL_DIR}")
        print("[INFO] Đang xóa (~2.7GB)...")
        shutil.rmtree(OLD_MODEL_DIR)
        print("[OK] Đã xóa XTTS v2 cũ.")
    else:
        print("[INFO] Không tìm thấy model XTTS v2 cũ, bỏ qua.")


def download():
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[ERROR] Cần huggingface_hub: pip install huggingface_hub")
        return False

    print("=" * 55)
    print("  Download viXTTS – Vietnamese Voice Cloning (~1.8GB)")
    print("=" * 55)

    # Xóa model cũ trước
    delete_old_xtts()

    if check_already_downloaded():
        print(f"\n[OK] viXTTS model đã có tại: {MODEL_DIR}")
        print("Không cần download lại. Bắt đầu chạy app ngay!")
        return True

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n[INFO] Đang download từ HuggingFace: {REPO_ID}")
    print(f"[INFO] Lưu vào: {MODEL_DIR}")
    print("[INFO] Khoảng ~1.8GB, vui lòng chờ...\n")

    try:
        snapshot_download(
            repo_id=REPO_ID,
            local_dir=str(MODEL_DIR),
            local_dir_use_symlinks=False,
            ignore_patterns=["*.md", "*.txt", "*.gitattributes"],
        )
    except Exception as e:
        print(f"\n[ERROR] Download thất bại: {e}")
        _download_individual_files()

    if check_already_downloaded():
        print(f"\n[SUCCESS] Download xong! viXTTS model tại: {MODEL_DIR}")
        print("Bây giờ bạn có thể dùng Voice Clone tiếng Việt trong app.")
        return True
    else:
        print("\n[ERROR] Download chưa đủ file. Thử lại.")
        return False


def _download_individual_files():
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return
    for fname in REQUIRED_FILES:
        dest = MODEL_DIR / fname
        if dest.exists():
            print(f"  [SKIP] {fname}")
            continue
        try:
            print(f"  [↓] Đang tải {fname}...")
            hf_hub_download(
                repo_id=REPO_ID,
                filename=fname,
                local_dir=str(MODEL_DIR),
                local_dir_use_symlinks=False,
            )
            print(f"  [OK] {fname}")
        except Exception as e:
            print(f"  [WARN] {fname}: {e}")


if __name__ == "__main__":
    success = download()
    exit(0 if success else 1)
