# מערכת Web לפיקוח קיר כלים (Django + HTMX + labbui + SigLIP)

מערכת ראייה ממוחשבת מבוססת Web מלאה לניטור נוכחות ומיקום כלי עבודה בזמן אמת, מותאמת למחשבים עם **16GB RAM ומעלה** (ריצה על CPU מקומי עם Batch Inference ו-Cached Embeddings).

## תכונות מרכזיות
- **100% Web-Native (Django + HTMX):** ללא חלונות OpenCV חיצוניים. כל הכיול, הגדרות המצלמה והסריקות מתבצעים ישירות מהדפדפן.
- **סטודיו כיול אינטראקטיבי (HTML5 Canvas):** צילום פריים מהדפדפן, סימון מלבנים (ROIs) עם העכבר עבור כלי עבודה ונקודת עוגן (Anchor Point), וחישוב אוטומטי של יחס הרזולוציה (Scaling).
- **מנוע SigLIP מואץ (Batch Inference + Cached Vectors):** וקטור הרפרנס של כל כלי מחושב פעם אחת בלבד בכיול ונשמר ב-SQLite. בזמן סריקה כל החיתוכים מורצים יחד באצווה אחת (`torch.inference_mode()`), מה שמוריד את צריכת הזיכרון לפחות מ-1GB RAM.
- **ייצוב חומרה ופוקוס אוטומטי:** השלת 45 פריימים ראשוניים (ניתן לשינוי במסך ההגדרות) למניעת תמונות שרופות (Overexposure) או חוסר פוקוס.
- **בקרת תזוזה חכמה ב-3 טווחים (Deadbands):**
  - מתחת ל-6px: התעלמות מרעידות קלות.
  - 6px עד 40px: פיצוי והزזה שקטה של הריבועים ברקע ללא התרעות מציקות.
  - מעל 40px או הסתרת העוגן: התרעה ויזואלית בדשבורד.

---

## הוראות הרצה מהירות (VS Code)

### 1. הפעלת סביבה וירטואלית והתקנת ספריות
```bash
python -m venv venv
# ב-Linux / macOS:
source venv/bin/activate
# ב-Windows:
venv\Scripts\activate

pip install --upgrade pip
pip install Django opencv-python Pillow numpy django-cotton labbui
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers
```

### 2. יצירת מסד הנתונים (SQLite)
```bash
python manage.py makemigrations inventory audit
python manage.py migrate
```

### 3. הפעלת השרת
```bash
python manage.py runserver
```

### 4. שימוש במערכת בדפדפן
פתח את הדפדפן בכתובת: `http://127.0.0.1:8000/`
1. **הגדרות מצלמה (`/settings/`):** ודא שאינדקס המצלמה (`0` או `1`) ומספר פריימי הייצוב (`45`) מתאימים למצלמה שלך ולחץ "בדוק ושמור הגדרות".
2. **סטודיו כיול (`/calibrate/`):**
   - לחץ על **"צלם פריים כיול מהמצלמה"**.
   - גרור מלבן עם העכבר על התמונה סביב נקודה קבועה (מדבקה/פינה), בחר "נקודת עוגן (Anchor Point)" ולחץ שמור.
   - גרור מלבן סביב כל כלי עבודה, הזן את שמו (למשל "פטיש", "מברג") ולחץ שמור.
3. **דשבורד פיקוח (`/`):** לחץ על **"סרוק קיר עכשיו"** (או הפעל סריקה אוטומטית כל 30 שניות) וצפה בתוצאות בזמן אמת!
