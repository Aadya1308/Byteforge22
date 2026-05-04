from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
from groq import Groq
from datetime import datetime, timedelta
from dotenv import load_dotenv
import tempfile, os, shutil, hashlib

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "demosecretkey123")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

USERS = {
    "doctor1": {
        "username": "doctor1",
        "hashed_password": pwd_context.hash("password123")
    }
}

def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(hours=8)
    data.update({"exp": expire})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username not in USERS:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = USERS.get(form.username)
    if not user or not pwd_context.verify(form.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Wrong credentials")
    token = create_token({"sub": form.username})
    return {"access_token": token, "token_type": "bearer"}

# ── AI Models ───────────────────────────────────────────────
print("Loading Whisper model...")
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── In-memory storage (no MongoDB needed for demo) ──────────
sessions = []
audit_log = []

# ── Routes ──────────────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    consent: bool = True,
    patient_id: str = "unknown",
    user: str = Depends(get_current_user)
):
    if not consent:
        raise HTTPException(status_code=403, detail="Patient consent required")

    suffix = os.path.splitext(audio.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
        tmp_path = tmp.name

    try:
        # Step 1: Transcribe
        segments, info = whisper_model.transcribe(tmp_path, beam_size=5)
        transcript = " ".join([seg.text for seg in segments])
        detected_lang = info.language

        # Step 2: Translate if non-English
        if detected_lang != "en":
            transcript = GoogleTranslator(
                source="auto", target="en"
            ).translate(transcript)

        # Step 3: Generate SOAP via Groq (free)
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a clinical documentation assistant. Generate structured SOAP notes from transcripts. Flag uncertain fields as [REVIEW REQUIRED]. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": f"""Generate a SOAP note from this transcript:

{transcript}

Return JSON with exactly these keys:
{{
  "subjective": "what patient reports",
  "objective": "clinical observations",
  "assessment": "diagnosis or impression",
  "plan": "treatment and follow-up",
  "icd_suggestion": "ICD-10 code and name"
}}"""
                }
            ],
        )

        import json
        soap_text = response.choices[0].message.content
        # Clean any markdown formatting
        soap_text = soap_text.replace("```json", "").replace("```", "").strip()
        soap = json.loads(soap_text)

        # Step 4: Save to memory
        record = {
            "patient_id": patient_id,
            "transcript": transcript,
            "detected_language": detected_lang,
            "soap": soap,
            "timestamp": datetime.utcnow().isoformat(),
            "clinician": user
        }
        sessions.append(record)

        # Step 5: Audit log
        audit_log.append({
            "audit_id": hashlib.sha256(
                f"{patient_id}{datetime.utcnow()}".encode()
            ).hexdigest()[:16],
            "patient_id": patient_id,
            "action": "TRANSCRIBE_AND_DOCUMENT",
            "clinician": user,
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "transcript": transcript,
            "detected_language": detected_lang,
            "soap": soap,
            "status": "success"
        }

    finally:
        os.unlink(tmp_path)

@app.get("/records/{patient_id}")
def get_records(patient_id: str, user: str = Depends(get_current_user)):
    records = [s for s in sessions if s["patient_id"] == patient_id]
    return {"records": records}

@app.get("/health")
def health():
    return {"status": "ok"}