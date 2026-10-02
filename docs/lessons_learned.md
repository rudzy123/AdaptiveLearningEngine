# Lessons Learned: Building ALE

## 1) Evaluation and generation must be decoupled

A robust adaptive tutor needs **separate generation and evaluation paths**:

- Generation (`lesson_generator`, `problem_generator`) optimizes teaching quality.
- Evaluation (`generation/evaluation.py`) optimizes correctness, diagnosis, and confidence updates.

Keeping these separate prevents prompt/format coupling and improves testability.

## 2) Adaptive systems need durable state first

Session continuity is foundational. Without persistent state, progression quality collapses.

Key decision:

- Persist session state in SQLite (`session_state.db`) for every API call.

Outcome:

- Crash recovery works.
- API behavior is deterministic by state, not process lifetime.

## 3) RAG is strong for grounding, weak for completeness

RAG improves factual grounding and citations, but has limitations:

- Retrieval quality depends on chunk coverage and concept tagging quality.
- Some concepts have sparse chunks, requiring fallback generated explanations.

Mitigation:

- Structured retrieval output (`chunks` + `source` + `score`)
- Citation injection in lessons
- Fallback explanations when chunk retrieval is empty

## 4) Progression must combine multiple signals

Confidence alone is insufficient. ALE progression works best when combining:

- Confidence thresholds
- Error type (`conceptual_error`, `calculation_error`, etc.)
- Consecutive failure streaks

This creates better educational behavior:

- Conceptual errors trigger reteach/simplification.
- Calculation errors trigger more practice.
- Strong confidence advances concept sequence.

## 5) API quality matters as much as model quality

A professional tutoring backend needs:

- Stable REST contracts
- Standard response envelopes
- Predictable errors (never raw crashes)
- Structured observability for debugging and analytics

Result:

- Clients can evolve independently.
- Production incidents are diagnosable from logs and DB records.

## 6) Small, focused modules scale better

Separating `api`, `services`, `engine`, `generation`, and `data` reduced coupling and clarified ownership.

This made it straightforward to:

- add tests,
- enforce validation,
- evolve progression rules,
- and support multiple UIs (CLI, Streamlit, Next.js, REST clients).

