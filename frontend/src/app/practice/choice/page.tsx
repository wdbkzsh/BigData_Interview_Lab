"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { fetchQuestions } from "@/lib/api"
import type { QuestionListItem } from "@/lib/types"
import ChoiceQuestion from "@/components/practice/ChoiceQuestion"
import QuestionBank from "@/components/practice/QuestionBank"
import styles from "./page.module.css"

function ChoicePracticeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const questionId = searchParams.get("id")

  const [questions, setQuestions] = useState<QuestionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [bankLoaded, setBankLoaded] = useState(false)

  // Load question bank
  const loadBank = useCallback(() => {
    setLoading(true)
    fetchQuestions({ question_type: "choice", page: 1, page_size: 50 })
      .then((data) => {
        setQuestions(data.items)
        setBankLoaded(true)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadBank()
  }, [loadBank])

  // Handle "next question" from within the question
  const handleDone = useCallback(() => {
    // Find current index and go to next
    const idx = questions.findIndex((q) => q.id === questionId)
    const nextIdx = idx + 1
    if (nextIdx < questions.length) {
      router.push(`/practice/choice?id=${questions[nextIdx].id}`)
    } else {
      // Last question — return to bank
      router.push("/practice/choice")
    }
  }, [questions, questionId, router])

  // Handle "return to bank"
  const handleBackToBank = useCallback(() => {
    router.push("/practice/choice")
  }, [router])

  // --- Render ---

  if (loading) {
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