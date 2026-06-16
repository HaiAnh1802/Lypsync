import os
import sys
import uuid
import shutil
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# Fix Unicode output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from tts import text_to_audio, estimate_duration, gemini_tts_direct, convert_for_lipsync, gemini_tts_for_pipeline, edge_tts_for_pipeline
from video_utils import loop_video, check_ffmpeg, get_duration
from lipsync import generate, is_wav2lip_available
from videoretalking import generate_vrt, is_videoretalking_available


# === Trạng thái xử lý job ===
jobs: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    yield


app = FastAPI(title="LipSync AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/status")
async def system_status():
    """Kiem tra trang thai he thong."""
    return {
        "ffmpeg": check_ffmpeg(),
        "wav2lip": is_wav2lip_available(),
        "videoretalking": is_videoretalking_available(),
        "ready": check_ffmpeg() and is_wav2lip_available()
    }


@app.post("/api/estimate")
async def estimate(text: str = Form(...)):
    """Ước tính thời lượng video output dựa trên text."""
    duration = estimate_duration(text)
    return {"estimated_duration": duration}


@app.post("/api/tts")
async def tts_generate(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    api_key: str = Form(...),
    voice: str = Form("Kore"),
):
    """
    Tạo giọng đọc từ text bằng Gemini TTS API.
    Trả về file WAV trực tiếp để download/phát.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text không được để trống")
    if not api_key.strip():
        raise HTTPException(status_code=400, detail="Cần Gemini API key")

    try:
        audio_path = await asyncio.to_thread(
            gemini_tts_direct, text, api_key, voice
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini TTS lỗi: {str(e)}")

    # Xóa file sau khi gửi xong
    background_tasks.add_task(os.remove, audio_path)

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"gemini_tts_{voice}.wav",
    )


@app.post("/api/generate")
async def generate_lipsync(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    text: str = Form(...),
    tts_engine: str = Form("gtts"),           # "gemini" | "edge" | "gtts"
    lipsync_engine: str = Form("wav2lip"),    # "wav2lip" | "videoretalking"
    gemini_api_key: str = Form(""),
    gemini_voice: str = Form(""),
    edge_voice: str = Form("vi-VN-HoaiMyNeural"),
):
    """
    Main endpoint: Upload video + text -> tra ve job_id de theo doi tien trinh.
    lipsync_engine: 'wav2lip' (default) hoac 'videoretalking'
    """
    if not check_ffmpeg():
        raise HTTPException(status_code=400, detail="FFmpeg chua duoc cai! Chay setup.bat truoc.")

    if lipsync_engine == "videoretalking":
        if not is_videoretalking_available():
            raise HTTPException(status_code=400, detail="VideoReTalking chua cai models! Chay setup_videoretalking.bat truoc.")
    else:
        if not is_wav2lip_available():
            raise HTTPException(status_code=400, detail="Wav2Lip chua duoc cai! Chay setup.bat truoc.")

    # Luu video upload
    job_id = uuid.uuid4().hex[:12]
    video_ext = Path(video.filename).suffix or ".mp4"
    video_path = f"uploads/{job_id}_input{video_ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    # Khoi tao job
    jobs[job_id] = {
        "status": "queued",
        "step": "Dang chuan bi...",
        "progress": 0,
        "output": None,
        "error": None
    }

    # Chay xu ly o background
    background_tasks.add_task(
        process_job, job_id, video_path, text,
        tts_engine.strip(), lipsync_engine.strip(),
        gemini_api_key.strip(),
        gemini_voice.strip(), edge_voice.strip()
    )

    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Theo dõi trạng thái job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return jobs[job_id]


@app.get("/api/download/{job_id}")
async def download_result(job_id: str):
    """Download video kết quả."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    
    job = jobs[job_id]
    if job["status"] != "done" or not job["output"]:
        raise HTTPException(status_code=400, detail="Video chưa sẵn sàng")
    
    return FileResponse(
        job["output"],
        media_type="video/mp4",
        filename="lipsync_output.mp4"
    )


async def process_job(job_id: str, video_path: str, text: str,
                      tts_engine: str = "gtts",
                      lipsync_engine: str = "wav2lip",
                      gemini_api_key: str = "", gemini_voice: str = "",
                      edge_voice: str = "vi-VN-HoaiMyNeural"):
    """Background task: TTS -> Loop -> LipSync (Wav2Lip or VideoReTalking)."""
    hq_audio_path = None
    try:
        # Bước 1: TTS
        if tts_engine == "gemini" and gemini_api_key:
            voice_label = gemini_voice or "Kore"
            jobs[job_id].update({"status": "processing", "step": f"🎤 Đang tạo giọng đọc Gemini ({voice_label})...", "progress": 15})
            audio_path, hq_audio_path = await asyncio.to_thread(
                gemini_tts_for_pipeline, text, gemini_api_key, voice_label
            )
        elif tts_engine == "edge":
            jobs[job_id].update({"status": "processing", "step": f"🎤 Đang tạo giọng đọc Edge TTS ({edge_voice})...", "progress": 15})
            audio_path, hq_audio_path = await asyncio.to_thread(
                edge_tts_for_pipeline, text, edge_voice
            )
        else:
            jobs[job_id].update({"status": "processing", "step": "🎤 Đang tạo giọng đọc gTTS...", "progress": 15})
            audio_path, audio_duration = await asyncio.to_thread(text_to_audio, text)

        audio_duration = get_duration(audio_path)

        # Bước 2: Loop video
        jobs[job_id].update({"step": f"🔄 Đang loop video ({audio_duration:.0f}s)...", "progress": 35})
        looped_video_path = await asyncio.to_thread(loop_video, video_path, audio_duration)

        # Buoc 3: Lip Sync
        engine_label = "VideoReTalking" if lipsync_engine == "videoretalking" else "Wav2Lip"
        jobs[job_id].update({"step": f"Dang lip sync ({engine_label} - GPU)...", "progress": 50})

        if lipsync_engine == "videoretalking":
            output_path = await asyncio.to_thread(
                generate_vrt, looped_video_path, audio_path,
                "outputs", hq_audio_path
            )
        else:
            output_path = await asyncio.to_thread(
                generate, looped_video_path, audio_path,
                "outputs", True, hq_audio_path
            )

        # Xong!
        jobs[job_id].update({
            "status": "done",
            "step": "✅ Hoàn tất!",
            "progress": 100,
            "output": output_path,
            "duration": audio_duration
        })

        # Dọn dẹp file tạm
        tmp_files = [audio_path, looped_video_path]
        if hq_audio_path:
            tmp_files.append(hq_audio_path)
        for f in tmp_files:
            if f and os.path.exists(f):
                os.remove(f)

    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "step": f"❌ Lỗi: {str(e)}",
            "progress": 0,
            "error": str(e)
        })
        print(f"Job {job_id} loi: {e}")


if __name__ == "__main__":
    import uvicorn
    print("[LipSync AI] Server dang khoi dong tai http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
