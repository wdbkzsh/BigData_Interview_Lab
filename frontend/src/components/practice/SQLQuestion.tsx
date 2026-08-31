"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  fetchQuestionDetailAtRevision,
  submitAttempt,
  confirmSQLAttempt,
} from "@/lib/api"
import type {
  QuestionDetail,
  AttemptResult,
  AssessmentData,
  SQLConfirmResult,
} from "@/lib/types"
import styles from "./SQLQuestion.module.css"

interface Props {
  questionId: string
  revision?: number
  onDone: () => void
}

type Phase =
  | "loading"
  | "loaded"
  | "submitting"
  | "awaiting_confirmation"
  | "confirming"
  | "completed"
  | "grading_failed"
  | "error"

const DIFFICULTY_LABELS: Record<number, string> = {
  1: "★",
  2: "★★",
  3: "★★★",
  4: "★★★★",
  5: "★★★★★",
}

const CRITERION_STATUS_LABELS: Record<string, string> = {
  matched: "满足",
  partial: "部分满足",
  missing: "未满足",
}

export default function SQLQuestion({ questionId, revision, onDone }: Props) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null)
  const [phase, setPhase] = useState<Phase>("loading")
  const [error, setError] = useState<string | null>(null)

  const [sqlInput, setSqlInput] = useState("")
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null)
  const [confirmResult, setConfirmResult] = useState<SQLConfirmResult | null>(null)
  const [adjustScore, setAdjustScore] = useState<string>("")
  const [clientRequestId] = useState(() => crypto.randomUUID())

  const frozenPayloadRef = useRef<{
    question_revision: number
    answer: string
    client_request_id: string
  } | null>(null)

  // Load question
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

  useEffect(() => {
    loadQuestion(questionId, revision)
  }, [questionId, revision, loadQuestion])

  // Submit SQL
  const handleSubmit = async () => {
    if (!question || !sqlInput.trim()) return

    if (!frozenPayloadRef.current) {
      frozenPayloadRef.current = {
        question_revision: question.revision,
        answer: sqlInput,
        client_request_id: clientRequestId,
      }
    }

    const payload = frozenPayloadRef.current
    setPhase("submitting")
    setError(null)

    try {
      const result = await submitAttempt(question.id, {
        question_revision: payload.question_revision,
        attempt_type: "practice",
        client_request_id: payload.client_request_id,
        answer: payload.answer,
      })
      setAttemptResult(result)

      if (result.status === "awaiting_confirmation") {
        setPhase("awaiting_confirmation")
      } else if (result.status === "grading_failed") {
        setPhase("grading_failed")
      } else {
        setPhase("awaiting_confirmation")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败")
      setPhase("loaded")
    }
  }

  // Accept
  const handleAccept = async () => {
    if (!attemptResult) return
    setPhase("confirming")
    setError(null)

    try {
      const result = await confirmSQLAttempt(attemptResult.attempt_id, {
        action: "accept",
      })
      setConfirmResult(result)
      setPhase("completed")
    } catch (err) {
      setError(err instanceof Error ? err.message : "确认失败")
      setPhase("awaiting_confirmation")
    }
  }

  // Adjust
  const handleAdjust = async () => {
    if (!attemptResult || !question) return
    const score = parseFloat(adjustScore)
    const maxScore = attemptResult.assessment?.max_score ?? 10

    if (isNaN(score) || score < 0 || score > maxScore) {
      setError(`分数必须在 0 到 ${maxScore} 之间`)
      return
    }

    setPhase("confirming")
    setError(null)

    try {
      const result = await confirmSQLAttempt(attemptResult.attempt_id, {
        action: "adjust",
        final_score: score,
      })
      setConfirmResult(result)
      setPhase("completed")
    } catch (err) {
      setError(err instanceof Error ? err.message : "确认失败")
      setPhase("awaiting_confirmation")
    }
  }

  // --- Render ---

  if (phase === "loading") {
    return <div className={styles.loading}>加载中...</div>
  }

  if (phase === "error" && !question) {
    return (
      <div className={styles.error}>
        <p>{error}</p>
        <button
          className={styles.retryButton}
          onClick={() => loadQuestion(questionId, revision)}
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

  const assessment = attemptResult?.assessment
  const maxScore = assessment?.max_score ?? 10
  const isConfirming = phase === "confirming"

  return (
    <div className={styles.container}>
      {/* Question info */}
      <div className={styles.meta}>
        <span>
          难度: {DIFFICULTY_LABELS[question.difficulty] ?? question.difficulty}
        </span>
        {question.primary_knowledge_point?.name && (
          <span>知识点: {question.primary_knowledge_point.name}</span>
        )}
      </div>

      {/* Question content */}
      {question.content && (
        <section className={styles.section}>
          <h4 className={styles.sectionTitle}>题目</h4>
          <p className={styles.sectionContent}>{question.content}</p>
        </section>
      )}

      {question.table_schema && (
        <section className={styles.section}>
          <h4 className={styles.sectionTitle}>表结构</h4>
          <pre className={styles.codeBlock}>{question.table_schema}</pre>
        </section>
      )}

      {question.field_description && (
        <section className={styles.section}>
          <h4 className={styles.sectionTitle}>字段说明</h4>
          <p className={styles.sectionContent}>{question.field_description}</p>
        </section>
      )}

      {question.business_requirement && (
        <section className={styles.section}>
          <h4 className={styles.sectionTitle}>业务需求</h4>
          <p className={styles.sectionContent}>{question.business_requirement}</p>
        </section>
      )}

      {/* SQL input (only when not yet submitted) */}
      {phase === "loaded" && (
        <>
          <textarea
            className={styles.sqlInput}
            value={sqlInput}
            onChange={(e) => setSqlInput(e.target.value)}
            placeholder="请输入你的 SQL..."
            rows={8}
          />
          <div className={styles.actions}>
            <button
              className={styles.submitButton}
              onClick={handleSubmit}
              disabled={!sqlInput.trim()}
              type="button"
            >
              提交 SQL
            </button>
          </div>
        </>
      )}

      {/* Submitting */}
      {phase === "submitting" && (
        <div className={styles.processing}>AI 正在判题…</div>
      )}

      {/* Submit error */}
      {error && phase === "loaded" && (
        <div className={styles.submitError}>{error}</div>
      )}

      {/* Grading failed */}
      {phase === "grading_failed" && attemptResult && (
        <div className={styles.feedback}>
          <div className={styles.feedbackTitle} style={{ color: "#c62828" }}>
            ❌ AI 判题失败
          </div>
          {attemptResult.assessment?.error_message && (
            <p className={styles.feedbackText}>
              {attemptResult.assessment.error_message}
            </p>
          )}
          <div className={styles.userSqlReadonly}>
            <h4 className={styles.sectionTitle}>你的 SQL</h4>
            <pre className={styles.codeBlock}>{attemptResult.answer}</pre>
          </div>
          <button
            className={styles.backButton}
            onClick={onDone}
            type="button"
          >
            返回 SQL 题库
          </button>
        </div>
      )}

      {/* Awaiting confirmation — show AI results */}
      {phase === "awaiting_confirmation" && attemptResult && assessment && (
        <>
          {/* User SQL (locked) */}
          <div className={styles.userSqlReadonly}>
            <h4 className={styles.sectionTitle}>你的 SQL</h4>
            <pre className={styles.codeBlock}>{attemptResult.answer}</pre>
          </div>

          {/* AI Score */}
          <div className={styles.aiScore}>
            <span className={styles.aiScoreLabel}>AI 建议分数</span>
            <span className={styles.aiScoreValue}>
              {assessment.raw_score} / {assessment.max_score}
            </span>
          </div>

          {/* Criteria */}
          {assessment.criteria && assessment.criteria.length > 0 && (
            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>评分标准</h4>
              <div className={styles.criteriaList}>
                {assessment.criteria.map((c) => (
                  <div key={c.id} className={styles.criterionItem}>
                    <div className={styles.criterionHeader}>
                      <span className={styles.criterionId}>{c.id}</span>
                      <span
                        className={`${styles.criterionStatus} ${
                          c.status === "matched"
                            ? styles.statusMatched
                            : c.status === "partial"
                              ? styles.statusPartial
                              : styles.statusMissing
                        }`}
                      >
                        {CRITERION_STATUS_LABELS[c.status] ?? c.status}
                      </span>
                      <span className={styles.criterionScore}>
                        {c.score}/{c.max_score}
                      </span>
                    </div>
                    {c.feedback && (
                      <p className={styles.criterionFeedback}>{c.feedback}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Knowledge Analysis */}
          {assessment.knowledge_analysis && (
            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>知识点分析</h4>
              {assessment.knowledge_analysis.mastered?.length > 0 && (
                <p className={styles.kpLine}>
                  <span className={styles.kpLabel}>已掌握:</span>
                  {assessment.knowledge_analysis.mastered.join(", ")}
                </p>
              )}
              {assessment.knowledge_analysis.weak?.length > 0 && (
                <p className={styles.kpLine}>
                  <span className={styles.kpLabel}>薄弱:</span>
                  {assessment.knowledge_analysis.weak.join(", ")}
                </p>
              )}
              {assessment.knowledge_analysis.missing?.length > 0 && (
                <p className={styles.kpLine}>
                  <span className={styles.kpLabel}>缺失:</span>
                  {assessment.knowledge_analysis.missing.join(", ")}
                </p>
              )}
            </section>
          )}

          {/* Errors / Suggestions */}
          {assessment.errors && assessment.errors.length > 0 && (
            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>逻辑错误</h4>
              <ul className={styles.listItems}>
                {assessment.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </section>
          )}

          {assessment.suggestions && assessment.suggestions.length > 0 && (
            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>改进建议</h4>
              <ul className={styles.listItems}>
                {assessment.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
          )}

          {assessment.reasoning_summary && (
            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>AI 评分说明</h4>
              <p className={styles.sectionContent}>
                {assessment.reasoning_summary}
              </p>
            </section>
          )}

          {/* Expected SQL */}
          {attemptResult.expected_sql && (
            <section className={styles.section}>
              <h4 className={styles.sectionTitle}>参考 SQL</h4>
              <pre className={styles.codeBlock}>
                {attemptResult.expected_sql}
              </pre>
              <p className={styles.hint}>
                参考 SQL 是一种可行实现，不代表唯一正确写法。
              </p>
            </section>
          )}

          {/* Confirm actions */}
          <div className={styles.confirmActions}>
            <button
              className={styles.acceptButton}
              onClick={handleAccept}
              disabled={isConfirming}
              type="button"
            >
              {isConfirming ? "处理中..." : "接受 AI 评分"}
            </button>

            <div className={styles.adjustGroup}>
              <input
                className={styles.adjustInput}
                type="number"
                min={0}
                max={maxScore}
                step={0.5}
                value={adjustScore}
                onChange={(e) => setAdjustScore(e.target.value)}
                placeholder={`0-${maxScore}`}
              />
              <button
                className={styles.adjustButton}
                onClick={handleAdjust}
                disabled={isConfirming || !adjustScore}
                type="button"
              >
                调整分数
              </button>
            </div>
          </div>

          {/* Confirm error */}
          {error && (
            <div className={styles.submitError}>{error}</div>
          )}
        </>
      )}

      {/* Confirming */}
      {isConfirming && (
        <div className={styles.processing}>处理中...</div>
      )}

      {/* Completed */}
      {phase === "completed" && confirmResult && (
        <div className={styles.completedSection}>
          <div className={styles.completedTitle}>✅ 已完成</div>

          <div className={styles.completedGrid}>
            <div className={styles.completedField}>
              <span className={styles.completedLabel}>最终得分</span>
              <span className={styles.completedValue}>
                {confirmResult.final_score} / {confirmResult.max_score}
              </span>
            </div>
            <div className={styles.completedField}>
              <span className={styles.completedLabel}>得分来源</span>
              <span className={styles.completedValue}>
                {confirmResult.final_score_source === "ai_confirmed"
                  ? "AI 评分"
                  : "用户调整"}
              </span>
            </div>
            {confirmResult.mastery_state && (
              <div className={styles.completedField}>
                <span className={styles.completedLabel}>掌握状态</span>
                <span className={styles.completedValue}>
                  {confirmResult.mastery_state}
                </span>
              </div>
            )}
            {confirmResult.next_review_date && (
              <div className={styles.completedField}>
                <span className={styles.completedLabel}>下次复习</span>
                <span className={styles.completedValue}>
                  {confirmResult.next_review_date}
                </span>
              </div>
            )}
          </div>

          <button
            className={styles.backButton}
            onClick={onDone}
            type="button"
          >
            返回 SQL 题库
          </button>
        </div>
      )}
    </div>
  )
}
