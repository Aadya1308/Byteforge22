# Multilingual AI-Powered Clinical Documentation & Decision Support System

A comprehensive backend system for automating clinical documentation during doctor-patient interactions, converting unstructured multilingual speech into structured medical records.

## Features

- **Real-time Audio Processing**: Capture and evaluate audio quality with consent validation
- **Multilingual ASR**: Whisper-powered speech-to-text with automatic language detection
- **Translation Services**: Support for 8+ languages (English, Spanish, French, German, Hindi, Chinese, Japanese, Arabic)
- **Clinical NLP**: Advanced entity extraction for symptoms, medications, diagnoses, and procedures
- **Knowledge Retrieval**: ICD-10 code suggestions and drug information integration
- **SOAP Note Generation**: Structured clinical documentation with validation
- **HL7 FHIR Integration**: EHR-ready output formats
- **Quality Assurance**: Document validation and hallucination detection

## Architecture

The system implements an 11-step workflow pipeline:

1. **Capture**: Audio stream + patient consent validation
2. **Evaluator/Guardrail**: Consent and audio quality checks
3. **Transcribe**: Whisper ASR with language detection
4. **Condition/Branch**: Translation for non-English content
5. **Extract**: Clinical NLP for entity extraction
6. **Knowledge Retrieval**: Drug database and ICD code lookup
7. **Structure**: SOAP note formatting
8. **Merge**: Combine SOAP, ICD, and entities
9. **Validate**: Hallucination and completeness checks
10. **Format**: HL7 FHIR/JSON output formatting
11. **Deliver**: EHR integration with session memory updates

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Redis (for caching)
- OpenAI API key
- FFmpeg (for audio processing)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd CLINICAL-DOCUMENTATION
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download spaCy models:
```bash
python -m spacy download en_core_web_sm
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. Initialize database:
```bash
# Create PostgreSQL database and run migrations
alembic upgrade head
```

### Running with Docker

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

2. The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, you can access comprehensive API documentation:

- **Swagger UI**: `http://localhost:8000/docs` - Interactive API documentation
- **ReDoc**: `http://localhost:8000/redoc` - Alternative documentation view
- **OpenAPI Schema**: `http://localhost:8000/openapi.json` - Raw API schema

#### Documentation Features:
- **Interactive Testing**: Try API endpoints directly from the browser
- **Request/Response Examples**: Clear examples for all endpoints
- **Schema Validation**: Automatic request validation
- **Authentication Support**: Bearer token authentication
- **Tagged Endpoints**: Organized by functional areas
- **Detailed Descriptions**: Comprehensive endpoint documentation

### Manual Setup

1. Start PostgreSQL and Redis services
2. Run the application:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Audio Processing
- `POST /api/v1/upload-audio` - Upload audio file
- `POST /api/v1/process-workflow` - Process clinical documentation workflow
- `POST /api/v1/process-workflow-async` - Async workflow processing

### Patient Management
- `POST /api/v1/patients` - Create patient record
- `GET /api/v1/patients/{patient_id}` - Get patient information
- `GET /api/v1/patients/{patient_id}/sessions` - Get patient sessions

### Clinical Sessions
- `GET /api/v1/sessions/{session_id}` - Get session details
- `GET /api/v1/sessions/{session_id}/documents` - Get session documents

### Documents
- `GET /api/v1/documents/{document_id}` - Get clinical document

### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/config` - System configuration

## Usage Example

### 1. Upload Audio and Process Workflow

```python
import requests

# Upload audio file
with open("consultation.wav", "rb") as f:
    upload_response = requests.post(
        "http://localhost:8000/api/v1/upload-audio",
        files={"file": f},
        data={
            "patient_id": "PAT123",
            "clinician_id": "DOC456",
            "consent_given": True
        }
    )

# Process workflow
workflow_response = requests.post(
    "http://localhost:8000/api/v1/process-workflow",
    json={
        "audio_file_path": upload_response.json()["file_path"],
        "patient_id": "PAT123",
        "clinician_id": "DOC456",
        "consent_given": True
    }
)

result = workflow_response.json()
print(f"Session ID: {result['session_id']}")
print(f"Status: {result['status']}")
print(f"Document: {result['document']['content']}")
```

### 2. Create Patient Record

```python
patient_response = requests.post(
    "http://localhost:8000/api/v1/patients",
    json={
        "patient_id": "PAT123",
        "name": "John Doe",
        "date_of_birth": "1980-01-15T00:00:00Z",
        "gender": "M",
        "contact_info": "john.doe@email.com"
    }
)
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | - |
| `OPENAI_API_KEY` | OpenAI API key for GPT services | - |
| `WHISPER_MODEL` | Whisper model size | `base` |
| `MAX_FILE_SIZE` | Maximum audio file size (bytes) | `25000000` |
| `SUPPORTED_LANGUAGES` | Supported language codes | `en,es,fr,de,hi,zh,ja,ar` |

### Audio Formats

Supported audio formats:
- WAV
- MP3
- M4A
- FLAC

### Supported Languages

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Hindi (hi)
- Chinese (zh)
- Japanese (ja)
- Arabic (ar)

## Development

### Running Tests

```bash
pytest tests/
```

### Code Structure

```
app/
├── api/v1/          # API endpoints
├── core/            # Configuration and database
├── models/          # Database models
├── schemas/         # Pydantic schemas
├── services/        # Business logic services
└── utils/           # Utility functions
```

### Services Overview

- **WorkflowEngine**: Orchestrates the entire clinical documentation pipeline
- **AudioProcessor**: Handles audio quality evaluation and preprocessing
- **TranscriptionService**: Whisper-based ASR with language detection
- **TranslationService**: Multilingual text translation
- **ClinicalNLPService**: Medical entity extraction
- **KnowledgeRetrievalService**: ICD codes and drug information lookup
- **DocumentStructurer**: SOAP note generation and formatting
- **ValidationService**: Document quality and validation checks
- **EHRIntegrationService**: HL7 FHIR formatting and EHR integration

## Deployment

### AWS Deployment

1. Use ECS/EKS for container orchestration
2. RDS for PostgreSQL
3. ElastiCache for Redis
4. S3 for audio file storage
5. Application Load Balancer for API gateway

### Azure Deployment

1. Azure Container Instances/App Service
2. Azure Database for PostgreSQL
3. Azure Cache for Redis
4. Azure Blob Storage
5. Azure Application Gateway

## Security Considerations

- All audio files are processed with explicit patient consent
- HIPAA-compliant data handling
- Encrypted storage and transmission
- Audit logging for all clinical data access
- Regular security updates and vulnerability scanning

## Performance

- Async processing for workflow steps
- Redis caching for knowledge base data
- Optimized audio processing pipelines
- Database connection pooling
- Horizontal scaling support

## Monitoring

- Health check endpoints
- Performance metrics collection
- Error tracking and alerting
- Workflow execution monitoring
- Resource usage tracking

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Team

**ByteForge22**
- Team Lead: Aadya Kasi Reddy
- Team Members: Vaidya Adithi, Aishani Pureddiwar, Ramavath Poojitha

## Support

For support and inquiries, please contact the development team or create an issue in the repository.
