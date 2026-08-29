/** API client — single place for backend URL and fetch helpers. */

import type {
  KnowledgePointTreeNode,
  KnowledgePointDetail,
  KnowledgeCard,
  CardProgress,
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