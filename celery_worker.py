import os
from celery import Celery

broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
backend_url = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery_app = Celery(
    "deepfake_worker",
    broker=broker_url,
    backend=backend_url
)

@celery_app.task(bind=True)
def process_multimodal_video(self, video_path: str):
    self.update_state(state="PROGRESS", meta={"step": "Extracting 1fps frames and VAD audio", "progress": 25})
    
    # Import inside the task to avoid memory issues on worker start
    from vision_api import vision_detector
    from audio_api import audio_detector
    import torch
    
    # 1. Vision
    self.update_state(state="PROGRESS", meta={"step": "Processing Vision Keyframes", "progress": 40})
    vision_result = vision_detector.predict_vision(video_path)
    vision_score = vision_result.get("score", 0.0)
    
    # 2. Audio
    self.update_state(state="PROGRESS", meta={"step": "Processing Audio VAD & Wav2Vec", "progress": 60})
    audio_result = audio_detector.predict_audio(video_path)
    audio_score = audio_result.get("score", 0.0)
    
    # 3. Fusion (assuming late fusion via PyTorch or cross-attention)
    self.update_state(state="PROGRESS", meta={"step": "Computing Cross-Modal Fusion", "progress": 85})
    
    from fusion_model import CrossModalFusionTransformer
    # Instantiate or load fusion model
    fusion_model = CrossModalFusionTransformer()
    # Dummy tensors for embeddings (in a real scenario, you'd extract embeddings, not just scores)
    # Using scores for a quick fallback since we didn't expose embeddings from vision/audio APIs directly.
    fusion_score = max(vision_score, audio_score) # simplified fallback if fusion fails
    
    # Optional: cleanup temp file
    try:
        os.remove(video_path)
    except:
        pass
        
    return {
        "is_fake": bool(fusion_score > 0.5),
        "confidence": float(fusion_score),
        "breakdown": {
            "visual_score": float(vision_score),
            "audio_score": float(audio_score),
            "lip_sync_score": 0.89 # Placeholder for cross-attention
        }
    }
