/** API client — single place for backend URL and fetch helpers. */

import type {
  KnowledgePointTreeNode,
  KnowledgePointDetail,
  KnowledgeCard,
  CardProgress,
  QuestionListResponse,
  QuestionDetail,
  AttemptSubmitBody,
  AttemptResult,
} from "./types"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(
      body?.detail?.message ?? `API error: ${res.status} ${res.statusText}`
    )
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

/** GET /api/v1/knowledge-points */
export async function fetchKnowledgeTree(): Promise<KnowledgePointTreeNode[]> {
  return apiFetch<KnowledgePointTreeNode[]>("/api/v1/knowledge-points")
}

/** GET /api/v1/knowledge-points/{id} */
export async function fetchKnowledgePointDetail(
  id: string
): Promise<KnowledgePointDetail> {
  return apiFetch<KnowledgePointDetail>(`/api/v1/knowledge-points/${id}`)
}

/** GET /api/v1/knowledge-points/{id}/card */
export async function fetchKnowledgeCard(
  knowledgePointId: string
): Promise<KnowledgeCard> {
  return apiFetch<KnowledgeCard>(
    `/api/v1/knowledge-points/${knowledgePointId}/card`
  )
}

/** POST /api/v1/knowledge-cards/{cardId}/view */
export async function recordCardView(
  cardId: string
): Promise<CardProgress> {
  return apiFetch<CardProgress>(
    `/api/v1/knowledge-cards/${cardId}/view`,
    { method: "POST" }
  )
}

// ---------------------------------------------------------------------------
// Question
// ---------------------------------------------------------------------------

/** GET /api/v1/questions?question_type=choice&page=1&page_size=20 */
export async function fetchQuestions(params: {
  question_type?: string
  page?: number
  page_size?: number
}): Promise<QuestionListResponse> {
  const searchParams = new URLSearchParams()
  if (params.question_type) searchParams.set("question_type", params.question_type)
  if (params.page) searchParams.set("page", String(params.page))
  if (params.page_size) searchParams.set("page_size", String(params.page_size))
  const qs = searchParams.toString()
  return apiFetch<QuestionListResponse>(`/api/v1/questions${qs ? `?${qs}` : ""}`)
}

/** GET /api/v1/questions/{id} */
export async function fetchQuestionDetail(
  questionId: string
): Promise<QuestionDetail> {
  return apiFetch<QuestionDetail>(`/api/v1/questions/${questionId}`)
}

// ---------------------------------------------------------------------------
// Attempt
// ---------------------------------------------------------------------------

/** POST /api/v1/questions/{id}/attempts */
export async function submitAttempt(
  questionId: string,
  body: AttemptSubmitBody
): Promise<AttemptResult> {
  return apiFetch<AttemptResult>(
    `/api/v1/questions/${questionId}/attempts`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  )
}