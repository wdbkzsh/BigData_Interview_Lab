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

export interface ReviewStateSummary {
  mastery_state: string
  next_review_date: string | null
}

export interface QuestionListItem {
  id: string
  title: string | null
  question_type: string
  difficulty: number
  primary_knowledge_point: KnowledgePointRef
  domain: KnowledgePointRef | null
  review_state: ReviewStateSummary | null
  pending_self_assessment_attempt_id: number | null
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
  status: string
  is_correct: boolean | null
  score: number | null
  correct_answer: string | null
  reference_answer: string | null
  explanation: string | null
}

// ---------------------------------------------------------------------------
// Self-Assessment
// ---------------------------------------------------------------------------

export interface SelfAssessmentBody {
  mastery_state: "unmastered" | "vague" | "familiar" | "mastered"
}

export interface ReviewStateSnapshot {
  mastery_state: string
  next_review_date: string
  policy_version: string
}

export interface SelfAssessmentResult {
  attempt_id: number
  status: string
  self_assessed_mastery_state: string
  review_state: ReviewStateSnapshot
}

// ---------------------------------------------------------------------------
// Attempt detail / recovery
// ---------------------------------------------------------------------------

export interface AttemptDetail {
  id: number
  question_id: string
  question_revision: number
  attempt_type: string
  status: string
  answer: string
  self_assessed_mastery_state: string | null
  reference_answer: string | null
  explanation: string | null
}

export interface PendingAttemptItem {
  attempt_id: number
  question_id: string
  created_at: string | null
}

export interface PendingAttemptsResponse {
  short_answer_self_assessment: PendingAttemptItem[]
}

// ---------------------------------------------------------------------------
// ReviewState
// ---------------------------------------------------------------------------

export interface ReviewStateInfo {
  question_id: string
  mastery_state: string | null
  next_review_date: string | null
  review_count: number
  consecutive_successes: number
  review_stage: number | null
  policy_version: string | null
}

export interface ManualMasteryBody {
  mastery_state: "unmastered" | "vague" | "familiar" | "mastered"
}

// ---------------------------------------------------------------------------
// Wrong Book
// ---------------------------------------------------------------------------

export interface WrongBookItem {
  question_id: string
  title: string | null
  question_type: string
  difficulty: number
  primary_knowledge_point_id: string
  primary_knowledge_point_name: string | null
  mastery_state: string | null
  next_review_date: string | null
  wrong_book_mode: string
  has_card: boolean
}

export interface WrongBookResponse {
  items: WrongBookItem[]
  page: number
  page_size: number
  total: number
}

export interface WrongBookPreferenceBody {
  mode: "auto" | "follow" | "ignore"
}

// ---------------------------------------------------------------------------
// Domains
// ---------------------------------------------------------------------------

export interface Domain {
  id: string
  name: string
}