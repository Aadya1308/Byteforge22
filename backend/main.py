from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pymongo import MongoClient
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from dotenv import load_dotenv
from models import (
    UserRegister, UserLogin, UserResponse,
    PatientCreate, SOAPNote, Prescription,
    ClinicalSession, Medication, ICDCode
)
from ai import transcribe_audio, translate_if_needed, generate_full_soap
import tempfile, os, shutil, hashlib, uuid

load_dotenv()

app = FastAPI(
    title="ClinicalDoc API",
    description="Real-Time Multilingual Healthcare Documentation System — ByteForge22",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth Config ─────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "devsecret123")
ALGORITHM  = "HS256"
pwd_ctx    = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2     = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── MongoDB ─────────────────────────────────────────────────
import certifi
mongo = MongoClient(
    os.getenv("MONGO_URL"),
    tlsCAFile=certifi.where()
)
db    = mongo["clinicaldoc"]

users_col    = db["users"]
patients_col = db["patients"]
sessions_col = db["sessions"]
scripts_col  = db["prescriptions"]
audit_col    = db["audit"]

# Create indexes for fast lookup
users_col.create_index("email", unique=True)
patients_col.create_index("patient_id", unique=True)
sessions_col.create_index("session_id", unique=True)


# ═══════════════════════════════════════════════════════════
#  AUTH HELPERS
# ═══════════════════════════════════════════════════════════

def hash_pw(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_pw(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def make_token(user_id: str, email: str, role: str) -> str:
    exp = datetime.utcnow() + timedelta(hours=8)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        SECRET_KEY, algorithm=ALGORITHM
    )

def get_current_user(token: str = Depends(oauth2)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = users_col.find_one({"user_id": user_id}, {"_id": 0, "hashed_password": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def write_audit(action: str, performed_by: str, target_id: str = "", details: str = ""):
    audit_col.insert_one({
        "audit_id":     hashlib.sha256(f"{performed_by}{datetime.utcnow()}".encode()).hexdigest()[:16],
        "action":       action,
        "performed_by": performed_by,
        "target_id":    target_id,
        "details":      details,
        "timestamp":    datetime.utcnow().isoformat()
    })


# ═══════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════

@app.post("/auth/register", tags=["Auth"])
def register(data: UserRegister):
    if users_col.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    user_doc = {
        "user_id":        user_id,
        "full_name":      data.full_name,
        "email":          data.email,
        "phone":          data.phone,
        "role":           data.role,
        "specialization": data.specialization,
        "hospital_name":  data.hospital_name,
        "license_number": data.license_number,
        "hashed_password": hash_pw(data.password),
        "is_active":      True,
        "created_at":     datetime.utcnow().isoformat()
    }
    users_col.insert_one(user_doc)
    write_audit("USER_REGISTERED", user_id, user_id, f"Role: {data.role}")

    token = make_token(user_id, data.email, data.role)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "user_id":   user_id,
            "full_name": data.full_name,
            "email":     data.email,
            "role":      data.role
        }
    }


@app.post("/auth/login", tags=["Auth"])
def login(data: OAuth2PasswordRequestForm = Depends()):
    user = users_col.find_one({"email": data.username})
    if not user or not verify_pw(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")

    token = make_token(user["user_id"], user["email"], user["role"])
    write_audit("USER_LOGIN", user["user_id"])
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "user_id":        user["user_id"],
            "full_name":      user["full_name"],
            "email":          user["email"],
            "role":           user["role"],
            "specialization": user.get("specialization"),
            "hospital_name":  user.get("hospital_name")
        }
    }


@app.get("/auth/me", tags=["Auth"])
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# ═══════════════════════════════════════════════════════════
#  PATIENT ROUTES
# ═══════════════════════════════════════════════════════════

@app.post("/patients", tags=["Patients"])
def create_patient(
    data: PatientCreate,
    current_user: dict = Depends(get_current_user)
):
    patient_id = "PAT-" + str(uuid.uuid4())[:8].upper()
    doc = {
        "patient_id":              patient_id,
        "full_name":               data.full_name,
        "age":                     data.age,
        "gender":                  data.gender,
        "date_of_birth":           data.date_of_birth,
        "phone":                   data.phone,
        "email":                   data.email,
        "address":                 data.address,
        "blood_group":             data.blood_group,
        "height_cm":               data.height_cm,
        "weight_kg":               data.weight_kg,
        "language":                data.language,
        "emergency_contact_name":  data.emergency_contact_name,
        "emergency_contact_phone": data.emergency_contact_phone,
        "known_allergies":         data.known_allergies,
        "chronic_conditions":      data.chronic_conditions,
        "current_medications":     data.current_medications,
        "past_surgeries":          data.past_surgeries,
        "family_history":          data.family_history,
        "immunization_history":    data.immunization_history,
        "insurance_provider":      data.insurance_provider,
        "insurance_id":            data.insurance_id,
        "registered_by":           current_user["user_id"],
        "created_at":              datetime.utcnow().isoformat()
    }
    patients_col.insert_one(doc)
    write_audit("PATIENT_CREATED", current_user["user_id"], patient_id)
    return {"patient_id": patient_id, "message": "Patient registered", **doc}


@app.get("/patients", tags=["Patients"])
def list_patients(
    search: str = Query(default="", description="Search by name or phone"),
    skip:   int = 0,
    limit:  int = 20,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if search:
        query = {"$or": [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"phone":     {"$regex": search, "$options": "i"}},
            {"patient_id": {"$regex": search, "$options": "i"}}
        ]}
    patients = list(patients_col.find(query, {"_id": 0}).skip(skip).limit(limit))
    total    = patients_col.count_documents(query)
    return {"total": total, "patients": patients}


@app.get("/patients/{patient_id}", tags=["Patients"])
def get_patient(
    patient_id: str,
    current_user: dict = Depends(get_current_user)
):
    p = patients_col.find_one({"patient_id": patient_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p


@app.get("/patients/{patient_id}/history", tags=["Patients"])
def get_patient_history(
    patient_id: str,
    current_user: dict = Depends(get_current_user)
):
    sessions = list(sessions_col.find(
        {"patient_id": patient_id}, {"_id": 0}
    ).sort("created_at", -1))
    prescriptions = list(scripts_col.find(
        {"patient_id": patient_id}, {"_id": 0}
    ).sort("date", -1))
    return {
        "patient_id":    patient_id,
        "total_visits":  len(sessions),
        "sessions":      sessions,
        "prescriptions": prescriptions
    }


# ═══════════════════════════════════════════════════════════
#  TRANSCRIPTION + SOAP GENERATION
# ═══════════════════════════════════════════════════════════

@app.post("/sessions/transcribe", tags=["Clinical Sessions"])
async def transcribe_and_document(
    audio:      UploadFile = File(...),
    patient_id: str        = "unknown",
    consent:    bool       = True,
    session_type: str      = "consultation",
    current_user: dict     = Depends(get_current_user)
):
    # ── Consent gate (HIPAA) ───────────────────
    if not consent:
        raise HTTPException(status_code=403, detail="Patient consent required (HIPAA)")

    # ── Get patient info for context ───────────
    patient_info = {}
    if patient_id != "unknown":
        p = patients_col.find_one({"patient_id": patient_id}, {"_id": 0})
        if p:
            patient_info = p

    # ── Save audio to temp file ────────────────
    suffix = os.path.splitext(audio.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
        tmp_path = tmp.name

    try:
        # Step 1: Transcribe
        transcription  = transcribe_audio(tmp_path)
        raw_transcript = transcription["transcript"]
        detected_lang  = transcription["detected_language"]
        lang_confidence = transcription["language_confidence"]

        # Step 2: Translate if needed
        english_transcript = translate_if_needed(raw_transcript, detected_lang)

        # Step 3: Generate full SOAP note
        soap_data = generate_full_soap(english_transcript, patient_info)

        # Step 4: Build session record
        session_id = "SES-" + str(uuid.uuid4())[:8].upper()

        session_doc = {
            "session_id":          session_id,
            "patient_id":          patient_id,
            "patient_name":        patient_info.get("full_name", "Unknown"),
            "clinician_id":        current_user["user_id"],
            "clinician_name":      current_user["full_name"],
            "hospital_name":       current_user.get("hospital_name"),
            "audio_filename":      audio.filename,
            "raw_transcript":      raw_transcript,
            "english_transcript":  english_transcript,
            "detected_language":   detected_lang,
            "language_confidence": lang_confidence,
            "session_type":        session_type,
            "soap_note":           soap_data,
            "status":              "completed",
            "created_at":          datetime.utcnow().isoformat(),
            "completed_at":        datetime.utcnow().isoformat()
        }
        sessions_col.insert_one(session_doc)

        # Step 5: Auto-generate prescription if medications prescribed
        prescription_id = None
        if soap_data.get("medications_prescribed"):
            prescription_id = "RX-" + str(uuid.uuid4())[:8].upper()
            rx_doc = {
                "prescription_id": prescription_id,
                "session_id":      session_id,
                "patient_id":      patient_id,
                "patient_name":    patient_info.get("full_name", "Unknown"),
                "clinician_name":  current_user["full_name"],
                "clinician_id":    current_user["user_id"],
                "hospital_name":   current_user.get("hospital_name"),
                "license_number":  current_user.get("license_number"),
                "date":            datetime.utcnow().strftime("%Y-%m-%d"),
                "diagnosis":       soap_data.get("primary_diagnosis", ""),
                "icd_codes":       soap_data.get("icd_codes", []),
                "medications":     soap_data.get("medications_prescribed", []),
                "lab_tests_ordered": soap_data.get("lab_tests_ordered", []),
                "follow_up":       soap_data.get("follow_up", ""),
                "special_notes":   soap_data.get("special_instructions", ""),
                "valid_for_days":  30,
                "created_at":      datetime.utcnow().isoformat()
            }
            scripts_col.insert_one(rx_doc)
            sessions_col.update_one(
                {"session_id": session_id},
                {"$set": {"prescription_id": prescription_id}}
            )

        # Step 6: Audit log
        write_audit(
            "CLINICAL_SESSION_CREATED",
            current_user["user_id"],
            session_id,
            f"Patient: {patient_id}, Lang: {detected_lang}"
        )

        return {
            "session_id":         session_id,
            "prescription_id":    prescription_id,
            "patient_id":         patient_id,
            "detected_language":  detected_lang,
            "raw_transcript":     raw_transcript,
            "english_transcript": english_transcript,
            "soap_note":          soap_data,
            "status":             "completed"
        }

    finally:
        os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════
#  SESSION ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/sessions", tags=["Clinical Sessions"])
def list_sessions(
    patient_id: str = Query(default=""),
    skip:  int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if patient_id:
        query["patient_id"] = patient_id
    sessions = list(sessions_col.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))
    return {"total": len(sessions), "sessions": sessions}


@app.get("/sessions/{session_id}", tags=["Clinical Sessions"])
def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    s = sessions_col.find_one({"session_id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@app.patch("/sessions/{session_id}/review", tags=["Clinical Sessions"])
def mark_reviewed(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    sessions_col.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": "reviewed",
            "reviewed_by": current_user["full_name"],
            "reviewed_at": datetime.utcnow().isoformat()
        }}
    )
    write_audit("SESSION_REVIEWED", current_user["user_id"], session_id)
    return {"message": "Session marked as reviewed"}


# ═══════════════════════════════════════════════════════════
#  PRESCRIPTION ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/prescriptions/{prescription_id}", tags=["Prescriptions"])
def get_prescription(
    prescription_id: str,
    current_user: dict = Depends(get_current_user)
):
    rx = scripts_col.find_one({"prescription_id": prescription_id}, {"_id": 0})
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return rx


@app.get("/prescriptions/patient/{patient_id}", tags=["Prescriptions"])
def get_patient_prescriptions(
    patient_id: str,
    current_user: dict = Depends(get_current_user)
):
    rxs = list(scripts_col.find({"patient_id": patient_id}, {"_id": 0}).sort("date", -1))
    return {"patient_id": patient_id, "total": len(rxs), "prescriptions": rxs}


# ═══════════════════════════════════════════════════════════
#  SYSTEM ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/health", tags=["System"])
def health():
    return {
        "status":  "ok",
        "service": "ClinicalDoc API v2",
        "team":    "ByteForge22"
    }


@app.get("/config", tags=["System"])
def config():
    return {
        "supported_languages":  ["en", "hi", "te", "ta", "ml", "kn", "bn", "mr"],
        "supported_audio":      ["wav", "mp3", "m4a", "ogg", "mp4"],
        "asr_model":            "faster-whisper-small",
        "llm_model":            "llama-3.3-70b-versatile (Groq)",
        "soap_sections":        ["Subjective", "Objective", "Assessment", "Plan"],
        "user_roles":           ["doctor", "nurse", "admin", "receptionist"],
        "session_types":        ["consultation", "follow_up", "emergency"],
        "icd_version":          "ICD-10",
        "compliance":           ["HIPAA", "audit_logging", "consent_gating"]
    }


@app.get("/audit", tags=["System"])
def get_audit_log(
    skip:  int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    logs = list(audit_col.find({}, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit))
    return {"total": len(logs), "logs": logs}