"use client";

import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { useLearning, useLesson, usePhase } from "@/store/LearningContext";

export function LessonPanel() {
  const { loading, transitioning, startProblems, session } = useLearning();
  const lesson = useLesson();
  const phase = usePhase();

  if (!session) {
    return (
      <Card title="Lesson" subtitle="Select a topic to begin">
        <p className="text-sm text-slate-600">
          Choose Math, Physics, or Computer Science from the sidebar. Your lesson
          will appear here with explanations drawn from course materials when
          available.
        </p>
      </Card>
    );
  }

  if (loading && !lesson) {
    return (
      <Card title="Lesson">
        <LoadingSpinner label="Preparing lesson…" />
      </Card>
    );
  }

  if (!lesson) {
    return (
      <Card title="Lesson">
        <p className="text-sm text-slate-500">No lesson loaded.</p>
      </Card>
    );
  }

  const showStart =
    phase === "lesson" || phase === "concept_summary" || phase === "feedback";

  return (
    <Card
      id="lesson"
      title={lesson.title}
      subtitle={`${lesson.concept_label} · ${lesson.difficulty} · ${lesson.topic}`}
      className={`animate-fade-in ${transitioning ? "opacity-70" : ""}`}
    >
      {lesson.has_pdf && (
        <span className="mb-4 inline-block rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
          PDF-backed content
        </span>
      )}

      <div className="prose prose-slate max-w-none">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Explanation
        </h3>
        <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-slate-700">
          {lesson.explanation}
        </p>

        <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Example
        </h3>
        <div className="mt-2 rounded-lg border border-slate-100 bg-surface-muted p-4 text-[15px] leading-relaxed text-slate-700">
          {lesson.example}
        </div>

        {lesson.sources.length > 0 && (
          <>
            <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Sources
            </h3>
            <ul className="mt-2 list-inside list-disc text-sm text-slate-600">
              {lesson.sources.map((s, i) => (
                <li key={i} className="truncate">
                  {s}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {showStart && phase === "lesson" && (
        <div className="mt-6 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={() => startProblems()}
            disabled={loading}
            className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-50"
          >
            Start practice problems
          </button>
        </div>
      )}
    </Card>
  );
}
