"use client";

import { Card } from "@/components/ui/Card";
import { useFeedback, useLearning, usePhase } from "@/store/LearningContext";

export function FeedbackPanel() {
  const { nextStep, loading, session, transitioning } = useLearning();
  const feedback = useFeedback();
  const phase = usePhase();

  if (!session || !feedback) return null;
  if (phase !== "feedback" && phase !== "concept_summary") return null;

  const isCorrect = feedback.correct;
  const border = isCorrect
    ? "border-emerald-200 ring-1 ring-emerald-100"
    : "border-red-200 ring-1 ring-red-100";
  const headerBg = isCorrect ? "bg-emerald-50" : "bg-red-50";
  const headerText = isCorrect ? "text-emerald-800" : "text-red-800";

  return (
    <Card
      id="feedback"
      className={`animate-slide-up ${border} ${transitioning ? "opacity-80" : ""}`}
    >
      <div
        className={`-mx-6 -mt-6 mb-4 rounded-t-xl px-6 py-4 ${headerBg}`}
      >
        <p className={`text-lg font-semibold ${headerText}`}>
          {isCorrect ? "Correct" : "Incorrect"}
        </p>
        <p className={`mt-1 text-sm ${isCorrect ? "text-emerald-700" : "text-red-700"}`}>
          Score {Math.round(feedback.score * 100)}% · {feedback.mistake_type}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-medium uppercase text-slate-400">
            Confidence
          </dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">
            {Math.round(feedback.confidence * 100)}%
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase text-slate-400">
            Change
          </dt>
          <dd
            className={`mt-0.5 text-lg font-semibold tabular-nums ${
              feedback.confidence_delta >= 0
                ? "text-emerald-600"
                : "text-red-600"
            }`}
          >
            {feedback.confidence_delta >= 0 ? "+" : ""}
            {feedback.confidence_delta.toFixed(2)}
          </dd>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <dt className="text-xs font-medium uppercase text-slate-400">
            Error type
          </dt>
          <dd className="mt-0.5 text-sm font-medium capitalize text-slate-800">
            {feedback.mistake_type.replace(/_/g, " ")}
          </dd>
        </div>
      </dl>

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-slate-700">Explanation</h3>
        <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-slate-600">
          {feedback.feedback}
        </p>
      </div>

      {feedback.hint && (
        <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50/80 p-4">
          <h3 className="text-sm font-semibold text-amber-900">Hint</h3>
          <p className="mt-1 text-sm text-amber-800">{feedback.hint}</p>
        </div>
      )}

      {feedback.progression_message && (
        <p className="mt-4 text-sm text-slate-500">
          <span className="font-medium text-slate-700">Next:</span>{" "}
          {feedback.progression_action} — {feedback.progression_message}
        </p>
      )}

      <div className="mt-6 border-t border-slate-100 pt-4">
        <button
          type="button"
          onClick={() => nextStep()}
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {loading
            ? "Loading…"
            : phase === "concept_summary"
              ? "Continue to next concept"
              : "Next problem →"}
        </button>
      </div>
    </Card>
  );
}
