const BASE = "/api";

export interface Pile {
  id: string;
  name: string;
  watch_folder_path: string | null;
  created_at: string;
}

export interface DocumentRead {
  id: string;
  pile_id: string;
  filename: string;
  mime_type: string;
  doc_type: string | null;
  content_hash: string;
  ingested_at: string;
}

export interface RunRead {
  id: string;
  pile_id: string;
  status: string;
  thread_id: string;
  started_at: string;
  completed_at: string | null;
}

export interface PendingReviewItem {
  id: string;
  pile_id: string;
  item_type: "conflict" | "finding";
  payload: {
    description: string;
    citations: string[];
    conflict_type?: string;
    conflict_id?: string;
    rule_text?: string;
    finding_id?: string;
  };
  status: string;
  reviewer: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface Rule {
  id: string;
  pile_id: string;
  rule_text: string;
  source: string | null;
  created_at: string;
}

export interface DeliverableSection {
  section_key: string;
  content: string;
  version: number;
  citations: string[];
  updated_at: string;
}

export interface RunStage {
  stage_name: string;
  total_duration_ms: number;
  call_count: number;
  tokens_used: number | null;
  cost_estimate: number | null;
}

export interface RunStages {
  run_id: string;
  status: string;
  total_duration_ms: number;
  stages: RunStage[];
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: isFormData ? undefined : { "Content-Type": "application/json", ...(options?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  createPile: (name: string) =>
    request<Pile>("/piles", { method: "POST", body: JSON.stringify({ name }) }),
  uploadDocument: (pileId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentRead>(`/piles/${pileId}/documents`, { method: "POST", body: form });
  },
  startRun: (pileId: string, llmProvider?: string) =>
    request<RunRead>(`/piles/${pileId}/runs`, {
      method: "POST",
      body: JSON.stringify({ llm_provider: llmProvider ?? null }),
    }),
  submitRule: (pileId: string, ruleText: string) =>
    request<Rule>(`/piles/${pileId}/rules`, { method: "POST", body: JSON.stringify({ rule_text: ruleText }) }),
  listRules: (pileId: string) => request<Rule[]>(`/piles/${pileId}/rules`),
  startExamine: (pileId: string, llmProvider?: string) =>
    request<RunRead>(`/piles/${pileId}/examine`, {
      method: "POST",
      body: JSON.stringify({ llm_provider: llmProvider ?? null }),
    }),
  listReview: (pileId: string) => request<PendingReviewItem[]>(`/piles/${pileId}/review`),
  approve: (itemId: string, reviewer: string) =>
    request<PendingReviewItem>(`/review/${itemId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reviewer }),
    }),
  reject: (itemId: string, reviewer: string) =>
    request<PendingReviewItem>(`/review/${itemId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reviewer }),
    }),
  getDeliverable: (pileId: string) => request<DeliverableSection[]>(`/piles/${pileId}/deliverable`),
  getRunStages: (runId: string) => request<RunStages>(`/runs/${runId}/stages`),
};
