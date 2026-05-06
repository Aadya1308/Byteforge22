from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
from groq import Groq
from dotenv import load_dotenv
import os, json

load_dotenv()

print("Loading Whisper model...")
whisper = WhisperModel("small", device="cpu", compute_type="int8")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def transcribe_audio(audio_path: str) -> dict:
    segments, info = whisper.transcribe(audio_path, beam_size=5)
    transcript = " ".join([seg.text for seg in segments])
    return {
        "transcript":           transcript,
        "detected_language":    info.language,
        "language_confidence":  round(info.language_probability, 2)
    }


def translate_if_needed(transcript: str, detected_lang: str) -> str:
    if detected_lang == "en":
        return transcript
    return GoogleTranslator(source="auto", target="en").translate(transcript)


def generate_full_soap(transcript: str, patient_info: dict = {}) -> dict:
    """Generate complete structured SOAP note with medications, ICD codes, prescription."""

    patient_context = ""
    if patient_info:
        patient_context = f"""
Patient Context:
- Name: {patient_info.get('full_name', 'Unknown')}
- Age: {patient_info.get('age', 'Unknown')}
- Gender: {patient_info.get('gender', 'Unknown')}
- Blood Group: {patient_info.get('blood_group', 'Unknown')}
- Known Allergies: {', '.join(patient_info.get('known_allergies', [])) or 'None'}
- Chronic Conditions: {', '.join(patient_info.get('chronic_conditions', [])) or 'None'}
- Current Medications: {', '.join(patient_info.get('current_medications', [])) or 'None'}
"""

    prompt = f"""You are an expert clinical documentation AI assistant. 
Generate a complete, structured medical SOAP note from the following doctor-patient transcript.
Be thorough, accurate, and medically precise.
Flag any uncertain or unclear fields as [REVIEW REQUIRED].

{patient_context}

TRANSCRIPT:
{transcript}

Return a JSON object with EXACTLY this structure:
{{
  "chief_complaint": "main reason for visit in patient's words",
  "history_of_illness": "detailed history of present illness",
  "symptoms": ["symptom1", "symptom2"],
  "symptom_duration": "how long symptoms have been present",
  "pain_scale": 5,
  "patient_reported_meds": ["any medications patient mentioned taking"],
  "allergies_reported": ["any allergies mentioned"],

  "vital_signs": {{
    "blood_pressure": "120/80 mmHg or null if not mentioned",
    "pulse_rate": "72 bpm or null",
    "temperature": "98.6F or null",
    "respiratory_rate": "16/min or null",
    "oxygen_saturation": "98% or null"
  }},
  "physical_examination": "findings from physical exam if mentioned",
  "lab_results": "any lab results mentioned or null",

  "primary_diagnosis": "main diagnosis",
  "differential_diagnosis": ["other possible diagnoses"],
  "icd_codes": [
    {{
      "code": "ICD-10 code e.g. J06.9",
      "description": "full description",
      "category": "body system category"
    }}
  ],
  "clinical_impression": "overall clinical assessment",
  "severity": "mild or moderate or severe",

  "medications_prescribed": [
    {{
      "name": "medication name",
      "dosage": "e.g. 500mg",
      "frequency": "e.g. twice daily",
      "duration": "e.g. 5 days",
      "route": "oral or IV or topical",
      "instructions": "e.g. take after food"
    }}
  ],
  "procedures": ["any procedures to be done"],
  "lab_tests_ordered": ["CBC", "Blood glucose", etc],
  "imaging_ordered": ["X-ray chest", etc if applicable],
  "referrals": ["refer to cardiologist", etc if needed],
  "lifestyle_advice": ["rest", "increase fluid intake", etc],
  "follow_up": "review after X days",
  "sick_leave_days": 3,
  "diet_instructions": "dietary advice if any",
  "special_instructions": "any special instructions",

  "confidence_score": 0.85,
  "flagged_fields": ["list any fields that are uncertain or need clinician review"]
}}

Return ONLY the JSON. No markdown, no explanation."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a medical AI that generates precise clinical documentation. Always respond with valid JSON only. Never add markdown formatting."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1
    )

    raw = response.choices[0].message.content
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Return safe fallback
        return {
            "chief_complaint": "[REVIEW REQUIRED]",
            "history_of_illness": transcript,
            "symptoms": [],
            "primary_diagnosis": "[REVIEW REQUIRED]",
            "differential_diagnosis": [],
            "icd_codes": [],
            "medications_prescribed": [],
            "lab_tests_ordered": [],
            "follow_up": "[REVIEW REQUIRED]",
            "confidence_score": 0.0,
            "flagged_fields": ["All fields - JSON parse error, manual review needed"]
        }