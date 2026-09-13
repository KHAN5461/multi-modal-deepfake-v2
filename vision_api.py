import torch
import numpy as np
import cv2
import base64
from transformers import AutoImageProcessor, AutoModelForImageClassification

def generate_heatmap_b64(frame):
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    _, encoded = cv2.imencode('.jpg', frame, encode_param)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    diff = cv2.absdiff(frame, decoded)
    diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    diff = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    heatmap = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
    _, buffer = cv2.imencode('.png', heatmap)
    return base64.b64encode(buffer).decode('utf-8')

def generate_fft_b64(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
    magnitude_spectrum = cv2.normalize(magnitude_spectrum, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    heatmap = cv2.applyColorMap(magnitude_spectrum, cv2.COLORMAP_VIRIDIS)
    _, buffer = cv2.imencode('.png', heatmap)
    return base64.b64encode(buffer).decode('utf-8')

class FaceExtractor:
    def __init__(self):
        try:
            from uniface.detection import RetinaFace
            from uniface.tracking import BYTETracker
            self.detector = RetinaFace(confidence_threshold=0.6, nms_threshold=0.4)
            self.tracker = BYTETracker()
            print("Successfully loaded UniFace for Multi-Face Tracking")
        except ImportError:
            self.detector = None
            self.tracker = None
            print("uniface not installed. Multi-Face tracking will fall back to center crop.")

    def extract_image_faces(self, file_path):
        frame = cv2.imread(file_path)
        if frame is None:
            return [], frame
            
        faces = []
        if self.detector:
            detected_faces = self.detector.detect(frame)
            if detected_faces:
                for face in detected_faces:
                    x1, y1, x2, y2 = map(int, face.bbox[:4])
                    h, w, _ = frame.shape
                    
                    box_w, box_h = x2 - x1, y2 - y1
                    pad_x = int(box_w * 0.5)
                    pad_y = int(box_h * 0.5)
                    
                    crop_x1 = max(0, x1 - pad_x)
                    crop_y1 = max(0, y1 - pad_y)
                    crop_x2 = min(w, x2 + pad_x)
                    crop_y2 = min(h, y2 + pad_y)
                    
                    if (crop_x2 - crop_x1) > 0 and (crop_y2 - crop_y1) > 0:
                        # OVERLAP-AWARE MASKING skipped for brevity, standard extraction
                        cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                        cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
                        faces.append({"bbox": [crop_x1, crop_y1, crop_x2 - crop_x1, crop_y2 - crop_y1], "img": cropped_rgb})
            
        if not faces:
            # Fallback Center Crop
            h_img, w_img = frame.shape[:2]
            ch, cw = h_img // 2, w_img // 2
            size = min(h_img, w_img) // 4
            cropped = frame[ch-size:ch+size, cw-size:cw+size]
            if cropped.size > 0:
                faces.append({"bbox": [cw-size, ch-size, size*2, size*2], "img": cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)})
                
        return faces, frame

    def extract_video_timeline(self, file_path):
        cap = cv2.VideoCapture(file_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or fps != fps: fps = 30
        
        frames = []
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            if frame_idx % int(fps) == 0:
                detected_faces = None
                if self.detector:
                    detected_faces = self.detector.detect(frame)
                
                if detected_faces and len(detected_faces) > 0:
                    x1, y1, x2, y2 = map(int, detected_faces[0].bbox[:4])
                    h_img, w_img, _ = frame.shape
                    
                    w, h = x2 - x1, y2 - y1
                    pad_x = int(w * 0.5)
                    pad_y = int(h * 0.5)
                    
                    crop_x1 = max(0, x1 - pad_x)
                    crop_y1 = max(0, y1 - pad_y)
                    crop_x2 = min(w_img, x2 + pad_x)
                    crop_y2 = min(h_img, y2 + pad_y)
                    
                    x, y, w, h = crop_x1, crop_y1, crop_x2 - crop_x1, crop_y2 - crop_y1
                else:
                    h_img, w_img = frame.shape[:2]
                    x, y = w_img // 4, h_img // 4
                    w, h = w_img // 2, h_img // 2
                    
                if w > 0 and h > 0:
                    cropped = frame[y:y+h, x:x+w]
                    if cropped.size > 0:
                        cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
                        frames.append((cropped_rgb, frame))
            frame_idx += 1
        cap.release()
        return frames

class VisionModel:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        import os
        
        # Check if the user has fine-tuned their own custom model
        custom_model_dir = "./custom_weights"
        if os.path.exists(custom_model_dir) and os.path.exists(os.path.join(custom_model_dir, "config.json")):
            self.model_vit_id = custom_model_dir
            print(f"Found Custom Weights! Loading Fine-Tuned ViT model from {custom_model_dir}")
        else:
            self.model_vit_id = "dima806/deepfake_vs_real_image_detection"
            
        self.model_cnn_id = "prithivMLmods/Deep-Fake-Detector-Model"
        
        self.model_vit = None
        self.processor_vit = None
        self.model_cnn = None
        self.processor_cnn = None
        
        try:
            self.processor_vit = AutoImageProcessor.from_pretrained(self.model_vit_id)
            self.model_vit = AutoModelForImageClassification.from_pretrained(self.model_vit_id).to(self.device).eval()
            print("Loaded Ensemble Model A (ViT)")
        except Exception as e:
            print(f"Warning: Could not load ViT model: {e}")
            
        try:
            self.processor_cnn = AutoImageProcessor.from_pretrained(self.model_cnn_id)
            self.model_cnn = AutoModelForImageClassification.from_pretrained(self.model_cnn_id).to(self.device).eval()
            print("Loaded Ensemble Model B (CNN)")
        except Exception as e:
            print(f"Warning: Could not load CNN model: {e}")
            
        self.face_extractor = FaceExtractor()

    def process_tensors(self, faces_list):
        if not faces_list: return []
        
        fake_probs_vit = [0.5] * len(faces_list)
        fake_probs_cnn = [0.5] * len(faces_list)
        fake_probs_ela = [0.5] * len(faces_list)
        fake_probs_bio = [0.5] * len(faces_list)
        
        # Phase 4: Biometric Landmark Analysis
        mp_face_mesh = None
        try:
            import mediapipe as mp
            mp_face_mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1)
        except ImportError:
            print("Warning: mediapipe not installed. Skipping Biometric checks.")
            
        # Calculate Localized ELA Variance & Biometrics
        for i, face_img in enumerate(faces_list):
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            _, encoded = cv2.imencode('.jpg', face_img, encode_param)
            decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            diff = cv2.absdiff(face_img, decoded)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            variance = np.var(gray_diff)
            ela_prob = (variance - 10.0) / 70.0
            fake_probs_ela[i] = max(0.0, min(1.0, ela_prob))
            
            bio_prob = 0.5
            if mp_face_mesh:
                results = mp_face_mesh.process(face_img)
                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0].landmark
                    left_eye_w = abs(landmarks[33].x - landmarks[133].x)
                    right_eye_w = abs(landmarks[362].x - landmarks[263].x)
                    symmetry_diff = abs(left_eye_w - right_eye_w)
                    bio_prob = min(symmetry_diff / 0.015, 1.0)
            fake_probs_bio[i] = bio_prob
            
        if self.model_vit:
            inputs = self.processor_vit(images=faces_list, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model_vit(**inputs).logits
            probs = torch.softmax(outputs, dim=1)
            fake_probs_vit = probs[:, 1].cpu().numpy().tolist()
            
        if self.model_cnn:
            inputs = self.processor_cnn(images=faces_list, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model_cnn(**inputs).logits
            probs = torch.softmax(outputs, dim=1)
            fake_probs_cnn = probs[:, 0].cpu().numpy().tolist()
            
        ensemble_probs = []
        for i in range(len(faces_list)):
            avg_prob = (fake_probs_vit[i] + fake_probs_cnn[i] + fake_probs_ela[i] + fake_probs_bio[i]) / 4.0
            ensemble_probs.append(avg_prob)
            
        return ensemble_probs

    def predict_vision(self, file_path: str, is_video: bool = False):
        if is_video:
            frames = self.face_extractor.extract_video_timeline(file_path)
            if not frames:
                return {"score": 0.0, "timeline": [], "heatmap": None, "fft": None, "faces": []}
            
            faces_list = [f[0] for f in frames]
            full_frame = frames[0][1]
            fake_probs = self.process_tensors(faces_list)
            
            return {
                "score": float(np.mean(fake_probs)),
                "timeline": fake_probs,
                "heatmap": generate_heatmap_b64(full_frame),
                "fft": generate_fft_b64(full_frame),
                "faces": []
            }
        else:
            extracted_faces, full_frame = self.face_extractor.extract_image_faces(file_path)
            if not extracted_faces:
                return {"score": 0.0, "timeline": [], "heatmap": None, "fft": None, "faces": []}
                
            faces_list = [f["img"] for f in extracted_faces]
            fake_probs = self.process_tensors(faces_list)
            
            result_faces = []
            for i, f in enumerate(extracted_faces):
                result_faces.append({
                    "face_id": f"face_{i}",
                    "bounding_box": f["bbox"],
                    "score": float(fake_probs[i])
                })
                
            overall_score = float(max(fake_probs)) if fake_probs else 0.0
            
            return {
                "score": overall_score,
                "timeline": [],
                "heatmap": generate_heatmap_b64(full_frame),
                "fft": generate_fft_b64(full_frame),
                "faces": result_faces
            }

vision_detector = VisionModel()
