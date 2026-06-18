"""
vixtts_runner.py – Script chạy trong venv_vixtts (Python 3.11)
Dùng low-level XTTS API để clone giọng chính xác hơn.
"""
import argparse
import os
import sys

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from pathlib import Path

BASE_DIR  = Path(__file__).parent.resolve()
MODEL_DIR = str(BASE_DIR / "models" / "vixtts")


def run(text: str, speaker_wav: str, language: str, output: str):
    try:
        import torch
        import torchaudio
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import Xtts
    except ImportError as e:
        print(f"[ERROR] Missing library: {e}", file=sys.stderr)
        sys.exit(1)

    config_path = os.path.join(MODEL_DIR, "config.json")
    if not os.path.exists(config_path):
        print(f"[ERROR] Model not found: {MODEL_DIR}", file=sys.stderr)
        print("[ERROR] Run download_xtts_model.bat first!", file=sys.stderr)
        sys.exit(1)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[viXTTS] Device: {device}", flush=True)
    print(f"[viXTTS] Loading model...", flush=True)

    # Load config
    config = XttsConfig()
    config.load_json(config_path)

    # Load model với low-level API
    model = Xtts.init_from_config(config)
    model.load_checkpoint(
        config,
        checkpoint_dir=MODEL_DIR,
        eval=True,
        use_deepspeed=False,
    )
    model = model.to(device)
    print("[viXTTS] Model loaded OK.", flush=True)

    # Extract voice conditioning từ file mẫu
    print(f"[viXTTS] Extracting voice from: {speaker_wav}", flush=True)
    gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
        audio_path=[speaker_wav],
        gpt_cond_len=config.gpt_cond_len,
        max_ref_length=config.max_ref_len,
        sound_norm_refs=config.sound_norm_refs,
    )

    # Inference
    print(f"[viXTTS] Generating speech ({language})...", flush=True)
    out = model.inference(
        text=text,
        language=language,
        gpt_cond_latent=gpt_cond_latent,
        speaker_embedding=speaker_embedding,
        temperature=0.75,
        length_penalty=1.0,
        repetition_penalty=5.0,
        top_k=50,
        top_p=0.85,
        do_sample=True,
        speed=1.0,
        enable_text_splitting=True,
    )

    # Lưu file wav
    wav_tensor = torch.tensor(out["wav"]).unsqueeze(0)
    torchaudio.save(output, wav_tensor, 24000)
    print(f"[viXTTS] Done: {output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--text",        required=True)
    parser.add_argument("--speaker_wav", required=True)
    parser.add_argument("--language",    default="vi")
    parser.add_argument("--output",      required=True)
    args = parser.parse_args()

    run(args.text, args.speaker_wav, args.language, args.output)
