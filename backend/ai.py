from faster_whisper import WhisperModel
from groq import Groq
from dotenv import load_dotenv
import os, json

load_dotenv()

print("Loading Whisper model...")
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")  # FIX 1: renamed to whisper_model
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def call_llm(prompt: str) -> str:
    """Helper to call Groq LLM."""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a medical AI assistant. Follow instructions exactly."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()


def transcribe_audio(audio_path: str) -> dict:
    segments, info = whisper_model.transcribe(audio_path)  # FIX 2: use whisper_model not model

    transcript = " ".join([s.text for s in segments])
    return {
        "transcript": transcript,
        "detected_language": info.language,
        "language_confidence": round(info.language_probability, 3)
    }


def translate_if_needed(transcript: str, detected_lang: str) -> str:
    if detected_lang == "en":
        return transcript  # already English, skip

    # FIX 3: proper translation prompt that works for ALL languages (mr, hi, te, ta, kn, bn, ml, etc.)
    lang_names = {
        "mr": "Marathi", "hi": "Hindi", "te": "Telugu", "ta": "Tamil",
        "kn": "Kannada", "bn": "Bengali", "ml": "Malayalam", "gu": "Gujarati",
        "pa": "Punjabi", "ur": "Urdu"
    }
    lang_name = lang_names.get(detected_lang, detected_lang.upper())

    prompt = f"""You are a certified medical interpreter.
Translate the following clinical conversation from {lang_name} to fluent English.

Rules:
- Provide a proper English TRANSLATION, NOT transliteration
- Do NOT write {lang_name} words in English letters (e.g. do not write "paracetamol getalo" — write "took paracetamol")
- Preserve all medical terms, symptoms, and medication names accurately
- Keep the conversational doctor-patient format intact
- If a word is already in English (like a medicine name), keep it as-is

{lang_name} text:
{transcript}

Return only the English translation, nothing else."""

    return call_llm(prompt)


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

{patient_context}

TRANSCRIPT:
{transcript}

Rules:
- Extract ONLY what is explicitly stated or clearly implied in the transcript
- Use null for fields not mentioned — NEVER use "[REVIEW REQUIRED]" or any placeholder strings
- Infer reasonable values where clinically appropriate:
  e.g. if patient says "throat pain for 3 days" → symptom_duration = "3 days"
  e.g. if patient says "fever" → add "fever" to symptoms
- Always provide differential_diagnosis based on symptoms even if doctor didn't mention them
- Always suggest relevant icd_codes based on the diagnosis
- For vital_signs: use null for each field not mentioned (do NOT write "null if not mentioned" as a string)
- confidence_score: float between 0.0 and 1.0 based on how complete the transcript is
- flagged_fields: list fields the doctor should double-check, empty array [] if nothing to flag

Return a JSON object with EXACTLY this structure:
{{
  "chief_complaint": "main reason for visit in patient's words",
  "history_of_illness": "detailed history of present illness",
  "symptoms": ["symptom1", "symptom2"],
  "symptom_duration": "how long symptoms have been present or null",
  "pain_scale": null,
  "patient_reported_meds": ["any medications patient mentioned taking"],
  "allergies_reported": [],

  "vital_signs": {{
    "blood_pressure": null,
    "pulse_rate": null,
    "temperature": null,
    "respiratory_rate": null,
    "oxygen_saturation": null
  }},
  "physical_examination": null,
  "lab_results": null,
  "imaging_results": null,

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
  "procedures": [],
  "lab_tests_ordered": [],
  "imaging_ordered": [],
  "referrals": [],
  "lifestyle_advice": [],
  "follow_up": "review after X days or null",
  "sick_leave_days": null,
  "diet_instructions": null,
  "special_instructions": null,

  "confidence_score": 0.85,
  "flagged_fields": []
}}

Return ONLY the JSON. No markdown, no explanation, no ```json fences."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a medical AI that generates precise clinical documentation. Always respond with valid JSON only. Never add markdown formatting. Never use placeholder strings like [REVIEW REQUIRED]."
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
        # Safe fallback — no [REVIEW REQUIRED] strings
        return {
            "chief_complaint": None,
            "history_of_illness": transcript,
            "symptoms": [],
            "symptom_duration": None,
            "pain_scale": None,
            "patient_reported_meds": [],
            "allergies_reported": [],
            "vital_signs": {
                "blood_pressure": None,
                "pulse_rate": None,
                "temperature": None,
                "respiratory_rate": None,
                "oxygen_saturation": None
            },
            "physical_examination": None,
            "lab_results": None,
            "imaging_results": None,
            "primary_diagnosis": None,
            "differential_diagnosis": [],
            "icd_codes": [],
            "clinical_impression": None,
            "severity": None,
            "medications_prescribed": [],
            "procedures": [],
            "lab_tests_ordered": [],
            "imaging_ordered": [],
            "referrals": [],
            "lifestyle_advice": [],
            "follow_up": None,
            "sick_leave_days": None,
            "diet_instructions": None,
            "special_instructions": None,
            "confidence_score": 0.0,
            "flagged_fields": ["JSON parse error — manual review needed"]
        }