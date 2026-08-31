"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { fetchQuestions, fetchDomains } from "@/lib/api"
import type { QuestionListItem, Domain } from "@/lib/types"
import SQLQuestion from "@/components/practice/SQLQuestion"
import QuestionBank from "@/components/practice/QuestionBank"
import styles from "./page.module.css"

function SQLPracticeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const questionId = searchParams.get("id")
  const revision = searchParams.get("revision") ? Number(searchParams.get("revision")) : undefined
  const source = searchParams.get("source")

  const [questions, setQuestions] = useState<QuestionListItem[]>([])
  const [domains, setDomains] = useState<Domain[]>([])
  const [selectedDomain, setSelectedDomain] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  // Handle "done" — return to bank
  const handleDone = useCallback(() => {
    if (source === "daily") {
      router.push("/")
      return
    }
    router.push("/practice/sql")
  }, [router, source])

  const handleBackToBank = useCallback(() => {
    if (source === "daily") {
      router.push("/")
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
  const backLabel = source === "daily" ? "← 返回今日任务" : "← 返回 SQL 题库"

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
          key={`${questionId}-${revision ?? "current"}`}
          questionId={questionId}
          revision={revision}
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
