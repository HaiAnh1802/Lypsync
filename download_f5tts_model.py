"""
download_f5tts_model.py
========================
Tải model F5-TTS vào thư mục models/f5tts/ trong project.
Chạy 1 lần qua setup_voiceclone.bat.
"""

import os
import sys
import shutil
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "models" / "f5tts"
REPO_ID = "SWivid/F5-TTS"
MODEL_SUBDIR = "F5TTS_v1_Base"
MODEL_FILENAME = "model_1250000.safetensors"
VOCAB_FILENAME = "vocab.txt"
VOCODER_REPO = "charactr/vocos-mel-24khz"
VOCODER_FILES = ["config.yaml", "pytorch_model.bin"]


def download_f5tts():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_file  = MODEL_DIR / MODEL_FILENAME
    vocab_file  = MODEL_DIR / VOCAB_FILENAME
    vocoder_dir = MODEL_DIR / "vocos"
    vocoder_dir.mkdir(exist_ok=True)

    print("=" * 50)
    print("  Download model F5-TTS vao models/f5tts/")
    print("=" * 50)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[LOI] huggingface_hub chua cai. Chay: pip install huggingface_hub")
        sys.exit(1)

    # ── 1. Download F5-TTS checkpoint ──────────────────────
    if model_file.exists() and model_file.stat().st_size > 1_000_000_000:
        print(f"[OK] Model da co san: {model_file}")
    else:
        print(f"[1/4] Dang tai F5-TTS model (~1.3GB): {MODEL_FILENAME}...")
        hf_hub_download(
            repo_id=REPO_ID,
            filename=f"{MODEL_SUBDIR}/{MODEL_FILENAME}",
            local_dir=str(MODEL_DIR),
        )
        # hf_hub_download luu vao subfolder -> move ra ngoai
        downloaded = MODEL_DIR / MODEL_SUBDIR / MODEL_FILENAME
        if downloaded.exists():
            shutil.move(str(downloaded), str(model_file))
            sub = MODEL_DIR / MODEL_SUBDIR
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        print(f"[OK] Da luu: {model_file}")

    # ── 1b. Download vocab.txt ─────────────────────────────
    if vocab_file.exists():
        print(f"[OK] vocab.txt da co")
    else:
        print(f"[2/4] Dang tai vocab.txt...")
        hf_hub_download(
            repo_id=REPO_ID,
            filename=f"{MODEL_SUBDIR}/{VOCAB_FILENAME}",
            local_dir=str(MODEL_DIR),
        )
        downloaded_vocab = MODEL_DIR / MODEL_SUBDIR / VOCAB_FILENAME
        if downloaded_vocab.exists():
            shutil.move(str(downloaded_vocab), str(vocab_file))
            sub = MODEL_DIR / MODEL_SUBDIR
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        print(f"[OK] Da luu: {vocab_file}")

    # ── 3. Download Vocos vocoder ────────────────────────────
    print(f"[3/4] Dang tai Vocos vocoder...")
    for vfile in VOCODER_FILES:
        dst = vocoder_dir / vfile
        if dst.exists():
            print(f"[OK] Vocos/{vfile} da co")
        else:
            hf_hub_download(
                repo_id=VOCODER_REPO,
                filename=vfile,
                local_dir=str(vocoder_dir),
            )
            print(f"[OK] Da luu: {dst}")

    # ── 4. Kiem tra ────────────────────────────────────────
    print(f"[4/4] Kiem tra...")
    ok = True
    for f in [model_file, vocab_file, vocoder_dir / "config.yaml", vocoder_dir / "pytorch_model.bin"]:
        if f.exists():
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  + {f.name}: {size_mb:.1f} MB")
        else:
            print(f"  - THIEU: {f}")
            ok = False

    if ok:
        print()
        print("[XONG] Tat ca model da san sang tai: models/f5tts/")
        print("       App se dung local model, khong can internet khi chay.")
    else:
        print("[CANH BAO] Mot so file con thieu!")
        sys.exit(1)


if __name__ == "__main__":
    download_f5tts()
