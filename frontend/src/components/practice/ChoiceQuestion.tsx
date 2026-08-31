"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { fetchQuestionDetailAtRevision, submitAttempt } from "@/lib/api"
import type { QuestionDetail, AttemptResult } from "@/lib/types"
import styles from "./ChoiceQuestion.module.css"

interface Props {
  questionId: string
  revision?: number
  attemptType?: "new" | "review" | "practice"
  onDone: () => void
}

const DIFFICULTY_LABELS: Record<number, string> = {
  1: "★",
  2: "★★",
  3: "★★★",
  4: "★★★★",
  5: "★★★★★",
}

export default function ChoiceQuestion({ questionId, revision, attemptType = "practice", onDone }: Props) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [submittedAnswer, setSubmittedAnswer] = useState<string | null>(null)
  const [clientRequestId, setClientRequestId] = useState(() =>
    crypto.randomUUID()
  )
  const [result, setResult] = useState<AttemptResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Frozen payload for retry — captured at submit time
  const frozenPayloadRef = useRef<{
    question_revision: number
    answer: string
    client_request_id: string
  } | null>(null)

  // Load question detail (optionally at specific revision)
  const loadQuestion = useCallback((id: string, rev?: number) => {
    setLoading(true)
    setLoadError(null)
    fetchQuestionDetailAtRevision(id, rev)
      .then((data) => setQuestion(data))
      .catch((err) => setLoadError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadQuestion(questionId, revision)
  }, [questionId, revision, loadQuestion])

  // Reset state for a new question
  useEffect(() => {
    setSelectedOption(null)
    setSubmittedAnswer(null)
    setResult(null)
    setSubmitError(null)
    frozenPayloadRef.current = null
    setClientRequestId(crypto.randomUUID())
  }, [questionId])

  const handleSubmit = async () => {
    if (!question) return

    // First submit: freeze the payload
    if (!frozenPayloadRef.current) {
      if (!selectedOption) return
      frozenPayloadRef.current = {
        question_revision: question.revision,
        answer: selectedOption,
        client_request_id: clientRequestId,
      }
      setSubmittedAnswer(selectedOption)
    }

    const payload = frozenPayloadRef.current
    setSubmitting(true)
    setSubmitError(null)

    try {
      const res = await submitAttempt(question.id, {
        question_revision: payload.question_revision,
        attempt_type: attemptType,
        client_request_id: payload.client_request_id,
        answer: payload.answer,
      })
      setResult(res)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "提交失败")
    } finally {
      setSubmitting(false)
    }
  }

  const handleNext = () => {
    onDone()
  }

  // --- Render ---

  if (loading) {
    return <div className={styles.loading}>加载题目中...</div>
  }

  if (loadError) {
    return (
      <div className={styles.error}>
        <p>{loadError}</p>
        <button
          className={styles.retryButton}
          onClick={() => loadQuestion(questionId)}
          type="button"
        >
          重试加载
        </button>
      </div>
    )
  }

  if (!question) {
    return <div className={styles.error}>题目不存在</div>
  }

  const isSubmitted = submittedAnswer !== null
  const showResult = result !== null

  return (
    <div className={styles.container}>
      {/* Header: difficulty + knowledge point */}
      <div className={styles.header}>
        <div className={styles.meta}>
          <span>难度: {DIFFICULTY_LABELS[question.difficulty] ?? question.difficulty}</span>
          {question.primary_knowledge_point?.name && (
            <span>知识点: {question.primary_knowledge_point.name}</span>
          )}
        </div>
      </div>

      {/* Content */}
      {question.content && <p className={styles.content}>{question.content}</p>}

      {/* Options */}
      <div className={styles.options}>
        {question.options?.map((opt) => {
          let optionClass = styles.option
          if (showResult) {
            // After result: highlight correct and incorrect
            if (opt.key === result.correct_answer) {
              optionClass += ` ${styles.correct}`
            } else if (
              opt.key === submittedAnswer &&
              !result.is_correct
            ) {
              optionClass += ` ${styles.incorrect}`
            }
            optionClass += ` ${styles.disabled}`
          } else if (isSubmitted) {
            optionClass += ` ${styles.disabled}`
          } else if (opt.key === selectedOption) {
            optionClass += ` ${styles.selected}`
          }

          return (
            <button
              key={opt.key}
              className={optionClass}
              onClick={() => {
                if (!isSubmitted) setSelectedOption(opt.key)
              }}
              disabled={isSubmitted}
              type="button"
            >
              <span className={styles.optionKey}>{opt.key}.</span>
              <span className={styles.optionText}>{opt.text}</span>
            </button>
          )
        })}
      </div>

      {/* Submit / Retry */}
      {!showResult && (
        <div className={styles.actions}>
          <button
            className={styles.submitButton}
            onClick={handleSubmit}
            disabled={submitting || (!isSubmitted && !selectedOption)}
            type="button"
          >
            {submitting
              ? "提交中..."
              : submitError
                ? "重试提交"
                : "提交"}
          </button>
        </div>
      )}

      {/* Submit error */}
      {submitError && !showResult && (
        <div className={styles.submitError}>{submitError}</div>
      )}

      {/* Feedback */}
      {showResult && result && (
        <>
          <div
            className={`${styles.feedback} ${
              result.is_correct
                ? styles.feedbackCorrect
                : styles.feedbackIncorrect
            }`}
          >
            <div
              className={`${styles.feedbackTitle} ${
                result.is_correct
                  ? styles.feedbackTitleCorrect
                  : styles.feedbackTitleIncorrect
              }`}
            >
              {result.is_correct ? "✅ 回答正确" : "❌ 回答错误"}
            </div>

            <div className={styles.feedbackSection}>
              <div className={styles.feedbackLabel}>正确答案</div>
              <div className={styles.feedbackValue}>
                {result.correct_answer}
              </div>
            </div>

            {result.explanation && (
              <div className={styles.feedbackSection}>
                <div className={styles.feedbackLabel}>解析</div>
                <div className={styles.feedbackValue}>
                  {result.explanation}
                </div>
              </div>
            )}
          </div>

          <button
            className={styles.nextButton}
            onClick={handleNext}
            type="button"
          >
            下一题 →
          </button>
        </>
      )}
    </div>
  )
}