import boto3, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from dotenv import load_dotenv
import tempfile

load_dotenv()

s3 = boto3.client(
    "s3",
    region_name           = os.getenv("AWS_REGION", "ap-south-1"),
    aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
)
BUCKET = os.getenv("S3_BUCKET_NAME")


def upload_audio_to_s3(local_path: str, patient_id: str, filename: str) -> dict:
    """
    Upload audio to private S3 bucket.
    Returns dict with s3_key and a 1-hour presigned URL.

    FIX: previously returned only the s3_key (str) so callers had no URL,
    and main.py never called this function at all — audio was silently dropped.
    Now returns both key + URL so main.py can store them on the session doc.
    """
    s3_key = f"audio/{patient_id}/{filename}"
    s3.upload_file(local_path, BUCKET, s3_key)          # actual upload
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": s3_key},
        ExpiresIn=3600
    )
    return {"s3_key": s3_key, "audio_url": presigned_url}


def get_audio_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a temporary signed URL for audio access (default 1 hour)."""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": s3_key},
        ExpiresIn=expires_in
    )


def generate_prescription_pdf(rx: dict) -> str:
    """Generate PDF prescription and return local path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name

    c = canvas.Canvas(tmp_path, pagesize=A4)
    width, height = A4

    # ── Header ──────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, "MEDICAL PRESCRIPTION")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 90, f"Dr. {rx.get('clinician_name', '')}")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 108, f"Hospital: {rx.get('hospital_name', 'N/A')}")
    c.drawString(50, height - 124, f"License:  {rx.get('license_number', 'N/A')}")
    c.drawString(400, height - 90,  f"Rx ID: {rx.get('prescription_id', '')}")
    c.drawString(400, height - 108, f"Date:  {rx.get('date', '')}")

    c.line(50, height - 135, width - 50, height - 135)

    # ── Patient Info ─────────────────────────────────────────
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 160, "PATIENT DETAILS")
    c.setFont("Helvetica", 10)
    c.drawString(50,  height - 178, f"Name:       {rx.get('patient_name', 'N/A')}")
    c.drawString(300, height - 178, f"Patient ID: {rx.get('patient_id', 'N/A')}")

    # ── Diagnosis ────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 210, "DIAGNOSIS")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 228, rx.get("diagnosis", "N/A"))

    icd_codes = rx.get("icd_codes", [])
    if icd_codes:
        codes_text = ", ".join([f"{i['code']} - {i['description']}" for i in icd_codes])
        c.drawString(50, height - 246, f"ICD-10: {codes_text[:80]}")

    # ── Medications ──────────────────────────────────────────
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 278, "MEDICATIONS PRESCRIBED")
    c.line(50, height - 285, width - 50, height - 285)

    y = height - 305
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50,  y, "Medication")
    c.drawString(220, y, "Dosage")
    c.drawString(290, y, "Frequency")
    c.drawString(390, y, "Duration")
    c.drawString(460, y, "Route")
    y -= 15

    c.setFont("Helvetica", 10)
    for i, med in enumerate(rx.get("medications", []), 1):
        c.drawString(50,  y, f"{i}. {med.get('name', '')}")
        c.drawString(220, y, med.get("dosage", ""))
        c.drawString(290, y, med.get("frequency", ""))
        c.drawString(390, y, med.get("duration", ""))
        c.drawString(460, y, med.get("route", "oral"))
        y -= 18
        if med.get("instructions"):
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(70, y, f"   ↳ {med['instructions']}")
            c.setFont("Helvetica", 10)
            y -= 15

    # ── Lab Tests ────────────────────────────────────────────
    lab_tests = rx.get("lab_tests_ordered", [])
    if lab_tests:
        y -= 10
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "LAB TESTS ORDERED")
        y -= 18
        c.setFont("Helvetica", 10)
        for test in lab_tests:
            c.drawString(60, y, f"• {test}")
            y -= 15

    # ── Follow-up & Notes ────────────────────────────────────
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, f"Follow-up: {rx.get('follow_up', 'N/A')}")
    y -= 18
    if rx.get("special_notes"):
        c.drawString(50, y, f"Notes: {rx.get('special_notes', '')}")

    # ── Footer ───────────────────────────────────────────────
    c.line(50, 80, width - 50, 80)
    c.setFont("Helvetica", 9)
    c.drawString(50, 65, "This prescription is valid for 30 days from the date of issue.")
    c.drawString(50, 50, "Generated by ClinicalDoc AI — ByteForge22")
    c.drawString(width - 200, 65, "Doctor's Signature: _____")

    c.save()
    return tmp_path


def upload_prescription_pdf(rx: dict) -> str:
    """Generate PDF, upload to S3, return 7-day presigned URL."""
    pdf_path = generate_prescription_pdf(rx)
    s3_key   = f"prescriptions/{rx['patient_id']}/{rx['prescription_id']}.pdf"
    s3.upload_file(pdf_path, BUCKET, s3_key)
    os.unlink(pdf_path)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": s3_key},
        ExpiresIn=604800          # 7 days
    )