export type LearnerLevel = "beginner" | "intermediate" | "advanced";
export type PanelPhase =
  | "setup"
  | "lesson"
  | "problem"
  | "feedback"
  | "concept_summary"
  | "done";

export interface ConceptProgressItem {
  concept_id: string;
  label: string;
  confidence: number;
  attempts: number;
  correct: number;
  is_current: boolean;
  is_weak: boolean;
}

export interface LessonData {
  concept_id: string;
  concept_label: string;
  title: string;
  topic: string;
  difficulty: string;
  explanation: string;
  example: string;
  has_pdf: boolean;
  sources: string[];
}

export interface ProblemData {
  problem_id: string;
  concept: string;
  question: string;
  difficulty: string;
  hint: string;
  index: number;
  total: number;
}

export interface FeedbackData {
  correct: boolean;
  score: number;
  mistake_type: string;
  feedback: string;
  hint: string;
  confidence: number;
  confidence_delta: number;
  progression_action: string;
  progression_message: string;
}

export interface SessionSnapshot {
  session_id: string;
  phase: PanelPhase;
  topic: string;
  user_id: string;
  level: string;
  current_concept_id: string;
  current_concept_label: string;
  concept_index: number;
  total_concepts: number;
  problem_index: number;
  problems_per_concept: number;
  problems_correct: number;
  rag_available: boolean;
  progression_action: string;
  concepts: ConceptProgressItem[];
  lesson: LessonData | null;
  problem: ProblemData | null;
  feedback: FeedbackData | null;
  error: string | null;
}

export interface StartTopicParams {
  user_id?: string;
  topic: string;
  level?: LearnerLevel;
  problems_per_concept?: number;
  max_concepts?: number;
}
