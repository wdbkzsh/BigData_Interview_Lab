"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  fetchQuestionDetailAtRevision,
  submitAttempt,
  fetchAttempt,
  confirmSQLAttempt,
  regradeSQLAttempt,
  disputeSQLAttempt,
} from "@/lib/api"
import type {
  QuestionDetail,
  AttemptResult,
  AssessmentData,
  SQLConfirmResult,
  AttemptDetail,
} from "@/lib/types"
import styles from "./SQLQuestion.module.css"

interface Props {
  questionId: string
  revision?: number
  attemptType?: "new" | "review" | "practice"
  pendingAttemptId?: number | null
  onDone: () => void
}

type Phase =
  | "loading"
  | "loaded"
  | "submitting"
  | "awaiting_confirmation"
  | "grading_failed"
  | "disputed"
  | "confirming"
  | "regrading"
  | "completed"
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

export default function SQLQuestion({
  questionId,
  revision,
  attemptType = "practice",
  pendingAttemptId,
  onDone,
}: Props) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null)
  const [phase, setPhase] = useState<Phase>("loading")
  const [error, setError] = useState<string | null>(null)

  const [sqlInput, setSqlInput] = useState("")
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null)
  const [confirmResult, setConfirmResult] = useState<SQLConfirmResult | null>(null)
  const [adjustScore, setAdjustScore] = useState<string>("")
  const [disputeReason, setDisputeReason] = useState("")
  const [showDisputeInput, setShowDisputeInput] = useState(false)
  const [clientRequestId] = useState(() => crypto.randomUUID())

  const frozenPayloadRef = useRef<{
    question_revision: number
    answer: string
    client_request_id: string
  } | null>(null)

  // Load question detail
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
    fetchAttempt(attemptId)
      .then((detail) => {
        // Load question at the attempt's revision
        fetchQuestionDetailAtRevision(detail.question_id, detail.question_revision)
          .then((q) => {
            setQuestion(q)
            setSqlInput(detail.answer)

            // Build attemptResult from detail
            const result: AttemptResult = {
              attempt_id: detail.id,
              question_id: detail.question_id,
              question_revision: detail.question_revision,
              answer: detail.answer,
              status: detail.status,
              is_correct: null,
              score: null,
              correct_answer: null,
              reference_answer: null,
              explanation: null,
            }

            // Set phase based on status
            if (detail.status === "awaiting_confirmation") {
              // Need to get assessment data — rebuild from detail
              // For now, set phase and let user take action
              setAttemptResult(result)
              setPhase("awaiting_confirmation")
            } else if (detail.status === "grading_failed") {
              setAttemptResult(result)
              setPhase("grading_failed")
            } else if (detail.status === "disputed") {
              setAttemptResult(result)
              setPhase("disputed")
            } else {
              setAttemptResult(result)
              setPhase("loaded")
            }
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

  // Initialize
  useEffect(() => {
    if (pendingAttemptId) {
      recoverAttempt(pendingAttemptId)
    } else {
      loadQuestion(questionId, revision)
    }
  }, [questionId, revision, pendingAttemptId, loadQuestion, recoverAttempt])

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
        attempt_type: attemptType,
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
    if (!attemptResult) return
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

  // Regrade
  const handleRegrade = async () => {
    if (!attemptResult) return
    setPhase("regrading")
    setError(null)

    try {
      const result = await regradeSQLAttempt(attemptResult.attempt_id)
      // Update attemptResult with new status
      setAttemptResult((prev) =>
        prev ? { ...prev, status: result.status } : prev
      )

      if (result.status === "awaiting_confirmation") {
        setPhase("awaiting_confirmation")
      } else if (result.status === "grading_failed") {
        setPhase("grading_failed")
      } else {
        setPhase("awaiting_confirmation")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "重新判题失败")
      // Restore previous phase
      if (attemptResult?.status === "grading_failed") {
        setPhase("grading_failed")
      } else if (attemptResult?.status === "disputed") {
        setPhase("disputed")
      } else {
        setPhase("awaiting_confirmation")
      }
    }
  }

  // Dispute
  const handleDispute = async () => {
    if (!attemptResult || !disputeReason.trim()) return
    setPhase("confirming")
    setError(null)

    try {
      const result = await disputeSQLAttempt(
        attemptResult.attempt_id,
        disputeReason.trim()
      )
      setAttemptResult((prev) =>
        prev ? { ...prev, status: result.status } : prev
      )
      setPhase("disputed")
      setShowDisputeInput(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "标记争议失败")
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
          onClick={() => {
            if (pendingAttemptId) {
              recoverAttempt(pendingAttemptId)
            } else {
              loadQuestion(questionId, revision)
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

  const assessment = attemptResult?.assessment
  const maxScore = assessment?.max_score ?? 10
  const isConfirming = phase === "confirming"
  const isRegrading = phase === "regrading"
  const isProcessing = isConfirming || isRegrading

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

      {/* Submitting / Regrading */}
      {(phase === "submitting" || phase === "regrading") && (
        <div className={styles.processing}>
          {phase === "submitting" ? "AI 正在判题…" : "AI 正在重新判题…"}
        </div>
      )}

      {/* Submit error */}
      {error && phase === "loaded" && (
        <div className={styles.submitError}>{error}</div>
      )}

      {/* User SQL (locked) — shown in all post-submit states */}
      {attemptResult && phase !== "loaded" && phase !== "submitting" && (
        <div className={styles.userSqlReadonly}>
          <h4 className={styles.sectionTitle}>你的 SQL</h4>
          <pre className={styles.codeBlock}>{attemptResult.answer}</pre>
        </div>
      )}

      {/* grading_failed */}
      {phase === "grading_failed" && attemptResult && (
        <div className={styles.feedback}>
          <div className={styles.feedbackTitle} style={{ color: "#c62828" }}>
            ❌ AI 判题失败
          </div>
          <p className={styles.feedbackText}>
            {assessment?.error_message || "判题过程中出现错误，请稍后重试。"}
          </p>
          <div className={styles.confirmActions}>
            <button
              className={styles.acceptButton}
              onClick={handleRegrade}
              disabled={isProcessing}
              type="button"
            >
              {isRegrading ? "重新判题中..." : "重新判题"}
            </button>
          </div>
          <button
            className={styles.backButton}
            onClick={onDone}
            type="button"
          >
            返回题库
          </button>
        </div>
      )}

      {/* disputed */}
      {phase === "disputed" && attemptResult && (
        <div className={styles.feedback}>
          <div className={styles.feedbackTitle} style={{ color: "#e65100" }}>
            ⚠️ 已标记争议
          </div>
          <p className={styles.feedbackText}>
            该判题已标记为有异议。您可以重新判题以获取新的 AI 评估。
          </p>
          <div className={styles.confirmActions}>
            <button
              className={styles.acceptButton}
              onClick={handleRegrade}
              disabled={isProcessing}
              type="button"
            >
              {isRegrading ? "重新判题中..." : "重新判题"}
            </button>
          </div>
          <button
            className={styles.backButton}
            onClick={onDone}
            type="button"
          >
            返回题库
          </button>
        </div>
      )}

      {/* awaiting_confirmation — show AI results */}
      {phase === "awaiting_confirmation" && attemptResult && assessment && (
        <>
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
              disabled={isProcessing}
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
                disabled={isProcessing || !adjustScore}
                type="button"
              >
                调整分数
              </button>
            </div>

            <button
              className={styles.adjustButton}
              onClick={handleRegrade}
              disabled={isProcessing}
              type="button"
            >
              {isRegrading ? "重新判题中..." : "重新判题"}
            </button>

            <button
              className={styles.adjustButton}
              onClick={() => setShowDisputeInput(!showDisputeInput)}
              disabled={isProcessing}
              type="button"
            >
              对此评分有异议
            </button>
          </div>

          {/* Dispute input */}
          {showDisputeInput && (
            <div className={styles.disputeSection}>
              <textarea
                className={styles.disputeInput}
                value={disputeReason}
                onChange={(e) => setDisputeReason(e.target.value)}
                placeholder="请说明争议原因..."
                rows={3}
              />
              <button
                className={styles.adjustButton}
                onClick={handleDispute}
                disabled={isProcessing || !disputeReason.trim()}
                type="button"
              >
                提交争议
              </button>
            </div>
          )}

          {/* Error */}
          {error && <div className={styles.submitError}>{error}</div>}
        </>
      )}

      {/* Confirming / processing */}
      {isProcessing && !isRegrading && (
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
            返回题库
          </button>
        </div>
      )}
    </div>
  )
}