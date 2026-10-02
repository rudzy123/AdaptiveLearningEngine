"use client";

import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { checkHealth } from "@/lib/api";

export default function HomePage() {
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth().then(setApiOk);
  }, []);

  return (
    <>
      {apiOk === false && (
        <div
          className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-900"
          role="alert"
        >
          API unreachable. Start the backend:{" "}
          <code className="rounded bg-amber-100 px-1">
            uvicorn api.main:app --reload --port 8000
          </code>
        </div>
      )}
      <DashboardLayout />
    </>
  );
}
