from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import uuid


# ═══════════════════════════════════════════════
#  AUTH & USER MODELS
# ═══════════════════════════════════════════════

class UserRegister(BaseModel):
    full_name:    str
    email:        EmailStr
    phone:        str
    password:     str
    role:         str = "doctor"          # doctor | nurse | admin | receptionist
    specialization: Optional[str] = None  # Cardiology, Neurology, etc.
    hospital_name:  Optional[str] = None
    license_number: Optional[str] = None  # Medical license ID

class UserLogin(BaseModel):
    email:    EmailStr
    password: str

class UserResponse(BaseModel):
    user_id:        str
    full_name:      str
    email:          str
    phone:          str
    role:           str
    specialization: Optional[str]
    hospital_name:  Optional[str]
    license_number: Optional[str]
    created_at:     str


# ═══════════════════════════════════════════════
#  PATIENT MODELS
# ═══════════════════════════════════════════════

class PatientCreate(BaseModel):
    full_name:       str
    age:             int
    gender:          str                   # Male | Female | Other
    date_of_birth:   Optional[str] = None
    phone:           Optional[str] = None
    email:           Optional[EmailStr] = None
    address:         Optional[str] = None
    blood_group:     Optional[str] = None  # A+, B-, O+, etc.
    height_cm:       Optional[float] = None
    weight_kg:       Optional[float] = None
    language:        str = "en"            # preferred language
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # Medical history
    known_allergies:       List[str] = []  # penicillin, sulfa, etc.
    chronic_conditions:    List[str] = []  # diabetes, hypertension, etc.
    current_medications:   List[str] = []  # ongoing meds before this visit
    past_surgeries:        List[str] = []
    family_history:        List[str] = []  # heart disease, cancer, etc.
    immunization_history:  List[str] = []
    insurance_provider:    Optional[str] = None
    insurance_id:          Optional[str] = None


# ═══════════════════════════════════════════════
#  CLINICAL DOCUMENTATION MODELS
# ═══════════════════════════════════════════════

class Medication(BaseModel):
    name:        str           # e.g. Paracetamol
    dosage:      str           # e.g. 500mg
    frequency:   str           # e.g. Twice daily
    duration:    str           # e.g. 5 days
    route:       str = "oral"  # oral | IV | topical | inhaled
    instructions: Optional[str] = None  # Take after food

class ICDCode(BaseModel):
    code:        str   # e.g. J06.9
    description: str   # e.g. Acute upper respiratory infection
    category:    str   # e.g. Respiratory

class VitalSigns(BaseModel):
    blood_pressure:    Optional[str] = None   # e.g. 120/80 mmHg
    pulse_rate:        Optional[str] = None   # e.g. 72 bpm
    temperature:       Optional[str] = None   # e.g. 98.6°F
    respiratory_rate:  Optional[str] = None   # e.g. 16/min
    oxygen_saturation: Optional[str] = None   # e.g. 98%
    weight_kg:         Optional[float] = None
    height_cm:         Optional[float] = None
    bmi:               Optional[float] = None

class SOAPNote(BaseModel):
    # S — Subjective (what patient says)
    chief_complaint:        str
    history_of_illness:     str
    symptoms:               List[str] = []
    symptom_duration:       Optional[str] = None
    pain_scale:             Optional[int] = None   # 1-10
    patient_reported_meds:  List[str] = []
    allergies_reported:     List[str] = []

    # O — Objective (what doctor observes)
    vital_signs:            Optional[VitalSigns] = None
    physical_examination:   Optional[str] = None
    lab_results:            Optional[str] = None
    imaging_results:        Optional[str] = None

    # A — Assessment (diagnosis)
    primary_diagnosis:      str
    differential_diagnosis: List[str] = []
    icd_codes:              List[ICDCode] = []
    clinical_impression:    Optional[str] = None
    severity:               Optional[str] = None  # mild | moderate | severe

    # P — Plan (treatment)
    medications_prescribed: List[Medication] = []
    procedures:             List[str] = []
    lab_tests_ordered:      List[str] = []
    imaging_ordered:        List[str] = []
    referrals:              List[str] = []        # refer to specialist
    lifestyle_advice:       List[str] = []
    follow_up:              Optional[str] = None  # e.g. Review after 7 days
    sick_leave_days:        Optional[int] = None
    diet_instructions:      Optional[str] = None
    special_instructions:   Optional[str] = None

    # Meta
    confidence_score:       float = 0.0          # AI confidence 0-1
    flagged_fields:         List[str] = []        # fields needing review
    reviewed_by_clinician:  bool = False


class Prescription(BaseModel):
    prescription_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    patient_id:      str
    session_id:      str
    clinician_name:  str
    hospital_name:   Optional[str] = None
    date:            str
    medications:     List[Medication] = []
    diagnosis:       str
    icd_codes:       List[ICDCode] = []
    follow_up:       Optional[str] = None
    special_notes:   Optional[str] = None
    valid_for_days:  int = 30


# ═══════════════════════════════════════════════
#  SESSION MODEL
# ═══════════════════════════════════════════════

class ClinicalSession(BaseModel):
    session_id:          str
    patient_id:          str
    clinician_id:        str
    clinician_name:      str
    hospital_name:       Optional[str]
    audio_filename:      Optional[str]
    raw_transcript:      Optional[str]
    english_transcript:  Optional[str]
    detected_language:   Optional[str]
    soap_note:           Optional[SOAPNote]
    prescription_id:     Optional[str]
    session_type:        str = "consultation"  # consultation | follow_up | emergency
    status:              str = "pending"       # pending | completed | reviewed
    created_at:          str
    completed_at:        Optional[str]