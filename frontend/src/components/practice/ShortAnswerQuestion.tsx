"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  fetchQuestionDetailAtRevision,
  submitAttempt,
  fetchAttemptDetail,
  submitSelfAssessment,
} from "@/lib/api"
import type {
  QuestionDetail,
  AttemptResult,
  AttemptDetail,
  SelfAssessmentResult,
} from "@/lib/types"
import styles from "./ShortAnswerQuestion.module.css"

interface Props {
  questionId: string
  revision?: number
  attemptType?: "new" | "review" | "practice"
  pendingAttemptId?: number | null
  onDone: () => void
}

const DIFFICULTY_LABELS: Record<number, string> = {
  1: "★",
  2: "★★",
  3: "★★★",
  4: "★★★★",
  5: "★★★★★",
}

const SA_OPTIONS = [
  { value: "unmastered" as const, label: "不会" },
  { value: "vague" as const, label: "模糊" },
  { value: "familiar" as const, label: "基本掌握" },
  { value: "mastered" as const, label: "熟练掌握" },
]

type Phase =
  | "loading"
  | "loaded"
  | "submitting"
  | "awaiting_sa"
  | "submitting_sa"
  | "completed"
  | "error"

export default function ShortAnswerQuestion({
  questionId,
  revision,
  attemptType = "practice",
  pendingAttemptId,
  onDone,
}: Props) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null)
  const [phase, setPhase] = useState<Phase>("loading")
  const [error, setError] = useState<string | null>(null)

  const [userAnswer, setUserAnswer] = useState("")
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null)
  const [saResult, setSaResult] = useState<SelfAssessmentResult | null>(null)

  // Frozen payload for retry
  const frozenPayloadRef = useRef<{
    question_revision: number
    answer: string
    client_request_id: string
  } | null>(null)

  const [clientRequestId] = useState(() => crypto.randomUUID())

  // Load question detail (optionally at specific revision)
  const loadQuestion = useCallback((id: string, rev?: number) => {
    setPhase("loading")
    setError(null)
    fetchQuestionDetailAtRevision(id, rev)
      .then((data) => {
        setQuestion(data)
        setPhase("loaded")
      })
      .catch((err) => {
        setError(err.message)
        setPhase("error")
      })
  }, [])

  // Recover pending attempt
  const recoverAttempt = useCallback((attemptId: number) => {
    setPhase("loading")
    setError(null)
    fetchAttemptDetail(attemptId)
      .then((detail) => {
        // Load question detail for display (at the revision the attempt was made)
        fetchQuestionDetailAtRevision(detail.question_id, detail.question_revision)
          .then((q) => {
            setQuestion(q)
            setUserAnswer(detail.answer)
            setAttemptResult({
              attempt_id: detail.id,
              question_id: detail.question_id,
              question_revision: detail.question_revision,
              answer: detail.answer,
              status: detail.status,
              is_correct: null,
              score: null,
              correct_answer: null,
              reference_answer: detail.reference_answer,
              explanation: detail.explanation,
            })
            setPhase("awaiting_sa")
          })
          .catch((err) => {
            setError(err.message)
            setPhase("error")
          })
      })
      .catch((err) => {
        setError(err.message)
        setPhase("error")
      })
  }, [])

  // Initialize: either recover pending or load question
  useEffect(() => {
    if (pendingAttemptId) {
      recoverAttempt(pendingAttemptId)
    } else {
      loadQuestion(questionId, revision)
    }
  }, [questionId, revision, pendingAttemptId, loadQuestion, recoverAttempt])

  // Submit answer
  const handleSubmit = async () => {
    if (!question || !userAnswer.trim()) return

    if (!frozenPayloadRef.current) {
      frozenPayloadRef.current = {
        question_revision: question.revision,
        answer: userAnswer,
        client_request_id: clientRequestId,
      }
    }

    const payload = frozenPayloadRef.current
    setPhase("submitting")
    setError(null)

    try {
      const result = await submitAttempt(question.id, {
        question_revision: payload.question_revision,
        attempt_type: attemptType,
        client_request_id: payload.client_request_id,
        answer: payload.answer,
      })
      setAttemptResult(result)
      setPhase("awaiting_sa")
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败")
      setPhase("loaded") // Allow retry
    }
  }

  // Submit self-assessment
  const handleSelfAssessment = async (
    masteryState: "unmastered" | "vague" | "familiar" | "mastered"
  ) => {
    if (!attemptResult) return

    setPhase("submitting_sa")
    setError(null)

    try {
      const result = await submitSelfAssessment(attemptResult.attempt_id, {
        mastery_state: masteryState,
      })
      setSaResult(result)
      setPhase("completed")
    } catch (err) {
      setError(err instanceof Error ? err.message : "自评失败")
      setPhase("awaiting_sa") // Allow retry
    }
  }

  // --- Render ---

  if (phase === "loading") {
    return <div className={styles.loading}>加载中...</div>
  }

  if (phase === "error") {
    return (
      <div className={styles.error}>
        <p>{error}</p>
        <button
          className={styles.retryButton}
          onClick={() => {
            if (pendingAttemptId) {
              recoverAttempt(pendingAttemptId)
            } else {
              loadQuestion(questionId)
            }
          }}
          type="button"
        >
          重试
        </button>
      </div>
    )
  }

  if (!question) {
    return <div className={styles.error}>题目不存在</div>
  }

  return (
    <div className={styles.container}>
      {/* Meta */}
      <div className={styles.meta}>
        <span>
          难度: {DIFFICULTY_LABELS[question.difficulty] ?? question.difficulty}
        </span>
        {question.primary_knowledge_point?.name && (
          <span>知识点: {question.primary_knowledge_point.name}</span>
        )}
      </div>

      {/* Content */}
      {question.content && <p className={styles.content}>{question.content}</p>}

      {/* Answer input */}
      <textarea
        className={styles.textarea}
        value={userAnswer}
        onChange={(e) => setUserAnswer(e.target.value)}
        placeholder="请输入你的答案..."
        disabled={phase !== "loaded"}
      />

      {/* Submit / Retry */}
      {phase === "loaded" && (
        <div className={styles.actions}>
          <button
            className={styles.submitButton}
            onClick={handleSubmit}
            disabled={!userAnswer.trim()}
            type="button"
          >
            提交
          </button>
        </div>
      )}

      {phase === "submitting" && (
        <div className={styles.actions}>
          <button className={styles.submitButton} disabled type="button">
            提交中...
          </button>
        </div>
      )}

      {/* Submit error */}
      {error && phase === "loaded" && (
        <div className={styles.submitError}>{error}</div>
      )}

      {/* Reference answer (after submit) */}
      {attemptResult && (phase === "awaiting_sa" || phase === "completed") && (
        <div className={styles.reference}>
          <div className={styles.section}>
            <div className={styles.sectionLabel}>我的答案</div>
            <div className={styles.sectionValue}>{attemptResult.answer}</div>
          </div>
          {attemptResult.reference_answer && (
            <div className={styles.section}>
              <div className={styles.sectionLabel}>参考答案</div>
              <div className={styles.sectionValue}>
                {attemptResult.reference_answer}
              </div>
            </div>
          )}
          {attemptResult.explanation && (
            <div className={styles.section}>
              <div className={styles.sectionLabel}>解析</div>
              <div className={styles.sectionValue}>
                {attemptResult.explanation}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Self-assessment buttons */}
      {phase === "awaiting_sa" && (
        <>
          <p style={{ fontSize: 14, marginBottom: 12, color: "var(--text-secondary, #666)" }}>
            请评估你的掌握程度：
          </p>
          <div className={styles.saButtons}>
            {SA_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={styles.saButton}
                onClick={() => handleSelfAssessment(opt.value)}
                type="button"
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}

      {phase === "submitting_sa" && (
        <div className={styles.saButtons}>
          {SA_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`${styles.saButton} ${styles.saButtonSubmitting}`}
              disabled
              type="button"
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Submitting SA error */}
      {error && phase === "awaiting_sa" && (
        <div className={styles.submitError}>{error}</div>
      )}

      {/* Completion */}
      {phase === "completed" && saResult && (
        <>
          <div className={styles.completion}>
            <div className={styles.completionTitle}>✅ 自评完成</div>
            <div className={styles.completionField}>
              <div className={styles.completionLabel}>掌握状态</div>
              <div className={styles.completionValue}>
                {SA_OPTIONS.find(
                  (o) => o.value === saResult.self_assessed_mastery_state
                )?.label ?? saResult.self_assessed_mastery_state}
              </div>
            </div>
            <div className={styles.completionField}>
              <div className={styles.completionLabel}>下次复习</div>
              <div className={styles.completionValue}>
                {saResult.review_state.next_review_date}
              </div>
            </div>
          </div>
          <button className={styles.nextButton} onClick={onDone} type="button">
            下一题 →
          </button>
        </>
      )}
    </div>
  )
}