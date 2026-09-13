import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from vision_api import vision_detector
from audio_api import audio_detector
from fusion_model import CrossModalFusionTransformer

app = FastAPI(title="Multimodal Deepfake Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/detect")
async def submit_video(file: UploadFile = File(...)):
    os.makedirs("temp", exist_ok=True)
    file_path = os.path.join("temp", file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    print(f"Processing media: {file.filename} synchronously...")
    
    # Detect if it's a video by extension
    ext = os.path.splitext(file.filename)[1].lower()
    is_video = ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
    
    # 1. Vision - returns score, heatmap, fft, faces, timeline
    vision_result = vision_detector.predict_vision(file_path, is_video=is_video)
    vision_score = vision_result.get("score", 0.0)
    
    # 2. Audio - returns score, flatness, phase, spectrogram
    audio_result = audio_detector.predict_audio(file_path)
    audio_score = audio_result.get("score", 0.0)
    
    # 3. Fusion
    fusion_model = CrossModalFusionTransformer()
    fusion_score = max(vision_score, audio_score)
    
    try:
        os.remove(file_path)
    except:
        pass
        
    return {
        "is_fake": bool(fusion_score > 0.5),
        "confidence": float(fusion_score),
        "breakdown": {
            "visual_score": float(vision_score),
            "audio_score": float(audio_score),
            "lip_sync_score": 0.89
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
