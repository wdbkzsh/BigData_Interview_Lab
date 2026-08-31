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
  AttemptDetail,
  PendingAttemptsResponse,
  SelfAssessmentBody,
  SelfAssessmentResult,
  ReviewStateInfo,
  ManualMasteryBody,
  WrongBookResponse,
  WrongBookPreferenceBody,
  DashboardData,
  DailyTaskData,
  DailyTaskItem,
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
// Domains
// ---------------------------------------------------------------------------

/** GET /api/v1/domains */
export async function fetchDomains(): Promise<{ id: string; name: string }[]> {
  return apiFetch<{ id: string; name: string }[]>("/api/v1/domains")
}

// ---------------------------------------------------------------------------
// Question
// ---------------------------------------------------------------------------

/** GET /api/v1/questions?question_type=choice&page=1&page_size=20 */
export async function fetchQuestions(params: {
  question_type?: string
  mastery_state?: string
  domain_id?: string
  page?: number
  page_size?: number
}): Promise<QuestionListResponse> {
  const searchParams = new URLSearchParams()
  if (params.question_type) searchParams.set("question_type", params.question_type)
  if (params.mastery_state) searchParams.set("mastery_state", params.mastery_state)
  if (params.domain_id) searchParams.set("domain_id", params.domain_id)
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

// ---------------------------------------------------------------------------
// Self-Assessment / Recovery
// ---------------------------------------------------------------------------

/** GET /api/v1/attempts/{id} */
export async function fetchAttemptDetail(
  attemptId: number
): Promise<AttemptDetail> {
  return apiFetch<AttemptDetail>(`/api/v1/attempts/${attemptId}`)
}

/** GET /api/v1/attempts/pending */
export async function fetchPendingAttempts(): Promise<PendingAttemptsResponse> {
  return apiFetch<PendingAttemptsResponse>("/api/v1/attempts/pending")
}

/** POST /api/v1/attempts/{id}/self-assessment */
export async function submitSelfAssessment(
  attemptId: number,
  body: SelfAssessmentBody
): Promise<SelfAssessmentResult> {
  return apiFetch<SelfAssessmentResult>(
    `/api/v1/attempts/${attemptId}/self-assessment`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  )
}

// ---------------------------------------------------------------------------
// ReviewState
// ---------------------------------------------------------------------------

/** GET /api/v1/questions/{id}/review-state */
export async function fetchReviewState(
  questionId: string
): Promise<ReviewStateInfo> {
  return apiFetch<ReviewStateInfo>(`/api/v1/questions/${questionId}/review-state`)
}

/** PUT /api/v1/questions/{id}/review-state */
export async function updateReviewState(
  questionId: string,
  body: ManualMasteryBody
): Promise<ReviewStateInfo> {
  return apiFetch<ReviewStateInfo>(
    `/api/v1/questions/${questionId}/review-state`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  )
}

// ---------------------------------------------------------------------------
// Wrong Book
// ---------------------------------------------------------------------------

/** GET /api/v1/wrong-book */
export async function fetchWrongBook(params: {
  knowledge_point_id?: string
  question_type?: string
  mastery_state?: string
  page?: number
  page_size?: number
}): Promise<WrongBookResponse> {
  const searchParams = new URLSearchParams()
  if (params.knowledge_point_id) searchParams.set("knowledge_point_id", params.knowledge_point_id)
  if (params.question_type) searchParams.set("question_type", params.question_type)
  if (params.mastery_state) searchParams.set("mastery_state", params.mastery_state)
  if (params.page) searchParams.set("page", String(params.page))
  if (params.page_size) searchParams.set("page_size", String(params.page_size))
  const qs = searchParams.toString()
  return apiFetch<WrongBookResponse>(`/api/v1/wrong-book${qs ? `?${qs}` : ""}`)
}

/** PUT /api/v1/questions/{id}/wrong-book-preference */
export async function setWrongBookPreference(
  questionId: string,
  body: WrongBookPreferenceBody
): Promise<{ question_id: string; mode: string }> {
  return apiFetch<{ question_id: string; mode: string }>(
    `/api/v1/questions/${questionId}/wrong-book-preference`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  )
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

/** GET /api/v1/dashboard */
export async function fetchDashboard(): Promise<DashboardData> {
  return apiFetch<DashboardData>("/api/v1/dashboard")
}

// ---------------------------------------------------------------------------
// DailyTask
// ---------------------------------------------------------------------------

/** GET /api/v1/daily-tasks/today */
export async function fetchTodayTask(): Promise<DailyTaskData> {
  return apiFetch<DailyTaskData>("/api/v1/daily-tasks/today")
}

/** POST /api/v1/daily-task-items/{id}/skip */
export async function skipDailyTaskItem(
  itemId: number
): Promise<DailyTaskItem> {
  return apiFetch<DailyTaskItem>(
    `/api/v1/daily-task-items/${itemId}/skip`,
    { method: "POST" }
  )
}

/** POST /api/v1/daily-task-items/{id}/restore */
export async function restoreDailyTaskItem(
  itemId: number
): Promise<DailyTaskItem> {
  return apiFetch<DailyTaskItem>(
    `/api/v1/daily-task-items/${itemId}/restore`,
    { method: "POST" }
  )
}

// ---------------------------------------------------------------------------
// Question Detail with revision
// ---------------------------------------------------------------------------

/** GET /api/v1/questions/{id}?revision=R */
export async function fetchQuestionDetailAtRevision(
  questionId: string,
  revision?: number
): Promise<QuestionDetail> {
  const qs = revision ? `?revision=${revision}` : ""
  return apiFetch<QuestionDetail>(`/api/v1/questions/${questionId}${qs}`)
}