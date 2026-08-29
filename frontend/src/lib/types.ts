/** TypeScript types matching backend API responses. */

export interface KnowledgePointTreeNode {
  id: string
  name: string
  level: number
  children: KnowledgePointTreeNode[]
}

export interface KnowledgePointDetail {
  id: string
  name: string
  description: string | null
  question_count: number
  has_card: boolean
}

export interface CardProgress {
  status: string // "unread" | "read"
  view_count: number
  last_viewed_at: string | null
}

export interface CardContent {
  title: string
  one_line_definition: string
  core_principle: string
  interview_highlights: string
  common_mistakes: string
}

export interface KnowledgeCard {
  id: string
  knowledge_point_id: string
  revision: number
  content: CardContent
  progress: CardProgress
}