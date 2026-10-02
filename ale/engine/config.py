"""Paths and tunables. Everything is local; there are no API keys or endpoints here."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
FIXTURE_CORPUS_DIR = DATA_DIR / "corpus"
CURRICULUM_PATH = DATA_DIR / "curriculum.json"


def default_db_path() -> Path:
    """Learner database location. Override with the ALE_DB environment variable."""
    return Path(os.environ.get("ALE_DB", "data/ale.db"))


# Confidence model ---------------------------------------------------------
INITIAL_CONFIDENCE = 0.2
LEARNING_RATE_EARLY = 0.6  # first attempts on a concept move confidence quickly
LEARNING_RATE_LATE = 0.4  # later attempts move it more slowly
EARLY_ATTEMPTS = 3

# Evaluation ---------------------------------------------------------------
PASS_SCORE = 0.7
EXACT_WEIGHT = 0.85
REASONING_WEIGHT = 0.15
PARTIAL_CAP = 0.9  # full key-point coverage without an exact match scores 0.9 before weighting

# Progression thresholds ---------------------------------------------------
ADVANCE_CONFIDENCE = 0.8
PRACTICE_CONFIDENCE = 0.5
FAILURE_STREAK_RETEACH = 3
MAX_DIFFICULTY = 3
MIN_DIFFICULTY = 1
MASTERED_CONFIDENCE = ADVANCE_CONFIDENCE

# Retrieval ----------------------------------------------------------------
BM25_K1 = 1.5
BM25_B = 0.75
CHUNK_WORDS = 140
