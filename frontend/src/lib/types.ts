/** TypeScript types matching backend API responses. */

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Question
// ---------------------------------------------------------------------------

export interface QuestionListItem {
  id: string
  title: string | null
  question_type: string
  difficulty: number
}

export interface QuestionListResponse {
  items: QuestionListItem[]
  page: number
  page_size: number
  total: number
}

export interface ChoiceOption {
  key: string
  text: string
}

export interface KnowledgePointRef {
  id: string
  name: string | null
}

export interface QuestionDetail {
  id: string
  revision: number
  question_type: string
  difficulty: number
  primary_knowledge_point: KnowledgePointRef
  content: string | null
  options: ChoiceOption[] | null
  // SQL fields (not used in choice flow, but part of backend schema)
  table_schema?: string | null
  field_description?: string | null
  business_requirement?: string | null
}

// ---------------------------------------------------------------------------
// Attempt
// ---------------------------------------------------------------------------

export interface AttemptSubmitBody {
  question_revision: number
  attempt_type: "new" | "review" | "practice"
  client_request_id: string
  answer: string
}

export interface AttemptResult {
  attempt_id: number
  question_id: string
  question_revision: number
  answer: string
  is_correct: boolean | null
  score: number | null
  correct_answer: string | null
  explanation: string | null
}