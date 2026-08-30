"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { fetchQuestions, fetchDomains } from "@/lib/api"
import type { QuestionListItem, Domain } from "@/lib/types"
import ChoiceQuestion from "@/components/practice/ChoiceQuestion"
import QuestionBank from "@/components/practice/QuestionBank"
import styles from "./page.module.css"

function ChoicePracticeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const questionId = searchParams.get("id")

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

  // Load question bank when domain changes
  useEffect(() => {
    if (questionId) return // Don't reload bank when viewing a question
    setLoading(true)
    fetchQuestions({
      question_type: "choice",
      domain_id: selectedDomain || undefined,
      page: 1,
      page_size: 50,
    })
      .then((data) => setQuestions(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedDomain, questionId])

  // Handle "next question"
  const handleDone = useCallback(() => {
    const idx = questions.findIndex((q) => q.id === questionId)
    const nextIdx = idx + 1
    if (nextIdx < questions.length) {
      router.push(`/practice/choice?id=${questions[nextIdx].id}`)
    } else {
      router.push("/practice/choice")
    }
  }, [questions, questionId, router])

  const handleBackToBank = useCallback(() => {
    router.push("/practice/choice")
  }, [router])

  // --- Render ---

  if (loading && !questionId) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>选择题题库</h1>
        </header>
        <div className={styles.loading}>加载中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>选择题题库</h1>
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
          <h1 className={styles.title}>选择题题库</h1>
        </header>

        {/* Domain filter */}
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
          <QuestionBank items={questions} basePath="/practice/choice" />
        </div>
      </div>
    )
  }

  // Has questionId → show question
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>选择题</h1>
        <button
          className={styles.backLink}
          onClick={handleBackToBank}
          type="button"
        >
          ← 返回题库
        </button>
      </header>
      <div className={styles.content}>
        <ChoiceQuestion
          key={questionId}
          questionId={questionId}
          onDone={handleDone}
        />
      </div>
    </div>
  )
}

export default function ChoicePracticePage() {
  return (
    <Suspense
      fallback={
        <div className={styles.page}>
          <header className={styles.header}>
            <h1 className={styles.title}>选择题题库</h1>
          </header>
          <div className={styles.loading}>加载中...</div>
        </div>
      }
    >
      <ChoicePracticeContent />
    </Suspense>
  )
}