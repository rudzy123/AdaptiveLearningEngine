"use client";

import { Sidebar } from "@/components/Sidebar";
import { LessonPanel } from "@/components/LessonPanel";
import { ProblemPanel } from "@/components/ProblemPanel";
import { FeedbackPanel } from "@/components/FeedbackPanel";
import { useLearning, usePhase } from "@/store/LearningContext";

export function DashboardLayout() {
  const { session, loading } = useLearning();
  const phase = usePhase();

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />
      <main className="flex flex-1 flex-col overflow-hidden">
        <header className="shrink-0 border-b border-slate-200 bg-white px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-900">
                {session
                  ? session.current_concept_label || "Learning session"
                  : "Welcome"}
              </h2>
              <p className="text-sm text-slate-500">
                {session
                  ? `${session.topic} · ${session.level} · ${
                      session.problems_correct
                    }/${session.problems_per_concept} correct this unit`
                  : "Structured lessons and adaptive practice"}
              </p>
            </div>
            {loading && (
              <span className="text-sm text-slate-400">Updating…</span>
            )}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-8 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            <LessonPanel />
            <ProblemPanel />
            <FeedbackPanel />

            {session?.phase === "done" && (
              <div className="animate-fade-in rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center">
                <p className="text-lg font-semibold text-emerald-900">
                  Session complete
                </p>
                <p className="mt-1 text-sm text-emerald-700">
                  Pick another topic in the sidebar to continue learning.
                </p>
              </div>
            )}

            {session?.phase === "concept_summary" && phase !== "feedback" && (
              <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">
                Concept finished. Review feedback above, then continue.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
