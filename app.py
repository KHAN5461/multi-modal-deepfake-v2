import os
import shutil
from fastapi import FastAPI, UploadFile, File
from celery_worker import process_multimodal_video
from fastapi.middleware.cors import CORSMiddleware

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
        
    task = process_multimodal_video.delay(file_path)
    return {"task_id": task.id, "status": "Queued"}

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    task = process_multimodal_video.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {"state": task.state, "status": "Pending..."}
    elif task.state != 'FAILURE':
        response = {"state": task.state, "result": task.result}
    else:
        response = {"state": task.state, "error": str(task.info)}
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
