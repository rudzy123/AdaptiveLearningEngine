"""Configuration for the Adaptive Learning Engine data pipeline."""

from __future__ import annotations

from pathlib import Path

# Project roots (adaptive_learning_engine/ is one level below workspace root)
PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

# Data directories
DATA_ROOT = WORKSPACE_ROOT / "learning_engine_data"
MATH_DIR = DATA_ROOT / "math"
PHYSICS_DIR = DATA_ROOT / "physics"
CS_DIR = DATA_ROOT / "cs"
PROBLEMS_DIR = DATA_ROOT / "problems"
PROCESSED_DIR = DATA_ROOT / "processed"

SOURCE_DIRS: dict[str, Path] = {
    "math": MATH_DIR,
    "physics": PHYSICS_DIR,
    "cs": CS_DIR,
    "problems": PROBLEMS_DIR,
}

# Ingestion settings
CHUNK_TARGET_WORDS = 400
CHUNK_MIN_WORDS = 300
CHUNK_MAX_WORDS = 500
CHUNK_OVERLAP_WORDS = 50

# PDF extraction backend: "pymupdf" or "pdfplumber"
PDF_EXTRACTOR = "pymupdf"

# Output storage
OUTPUT_FORMAT = "both"  # "json", "sqlite", or "both"
JSON_OUTPUT_DIR = PROCESSED_DIR / "chunks_json"
SQLITE_DB_PATH = PROCESSED_DIR / "learning_chunks.db"

# Download settings
MIT_OCW_BASE = "https://ocw.mit.edu"
STANFORD_CS161_BASE = "https://stanford-cs161.github.io"
DOWNLOAD_TIMEOUT_SECONDS = 120
DOWNLOAD_MAX_RETRIES = 3
DOWNLOAD_RETRY_BACKOFF_SECONDS = 2.0
DOWNLOAD_MANIFEST_PATH = DATA_ROOT / ".download_manifest.json"
USER_AGENT = (
    "AdaptiveLearningEngine/1.0 (+local educational pipeline; "
    "respects MIT OCW and Stanford open course materials)"
)

# Curriculum engine
CURRICULUM_OUTPUT_DIR = PROCESSED_DIR / "curriculum"
CURRICULUM_JSON_PATH = CURRICULUM_OUTPUT_DIR / "learning_path.json"
TOP_KEYWORDS_PER_MODULE = 8
TOP_CONCEPTS_PER_DOMAIN = 15

# Domain sequencing (cross-subject learning path)
DOMAIN_SEQUENCE = ["math", "physics", "cs", "problems"]

SUBTOPIC_SEQUENCE: dict[str, list[str]] = {
    "physics": ["mechanics", "thermodynamics"],
    "math": ["linear_algebra"],
    "cs": ["algorithms"],
}

# Concept tagging & retrieval
KNOWLEDGE_INDEX_DIR = PROCESSED_DIR / "knowledge"
CONCEPT_GROUPS_JSON = KNOWLEDGE_INDEX_DIR / "concept_groups.json"
MAX_CONCEPTS_PER_CHUNK = 8
MIN_CONCEPT_TAG_SCORE = 0.15
CHUNK_GROUP_MIN_SHARED_CONCEPTS = 2
CHUNK_GROUP_MIN_JACCARD = 0.2
RETRIEVAL_DEFAULT_TOP_K = 10
RETRIEVAL_MIN_SCORE = 0.05
LESSON_MAX_CHUNKS = 14
LESSON_CHUNKS_PER_CONCEPT = 3
LESSON_CHUNKS_PER_WEAK_CONCEPT = 5
WEAK_CONCEPT_SCORE_BOOST = 2.5

# Adaptive learning engine (memory & progression)
ENGINE_DATA_DIR = PROJECT_ROOT / "data"
USER_PROGRESS_DB_PATH = ENGINE_DATA_DIR / "user_progress.db"
EVALUATION_LOGS_DB_PATH = ENGINE_DATA_DIR / "evaluation_logs.db"
SESSION_STATE_DB_PATH = ENGINE_DATA_DIR / "session_state.db"
API_LOGS_DB_PATH = ENGINE_DATA_DIR / "logs.db"

VALID_TOPICS = frozenset({"math", "physics", "cs", "linear_algebra", "algorithms"})

# Deep evaluation scoring thresholds
EVAL_NUMERIC_TOLERANCE = 1e-2
EVAL_PARTIAL_THRESHOLD = 0.5
EVAL_CORRECT_THRESHOLD = 0.7
EVAL_PERFECT_SCORE = 1.0

# Confidence deltas by error type (applied after base update)
CONFIDENCE_DELTA = {
    "conceptual_error": -0.15,
    "calculation_error": -0.06,
    "misinterpretation": -0.12,
    "incomplete_answer": -0.08,
    "guessing": -0.10,
    "none": 0.05,
}

# Progression thresholds
CONFIDENCE_MASTERED = 0.8
CONFIDENCE_PRACTICE = 0.5
CONFIDENCE_ACCELERATE = 0.65  # strong eval can advance below full mastery
RETEACH_FAILURE_THRESHOLD = 3
REPEATED_FAILURE_STREAK = 2  # lower difficulty after this many wrong in a row
STALE_REVIEW_DAYS = 7
STRONG_SCORE_ACCELERATE = 0.7  # evaluation score triggering faster advance

# Logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_LEVEL = "INFO"
