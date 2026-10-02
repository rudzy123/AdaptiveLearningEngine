"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as api from "@/lib/api";
import type {
  FeedbackData,
  LearnerLevel,
  LessonData,
  PanelPhase,
  ProblemData,
  SessionSnapshot,
  ConceptProgressItem,
} from "@/lib/types";

interface LearningState {
  session: SessionSnapshot | null;
  userInput: string;
  loading: boolean;
  error: string | null;
  transitioning: boolean;
}

interface LearningActions {
  startTopic: (topic: string, level?: LearnerLevel, userId?: string) => Promise<void>;
  loadLesson: () => Promise<void>;
  startProblems: () => Promise<void>;
  submitAnswer: () => Promise<void>;
  nextStep: () => Promise<void>;
  setUserInput: (value: string) => void;
  clearError: () => void;
}

type LearningContextValue = LearningState & LearningActions;

const LearningContext = createContext<LearningContextValue | null>(null);

export function LearningProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [userInput, setUserInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  const run = useCallback(
    async (fn: () => Promise<SessionSnapshot>, resetInput = false) => {
      setLoading(true);
      setError(null);
      try {
        const snap = await fn();
        setSession(snap);
        if (resetInput) setUserInput("");
        if (snap.error) setError(snap.error);
      } catch (e) {
        const msg = e instanceof api.ApiError ? e.message : "Something went wrong";
        setError(msg);
      } finally {
        setLoading(false);
        setTransitioning(false);
      }
    },
    []
  );

  const startTopic = useCallback(
    async (topic: string, level: LearnerLevel = "beginner", userId = "default") => {
      setTransitioning(true);
      await run(() => api.startTopic({ topic, level, user_id: userId }), true);
    },
    [run]
  );

  const loadLesson = useCallback(async () => {
    if (!session?.session_id) return;
    setTransitioning(true);
    await run(() => api.getLesson(session.session_id));
  }, [run, session?.session_id]);

  const startProblems = useCallback(async () => {
    if (!session?.session_id) return;
    setTransitioning(true);
    await run(() => api.getProblem(session.session_id), true);
  }, [run, session?.session_id]);

  const submitAnswer = useCallback(async () => {
    if (!session?.session_id || !userInput.trim()) {
      setError("Please enter an answer.");
      return;
    }
    setTransitioning(true);
    await run(
      () => api.submitAnswer(session.session_id, userInput.trim()),
      false
    );
  }, [run, session?.session_id, userInput]);

  const nextStep = useCallback(async () => {
    if (!session?.session_id) return;
    setTransitioning(true);
    await run(() => api.nextStep(session.session_id), true);
  }, [run, session?.session_id]);

  const value = useMemo<LearningContextValue>(
    () => ({
      session,
      userInput,
      loading,
      error,
      transitioning,
      startTopic,
      loadLesson,
      startProblems,
      submitAnswer,
      nextStep,
      setUserInput,
      clearError: () => setError(null),
    }),
    [
      session,
      userInput,
      loading,
      error,
      transitioning,
      startTopic,
      loadLesson,
      startProblems,
      submitAnswer,
      nextStep,
    ]
  );

  return (
    <LearningContext.Provider value={value}>{children}</LearningContext.Provider>
  );
}

export function useLearning() {
  const ctx = useContext(LearningContext);
  if (!ctx) throw new Error("useLearning must be used within LearningProvider");
  return ctx;
}

export function useLesson(): LessonData | null {
  const { session } = useLearning();
  return session?.lesson ?? null;
}

export function useProblem(): ProblemData | null {
  const { session } = useLearning();
  return session?.problem ?? null;
}

export function useFeedback(): FeedbackData | null {
  const { session } = useLearning();
  return session?.feedback ?? null;
}

export function usePhase(): PanelPhase {
  const { session } = useLearning();
  return session?.phase ?? "setup";
}

export function useConcepts(): ConceptProgressItem[] {
  const { session } = useLearning();
  return session?.concepts ?? [];
}
