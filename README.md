# ClinicalDoc AI — ByteForge22

> **Real-time multilingual clinical documentation system** that converts doctor-patient audio conversations into structured SOAP notes, ICD-10 coded prescriptions, and EHR-ready records — automatically.

Built by **Team ByteForge22** for Cognizant Technoverse Hackathon 2026.

**Team:** Aadya Kasi Reddy (Lead) · Vaidya Adithi · Aishani Pureddiwar · Ramavath Poojitha

---

## What it does

A doctor records or uploads a consultation audio. The system:

1. Validates patient consent (HIPAA gate)
2. Transcribes speech using **faster-whisper** (local ASR, 8 Indian languages)
3. Translates non-English audio to English via **Llama-3.3-70B on Groq**
4. Generates a structured **SOAP note** (Subjective / Objective / Assessment / Plan) with ICD-10 codes
5. Auto-creates a **prescription** if medications are detected
6. Stores audio on **AWS S3** with presigned URLs, records in **MongoDB Atlas**
7. Generates downloadable **PDF prescriptions** via ReportLab
8. Logs every action to an **audit trail** for HIPAA compliance

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.111 + Uvicorn |
| Speech-to-Text | faster-whisper 1.0.3 (small, CPU, int8) |
| LLM | Llama-3.3-70B-Versatile via Groq API |
| Database | MongoDB Atlas (PyMongo 4.7) |
| Auth | JWT (HS256) + bcrypt via python-jose + passlib |
| Cloud Storage | AWS S3 (boto3) + presigned URLs |
| PDF Generation | ReportLab |
| Data Validation | Pydantic v2 |
| Frontend | React 19 + Vite 8 |

---

## Supported Languages

`en` English · `hi` Hindi · `te` Telugu · `ta` Tamil · `ml` Malayalam · `kn` Kannada · `bn` Bengali · `mr` Marathi

---

## Architecture — 8-Step Pipeline

```
Audio Upload (wav/mp3/m4a/ogg/mp4)
        │
        ▼
[1] Consent Gate (HIPAA) ──✗──► 403 Forbidden
        │ ✓
        ▼
[2] Fetch Patient Context (MongoDB → allergies, chronic conditions, meds)
        │
        ▼
[3] faster-whisper ASR → {transcript, detected_language, language_confidence}
        │
        ▼
[4] Upload audio to S3 → {s3_key, presigned_url (1hr)}
        │
        ▼
[5] Translate if non-English (Llama-3.3-70B via Groq) ──skip if English──►
        │
        ▼
[6] Generate SOAP note (Llama-3.3-70B, temp=0.1, strict JSON schema)
        │
        ▼
[7] structure_soap() → {subjective, objective, assessment, plan, meta}
        │
        ▼
[8] Persist: session → MongoDB
    Auto-create prescription (if medications found) → MongoDB
    Audit log entry → MongoDB
    PDF on demand → ReportLab → S3 (7-day presigned URL)
```

---

## Project Structure

```
Byteforge22/
├── backend/
│   ├── main.py          # FastAPI app, all routes, auth, pipeline orchestration
│   ├── ai.py            # Whisper ASR, Groq LLM calls, translation, SOAP generation
│   ├── models.py        # Pydantic models: UserRegister, PatientCreate, SOAPNote, Prescription...
│   ├── s3.py            # AWS S3 upload, presigned URLs, ReportLab PDF generation
│   └── requirements.txt
├── frontend/
│   └── src/
│       └── App.jsx      # React SPA: Auth, Patients, Transcribe, Sessions, Prescriptions, System
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- AWS account with an S3 bucket (private)
- Groq API key (free tier: [console.groq.com](https://console.groq.com))

---

## Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install boto3 reportlab certifi
```

Create a `.env` file in `backend/`:

```env
MONGO_URL=mongodb+srv://<user>:<password>@cluster.mongodb.net/
SECRET_KEY=your-strong-random-secret-key-here
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=ap-south-1
S3_BUCKET_NAME=your-bucket-name
```

Run the server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. The frontend connects to the backend at `http://127.0.0.1:8000` — ensure the backend is running first.

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Register doctor/nurse/admin/receptionist |
| POST | `/auth/login` | Login (returns JWT bearer token) |
| GET | `/auth/me` | Get current user profile |

### Patients
| Method | Endpoint | Description |
|---|---|---|
| POST | `/patients` | Create patient record |
| GET | `/patients` | List patients (search by name/phone/ID) |
| GET | `/patients/{patient_id}` | Get patient details |
| GET | `/patients/{patient_id}/history` | Get all sessions + prescriptions |

### Clinical Sessions
| Method | Endpoint | Description |
|---|---|---|
| POST | `/sessions/transcribe` | **Core endpoint** — upload audio, get SOAP note |
| GET | `/sessions` | List sessions (filter by patient_id) |
| GET | `/sessions/{session_id}` | Get session with full SOAP note |
| PATCH | `/sessions/{session_id}/review` | Mark session as clinician-reviewed |

### Prescriptions
| Method | Endpoint | Description |
|---|---|---|
| GET | `/prescriptions/{prescription_id}` | Get prescription |
| GET | `/prescriptions/patient/{patient_id}` | All prescriptions for a patient |
| GET | `/prescriptions/{prescription_id}/pdf` | Generate + download PDF (S3 presigned) |

### System
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/config` | Supported languages, models, formats |
| GET | `/audit` | Audit log (admin only) |

---

## SOAP Note Structure

Every transcription returns a structured SOAP note:

```json
{
  "subjective": {
    "chief_complaint": "...",
    "symptoms": ["fever", "headache"],
    "symptom_duration": "3 days",
    "pain_scale": null,
    "patient_reported_meds": [],
    "allergies_reported": []
  },
  "objective": {
    "vital_signs": { "blood_pressure": null, "temperature": "101°F" },
    "physical_examination": "..."
  },
  "assessment": {
    "primary_diagnosis": "Acute upper respiratory infection",
    "icd_codes": [{ "code": "J06.9", "description": "...", "category": "Respiratory" }],
    "severity": "mild"
  },
  "plan": {
    "medications_prescribed": [
      { "name": "Paracetamol", "dosage": "500mg", "frequency": "twice daily", "duration": "5 days", "route": "oral" }
    ],
    "follow_up": "Review after 5 days"
  },
  "meta": {
    "confidence_score": 0.87,
    "flagged_fields": []
  }
}
```

---

## User Roles

| Role | Capabilities |
|---|---|
| `doctor` | Full access — transcribe, create patients, review sessions |
| `nurse` | Create patients, view sessions |
| `admin` | All above + access to audit logs |
| `receptionist` | Create/view patients only |

---

## Security & Compliance

- **Consent gate**: Every transcription requires explicit `consent=True`; returns 403 otherwise
- **JWT auth**: HS256 tokens with 8-hour expiry on all protected routes
- **Password security**: bcrypt hashing via passlib
- **Audit trail**: Every significant action (login, patient create, session create, prescription download) is logged with timestamp, actor, and target
- **Private S3**: Audio and PDFs stored in a private bucket; access only via time-limited presigned URLs (audio: 1hr, PDF: 7 days)
- **Admin-only audit**: `/audit` endpoint returns 403 for non-admin roles

---

## MongoDB Collections

| Collection | Indexed Fields | Purpose |
|---|---|---|
| `users` | `email` (unique) | Clinician accounts |
| `patients` | `patient_id` (unique) | Patient records |
| `sessions` | `session_id` (unique) | Clinical sessions + SOAP notes |
| `prescriptions` | — | Auto-generated prescriptions |
| `audit` | — | Immutable action log |

---

## Environment Variable Reference

| Variable | Required | Description |
|---|---|---|
| `MONGO_URL` | ✓ | MongoDB Atlas connection string |
| `SECRET_KEY` | ✓ | JWT signing secret (use a strong random key) |
| `GROQ_API_KEY` | ✓ | Groq API key for Llama-3.3-70B |
| `AWS_ACCESS_KEY_ID` | ✓ | AWS credentials for S3 |
| `AWS_SECRET_ACCESS_KEY` | ✓ | AWS credentials for S3 |
| `AWS_REGION` | ✓ | S3 bucket region (default: `ap-south-1`) |
| `S3_BUCKET_NAME` | ✓ | Name of your private S3 bucket |

---

## Known Limitations

- Whisper runs on CPU synchronously — not suitable for high concurrency without a task queue (Celery + Redis recommended)
- CORS is currently set to `allow_origins=["*"]` — restrict to frontend domain in production
- Frontend stores JWT in localStorage — consider HttpOnly cookies for production

---

## License

MIT License
