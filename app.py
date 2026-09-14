import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from vision_api import vision_detector
from audio_api import audio_detector

app = FastAPI(title="Multimodal Deepfake Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audio file extensions that have an audio track worth analyzing
AUDIO_VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'}

@app.post("/detect")
async def submit_video(file: UploadFile = File(...)):
    os.makedirs("temp", exist_ok=True)
    
    # Fix 10: Unique temp filename per upload to prevent collisions
    ext = os.path.splitext(file.filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join("temp", unique_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    print(f"Processing media: {file.filename} synchronously...")
    
    is_video = ext in {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'}
    has_audio = ext in AUDIO_VIDEO_EXTS
    
    try:
        # 1. Vision - returns score, heatmap, fft, faces, timeline
        vision_result = vision_detector.predict_vision(file_path, is_video=is_video)
        vision_score = vision_result.get("score", 0.0)
        
        # 2. Audio - only run if file could have audio (Fix 8)
        audio_result = {"score": 0.0, "flatness": 0.0, "phase": 0.0, "spectrogram": None}
        audio_score = 0.0
        if has_audio:
            audio_result = audio_detector.predict_audio(file_path)
            audio_score = audio_result.get("score", 0.0)
        
        # 3. Fusion — weighted combination (Fix 9: removed dead fusion model)
        if has_audio and audio_score > 0.0:
            # Both modalities available: weighted fusion
            fusion_score = 0.6 * vision_score + 0.4 * audio_score
        else:
            # Image or no audio: use vision score directly
            fusion_score = vision_score
        
        # Compute lip_sync_score honestly (null if we can't compute it)
        lip_sync_score = None  # Fix 9: removed hardcoded 0.89
        
        return {
            "is_fake": bool(fusion_score > 0.5),
            "confidence": float(fusion_score),
            "breakdown": {
                "visual_score": float(vision_score),
                "audio_score": float(audio_score) if has_audio else None,
                "lip_sync_score": lip_sync_score
            },
            # Rich forensic data from vision
            "heatmap": vision_result.get("heatmap"),
            "fft": vision_result.get("fft"),
            "faces": vision_result.get("faces", []),
            "timeline": vision_result.get("timeline", []),
            # Rich forensic data from audio
            "spectrogram": audio_result.get("spectrogram"),
            "audio_flatness": audio_result.get("flatness", 0.0),
            "audio_phase": audio_result.get("phase", 0.0),
        }
    finally:
        # Always clean up uploaded file
        try:
            os.remove(file_path)
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
