"use client";

import { useConcepts, useLearning } from "@/store/LearningContext";

const TOPICS = [
  { id: "math", label: "Math", sub: "Linear algebra" },
  { id: "physics", label: "Physics", sub: "Mechanics & thermo" },
  { id: "cs", label: "Computer Science", sub: "Algorithms" },
];

function confidenceColor(confidence: number, isWeak: boolean): string {
  if (isWeak) return "bg-amber-500";
  if (confidence >= 0.8) return "bg-emerald-500";
  if (confidence >= 0.5) return "bg-blue-500";
  return "bg-slate-300";
}

export function Sidebar() {
  const {
    session,
    loading,
    startTopic,
    error,
  } = useLearning();
  const concepts = useConcepts();

  const activeTopic = session?.topic;

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Adaptive Learning
        </p>
        <h1 className="mt-1 text-lg font-semibold text-slate-900">
          Study dashboard
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p className="mb-2 px-1 text-xs font-medium uppercase text-slate-400">
          Topics
        </p>
        <nav className="space-y-1">
          {TOPICS.map((t) => {
            const isActive = activeTopic === t.id;
            return (
              <button
                key={t.id}
                type="button"
                disabled={loading}
                onClick={() => startTopic(t.id)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                  isActive
                    ? "bg-accent-soft text-accent ring-1 ring-accent/20"
                    : "text-slate-700 hover:bg-slate-50"
                } disabled:opacity-50`}
              >
                <span className="block text-sm font-medium">{t.label}</span>
                <span className="block text-xs text-slate-500">{t.sub}</span>
              </button>
            );
          })}
        </nav>

        {session && concepts.length > 0 && (
          <>
            <p className="mb-2 mt-6 px-1 text-xs font-medium uppercase text-slate-400">
              Concept progress
            </p>
            <ul className="space-y-2">
              {concepts.map((c) => (
                <li
                  key={c.concept_id}
                  className={`rounded-lg px-3 py-2 ${
                    c.is_current
                      ? "bg-slate-900 text-white"
                      : c.is_weak
                        ? "bg-amber-50 ring-1 ring-amber-200"
                        : "bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`truncate text-sm font-medium ${
                        c.is_current ? "text-white" : "text-slate-800"
                      }`}
                    >
                      {c.label}
                    </span>
                    <span
                      className={`text-xs tabular-nums ${
                        c.is_current ? "text-slate-300" : "text-slate-500"
                      }`}
                    >
                      {c.attempts > 0
                        ? `${Math.round(c.confidence * 100)}%`
                        : "—"}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-black/10">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${confidenceColor(
                        c.confidence,
                        c.is_weak && !c.is_current
                      )}`}
                      style={{
                        width: `${Math.max(c.attempts ? c.confidence * 100 : 0, c.is_current ? 8 : 0)}%`,
                      }}
                    />
                  </div>
                  {c.is_weak && !c.is_current && (
                    <p className="mt-1 text-[10px] font-medium uppercase text-amber-700">
                      Weak area
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {error && (
        <div className="mx-4 mb-4 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      {session && (
        <div className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
          <p>
            Unit {session.concept_index + 1} / {session.total_concepts}
          </p>
          <p className="mt-0.5 capitalize">Phase: {session.phase.replace("_", " ")}</p>
        </div>
      )}
    </aside>
  );
}
