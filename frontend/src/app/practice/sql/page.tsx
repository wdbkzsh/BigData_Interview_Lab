"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { fetchQuestions, fetchDomains, fetchPendingAttempts } from "@/lib/api"
import type { QuestionListItem, Domain, PendingAttemptItem } from "@/lib/types"
import SQLQuestion from "@/components/practice/SQLQuestion"
import QuestionBank from "@/components/practice/QuestionBank"
import styles from "./page.module.css"

function SQLPracticeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const questionId = searchParams.get("id")
  const revision = searchParams.get("revision") ? Number(searchParams.get("revision")) : undefined
  const attemptType = (searchParams.get("attempt_type") as "new" | "review" | "practice") || "practice"
  const source = searchParams.get("source")

  const [questions, setQuestions] = useState<QuestionListItem[]>([])
  const [domains, setDomains] = useState<Domain[]>([])
  const [selectedDomain, setSelectedDomain] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAttemptId, setPendingAttemptId] = useState<number | null>(null)

  // Load domains on mount
  useEffect(() => {
    fetchDomains()
      .then((data) => setDomains(data))
      .catch(() => {})
  }, [])

  // Load question bank when domain changes (not when viewing a question)
  useEffect(() => {
    if (questionId) return
    setLoading(true)
    fetchQuestions({
      question_type: "sql",
      domain_id: selectedDomain || undefined,
      page: 1,
      page_size: 50,
    })
      .then((data) => setQuestions(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedDomain, questionId])

  // Check for pending recovery when viewing a specific question
  useEffect(() => {
    if (!questionId) return
    fetchPendingAttempts()
      .then((pending) => {
        // Search across all SQL pending types
        const allSqlPending: PendingAttemptItem[] = [
          ...pending.sql_confirmation,
          ...pending.sql_grading_failed,
          ...pending.sql_disputed,
        ]

        // Match by question_id + revision + attempt_type
        const match = allSqlPending.find((p) => {
          if (p.question_id !== questionId) return false
          if (revision && p.question_revision !== revision) return false
          if (p.attempt_type !== attemptType) return false
          return true
        })

        if (match) {
          setPendingAttemptId(match.attempt_id)
        }
      })
      .catch(() => {})
  }, [questionId, revision, attemptType])

  // Handle "done" — return to bank or dashboard
  const handleDone = useCallback(() => {
    setPendingAttemptId(null)
    if (source === "daily") {
      router.push("/")
      return
    }
    if (source === "wrong_book") {
      router.push("/wrong-book")
      return
    }
    router.push("/practice/sql")
  }, [router, source])

  const handleBackToBank = useCallback(() => {
    if (source === "daily") {
      router.push("/")
    } else if (source === "wrong_book") {
      router.push("/wrong-book")
    } else {
      router.push("/practice/sql")
    }
  }, [router, source])

  // --- Render ---

  if (loading && !questionId) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>SQL 题库</h1>
        </header>
        <div className={styles.loading}>加载中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>SQL 题库</h1>
        </header>
        <div className={styles.error}>{error}</div>
      </div>
    )
  }

  // No questionId → show question bank
  if (!questionId) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>SQL 题库</h1>
        </header>

        {domains.length > 0 && (
          <div className={styles.domainFilter}>
            <button
              className={`${styles.domainButton} ${selectedDomain === "" ? styles.domainActive : ""}`}
              onClick={() => setSelectedDomain("")}
              type="button"
            >
              全部
            </button>
            {domains.map((d) => (
              <button
                key={d.id}
                className={`${styles.domainButton} ${selectedDomain === d.id ? styles.domainActive : ""}`}
                onClick={() => setSelectedDomain(d.id)}
                type="button"
              >
                {d.name}
              </button>
            ))}
          </div>
        )}

        <div className={styles.content}>
          <QuestionBank items={questions} basePath="/practice/sql" />
        </div>
      </div>
    )
  }

  // Has questionId → show question
  let backLabel = "← 返回 SQL 题库"
  if (source === "daily") backLabel = "← 返回今日任务"
  if (source === "wrong_book") backLabel = "← 返回错题本"

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>SQL 题</h1>
        <button
          className={styles.backLink}
          onClick={handleBackToBank}
          type="button"
        >
          {backLabel}
        </button>
      </header>
      <div className={styles.content}>
        <SQLQuestion
          key={pendingAttemptId ? `recovery-${pendingAttemptId}` : `${questionId}-${revision ?? "current"}`}
          questionId={questionId}
          revision={revision}
          attemptType={attemptType}
          pendingAttemptId={pendingAttemptId}
          onDone={handleDone}
        />
      </div>
    </div>
  )
}

export default function SQLPracticePage() {
  return (
    <Suspense
      fallback={
        <div className={styles.page}>
          <header className={styles.header}>
            <h1 className={styles.title}>SQL 题库</h1>
          </header>
          <div className={styles.loading}>加载中...</div>
        </div>
      }
    >
      <SQLPracticeContent />
    </Suspense>
  )
}