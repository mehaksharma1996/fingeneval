import type { Dashboard, DemoContext, Run, RunDetail } from "./types";

const API = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init);
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ message: response.statusText }));
    throw new Error(body.message ?? body.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

function auth(userId: string): HeadersInit {
  return { "Content-Type": "application/json", "X-User-Id": userId };
}

export const api = {
  bootstrap: () =>
    request<DemoContext>("/api/v1/demo/bootstrap", { method: "POST" }),
  dashboard: (userId: string) =>
    request<Dashboard>("/api/v1/dashboard", { headers: auth(userId) }),
  createRun: (projectId: string, userId: string) =>
    request<Run>(`/api/v1/projects/${projectId}/runs`, {
      method: "POST",
      headers: {
        ...auth(userId),
        "Idempotency-Key": `web-${crypto.randomUUID()}`,
      },
    }),
  run: (runId: string, userId: string) =>
    request<RunDetail>(`/api/v1/runs/${runId}`, { headers: auth(userId) }),
  review: (
    decisionId: string,
    userId: string,
    action: "APPROVE" | "REJECT" | "OVERRIDE",
    justification: string,
  ) =>
    request(`/api/v1/release-decisions/${decisionId}/reviews`, {
      method: "POST",
      headers: auth(userId),
      body: JSON.stringify({ action, justification }),
    }),
  remediate: (findingId: string, userId: string, ownerUserId: string) =>
    request<{ rerun: Run }>(
      `/api/v1/findings/${findingId}/remediate-and-rerun`,
      {
        method: "POST",
        headers: auth(userId),
        body: JSON.stringify({
          description:
            "Bind deadline claims to approved retrieved evidence and reject unsupported numeric assertions.",
          owner_user_id: ownerUserId,
        }),
      },
    ),
  report: (runId: string, userId: string) =>
    request<{ object_key: string; content_sha256: string }>(
      `/api/v1/runs/${runId}/reports`,
      {
        method: "POST",
        headers: auth(userId),
      },
    ),
};
