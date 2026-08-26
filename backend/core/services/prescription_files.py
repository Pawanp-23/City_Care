"""PDF generation, Cloudinary upload, and safe text extraction for prescriptions."""
from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path
import time
from urllib import error, request

from fastapi import HTTPException, status

from core.config import settings

LOCAL_PRESCRIPTIONS = Path(__file__).resolve().parents[2] / "data" / "prescriptions"


def build_prescription_pdf(*, patient_name: str, doctor_name: str, diagnosis: str, medicines: list[str], instructions: str) -> bytes:
    """Build a small valid PDF without making the clinical path package-dependent."""
    lines = [
        "CityCare Clinic - Prescription", "", f"Patient: {patient_name}",
        f"Doctor: Dr. {doctor_name}", "", f"Diagnosis: {diagnosis}", "", "Medicines:",
        *[f"- {medicine}" for medicine in medicines or ["No medicines listed"]],
        "", "Instructions:",
        *[part for line in instructions.splitlines() or [instructions] for part in _wrap(line, 88)],
    ]
    commands = ["BT", "/F1 12 Tf", "50 790 Td", "15 TL"]
    for line in lines:
        safe = line.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend((f"({safe}) Tj", "T*"))
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = BytesIO(); output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(output.tell()); output.write(f"{number} 0 obj\n".encode()); output.write(obj); output.write(b"\nendobj\n")
    xref = output.tell(); output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return output.getvalue()


def _wrap(value: str, width: int) -> list[str]:
    return [value[index:index + width] for index in range(0, len(value), width)] or [""]


def upload_pdf_to_cloudinary(pdf: bytes, public_id: str) -> tuple[str, str]:
    if not all((settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)):
        # Local development remains usable without a third-party account. Files
        # are not served statically; the patient-authorized download route is
        # still the only read path.
        LOCAL_PRESCRIPTIONS.mkdir(parents=True, exist_ok=True)
        filename = hashlib.sha256(public_id.encode("utf-8")).hexdigest() + ".pdf"
        (LOCAL_PRESCRIPTIONS / filename).write_bytes(pdf)
        return f"local:{filename}", f"local:{filename}"
    timestamp = str(int(time.time()))
    signature = hashlib.sha1(f"public_id={public_id}&timestamp={timestamp}{settings.cloudinary_api_secret}".encode("utf-8")).hexdigest()
    boundary = "----CityCarePrescriptionUpload"
    fields = {"public_id": public_id, "timestamp": timestamp, "api_key": settings.cloudinary_api_key, "signature": signature}
    body: list[bytes] = []
    for name, value in fields.items():
        body.extend((f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(), value.encode(), b"\r\n"))
    body.extend((f"--{boundary}\r\n".encode(), b'Content-Disposition: form-data; name="file"; filename="citycare-prescription.pdf"\r\n', b"Content-Type: application/pdf\r\n\r\n", pdf, b"\r\n", f"--{boundary}--\r\n".encode()))
    endpoint = f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/raw/upload"
    try:
        with request.urlopen(request.Request(endpoint, data=b"".join(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST"), timeout=20) as response:
            import json
            result = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Prescription storage is temporarily unavailable. Please try again.") from exc
    if not result.get("secure_url") or not result.get("public_id"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Prescription storage returned an invalid response.")
    return str(result["secure_url"]), str(result["public_id"])


def read_local_pdf(reference: str) -> bytes | None:
    """Return a local development PDF without allowing a path traversal."""
    if not reference.startswith("local:"):
        return None
    filename = reference.removeprefix("local:")
    if Path(filename).name != filename or not filename.endswith(".pdf"):
        return None
    path = LOCAL_PRESCRIPTIONS / filename
    return path.read_bytes() if path.is_file() else None


def extract_attachment_text(filename: str, contents: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PDF document support is not installed. Install backend requirements first.") from exc
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(contents)).pages).strip()
    if suffix in {".txt", ".md", ".csv"}:
        return contents.decode("utf-8").strip()
    raise HTTPException(status_code=400, detail="Attachments must be PDF, TXT, MD, or CSV files.")
