"use client";

import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { useLearning, usePhase, useProblem } from "@/store/LearningContext";

export function ProblemPanel() {
  const {
    session,
    userInput,
    setUserInput,
    submitAnswer,
    loading,
    transitioning,
    error,
    clearError,
  } = useLearning();
  const problem = useProblem();
  const phase = usePhase();

  if (!session) return null;

  const showProblem =
    phase === "problem" || phase === "feedback" || phase === "concept_summary";
  if (!showProblem) return null;

  if (loading && !problem && phase === "problem") {
    return (
      <Card title="Problem">
        <LoadingSpinner label="Generating problem…" />
      </Card>
    );
  }

  if (!problem) {
    return (
      <Card title="Problem">
        <p className="text-sm text-slate-500">No problem available.</p>
      </Card>
    );
  }

  const canSubmit = phase === "problem" && !loading;

  return (
    <Card
      id="problem"
      title="Practice problem"
      subtitle={`Question ${problem.index} of ${problem.total} · ${problem.difficulty}`}
      className={`animate-slide-up ${transitioning ? "opacity-80" : ""}`}
    >
      <p className="text-base font-medium leading-relaxed text-slate-900">
        {problem.question}
      </p>

      {problem.hint && phase === "problem" && (
        <p className="mt-3 text-sm text-slate-500">
          <span className="font-medium text-slate-600">Hint available</span> after
          you attempt an answer.
        </p>
      )}

      {phase === "problem" && (
        <div className="mt-5 space-y-3">
          <label htmlFor="answer" className="sr-only">
            Your answer
          </label>
          <textarea
            id="answer"
            rows={4}
            value={userInput}
            onChange={(e) => {
              clearError();
              setUserInput(e.target.value);
            }}
            placeholder="Type your answer here…"
            disabled={!canSubmit}
            className="w-full resize-y rounded-lg border border-slate-200 bg-white px-4 py-3 text-[15px] text-slate-900 placeholder:text-slate-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:bg-slate-50"
          />
          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={() => submitAnswer()}
            disabled={!canSubmit || !userInput.trim()}
            className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Submitting…" : "Submit answer"}
          </button>
        </div>
      )}
    </Card>
  );
}
