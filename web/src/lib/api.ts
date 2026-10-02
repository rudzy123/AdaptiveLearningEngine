import type { SessionSnapshot, StartTopicParams } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(String(detail), res.status);
  }

  return res.json() as Promise<T>;
}

export async function startTopic(
  params: StartTopicParams
): Promise<SessionSnapshot> {
  return request<SessionSnapshot>("/start_topic", {
    method: "POST",
    body: JSON.stringify({
      user_id: params.user_id ?? "default",
      topic: params.topic,
      level: params.level ?? "beginner",
      problems_per_concept: params.problems_per_concept ?? 3,
      max_concepts: params.max_concepts ?? 8,
    }),
  });
}

export async function getLesson(sessionId: string): Promise<SessionSnapshot> {
  return request<SessionSnapshot>(
    `/get_lesson?session_id=${encodeURIComponent(sessionId)}`
  );
}

export async function getProblem(sessionId: string): Promise<SessionSnapshot> {
  return request<SessionSnapshot>(
    `/get_problem?session_id=${encodeURIComponent(sessionId)}`
  );
}

export async function submitAnswer(
  sessionId: string,
  answer: string
): Promise<SessionSnapshot> {
  return request<SessionSnapshot>("/submit_answer", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, answer }),
  });
}

export async function nextStep(
  sessionId: string
): Promise<SessionSnapshot> {
  return request<SessionSnapshot>(
    `/next_step?session_id=${encodeURIComponent(sessionId)}`,
    { method: "POST" }
  );
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
