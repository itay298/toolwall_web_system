import os
import time
import cv2
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import AutoImageProcessor, AutoModel


class VisionEngine:


    def __init__(self):
        self.device = "cpu"
        self.model_id = "google/siglip-base-patch16-224"
        self.processor = None
        self.model = None
        # שמירת חיבור מצלמה חי לסריקות אוטומטיות מהירות
        self.cap = None
        self.active_cam_cfg = None

    def capture_frame(self, wall):
        cfg = (wall.camera_index, wall.frame_width, wall.frame_height)

        # אם המצלמה עדיין לא פתוחה או שההגדרות שונו - פותחים ומבצעים חימום מלא (45 פריימים)
        if self.cap is None or not self.cap.isOpened() or self.active_cam_cfg != cfg:
            if self.cap is not None:
                self.cap.release()

            if os.name == "nt":
                self.cap = cv2.VideoCapture(wall.camera_index, cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(wall.camera_index)
            else:
                self.cap = cv2.VideoCapture(wall.camera_index)

            if not self.cap.isOpened():
                raise RuntimeError(f"לא ניתן לפתוח מצלמה באינדקס {wall.camera_index}.")

            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, wall.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, wall.frame_height)
            self.active_cam_cfg = cfg

            # חימום מלא מתבצע רק בפעם הראשונה שהמצלמה נפתחת!
            warmup = max(10, int(wall.warmup_frames))
            for _ in range(warmup):
                self.cap.read()
                time.sleep(0.03)

        # בסריקות אוטומטיות עוקבות המצלמה כבר בפוקוס - מנקים רק 4 פריימים ישנים מה-Buffer
        frame = None
        for _ in range(5):
            ret, temp = self.cap.read()
            if ret and temp is not None:
                frame = temp

        # אם החיבור נפל (למשל כבל USB זז), מאפסים כדי שינסה להתחבר מחדש בסריקה הבאה
        if frame is None:
            self.cap.release()
            self.cap = None
            raise RuntimeError(f"שגיאה בקריאת פריים ממצלמה באינדקס {wall.camera_index}.")

        return frame

    def _ensure_loaded(self):
        if self.model is None:
            print("[VisionEngine] טוען מודל SigLIP לזיכרון (CPU Optimized)...")
            self.processor = AutoImageProcessor.from_pretrained(self.model_id)
            self.model = AutoModel.from_pretrained(self.model_id).to(self.device)
            self.model.eval()
            print("[VisionEngine] מודל SigLIP מוכן לעבודה.")

    def _extract_features_tensor(self, pixel_values: torch.Tensor) -> torch.Tensor:
        """מחלץ טנזור מנורמל של וקטורי התמונה בלי תלות בגרסת transformers"""
        outputs = self.model.get_image_features(pixel_values=pixel_values)
        if isinstance(outputs, torch.Tensor):
            feats = outputs
        elif hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            feats = outputs.pooler_output
        elif hasattr(outputs, "image_embeds") and outputs.image_embeds is not None:
            feats = outputs.image_embeds
        else:
            feats = outputs[0]

        return F.normalize(feats, p=2, dim=-1)

   
    def compute_single_embedding(self, crop_bgr) -> list[float]:
        """מחשב וקטור משמעות (768d) לחיתוך בודד בזמן הכיול בדפדפן"""
        self._ensure_loaded()
        rgb_img = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
        inputs = self.processor(images=[rgb_img], return_tensors="pt").to(self.device)

        with torch.inference_mode():
            feats = self._extract_features_tensor(inputs["pixel_values"])
        return feats[0].cpu().tolist()

    def batch_compare(self, crops_bgr: list, ref_embeddings: list[list[float]]) -> list[float]:
        """מריץ השוואת SigLIP באצווה אחת על כל הכלים במקביל"""
        if not crops_bgr:
            return []
        self._ensure_loaded()

        pil_images = [Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)) for c in crops_bgr]
        inputs = self.processor(images=pil_images, return_tensors="pt").to(self.device)

        with torch.inference_mode():
            curr_feats = self._extract_features_tensor(inputs["pixel_values"])
            ref_tensor = torch.tensor(ref_embeddings, dtype=curr_feats.dtype, device=self.device)
            similarities = (curr_feats * ref_tensor).sum(dim=-1).cpu().tolist()

        return [float(s) for s in similarities]

    def get_drift(self, frame, wall):
        """בקרת תזוזה ב-3 טווחים ביחס לנקודת העוגן"""
        if not wall.anchor_image or wall.anchor_w <= 0 or wall.anchor_h <= 0:
            return 0, 0, False

        try:
            anchor_path = wall.anchor_image.path
        except Exception:
            return 0, 0, False

        if not os.path.exists(anchor_path):
            return 0, 0, False

        anchor_ref = cv2.imread(anchor_path, cv2.IMREAD_GRAYSCALE)
        if anchor_ref is None:
            return 0, 0, False

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if anchor_ref.shape[0] > gray_frame.shape[0] or anchor_ref.shape[1] > gray_frame.shape[1]:
            return 0, 0, False

        res = cv2.matchTemplate(gray_frame, anchor_ref, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, (cur_x, cur_y) = cv2.minMaxLoc(res)

        if max_val < 0.55:
            return 0, 0, True

        dx = int(cur_x - wall.anchor_x)
        dy = int(cur_y - wall.anchor_y)
        dist = (dx**2 + dy**2) ** 0.5

        if dist < 6:
            return 0, 0, False
        elif dist <= 40:
            return dx, dy, False
        else:
            return dx, dy, True


engine = VisionEngine()