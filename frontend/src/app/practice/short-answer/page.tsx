"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { fetchQuestions, fetchPendingAttempts } from "@/lib/api"
import type { QuestionListItem } from "@/lib/types"
import ShortAnswerQuestion from "@/components/practice/ShortAnswerQuestion"
import QuestionBank from "@/components/practice/QuestionBank"
import styles from "./page.module.css"

function ShortAnswerPracticeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const questionId = searchParams.get("id")

  const [questions, setQuestions] = useState<QuestionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAttemptId, setPendingAttemptId] = useState<number | null>(null)

  // Load question bank and check pending
  useEffect(() => {
    const init = async () => {
      try {
        const [data, pending] = await Promise.all([
          fetchQuestions({ question_type: "short_answer", page: 1, page_size: 50 }),
          fetchPendingAttempts(),
        ])
        setQuestions(data.items)

        // If we have a questionId and there's a pending attempt for it, recover
        if (questionId) {
          const match = pending.short_answer_self_assessment.find(
            (p) => p.question_id === questionId
          )
          if (match) {
            setPendingAttemptId(match.attempt_id)
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败")
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [questionId])

  // Handle "next question"
  const handleDone = useCallback(() => {
    setPendingAttemptId(null)
    const idx = questions.findIndex((q) => q.id === questionId)
    const nextIdx = idx + 1
    if (nextIdx < questions.length) {
      router.push(`/practice/short-answer?id=${questions[nextIdx].id}`)
    } else {
      router.push("/practice/short-answer")
    }
  }, [questions, questionId, router])

  // Handle "return to bank"
  const handleBackToBank = useCallback(() => {
    router.push("/practice/short-answer")
  }, [router])

  // --- Render ---

  if (loading) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题题库</h1>
        </header>
        <div className={styles.loading}>加载中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题题库</h1>
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
          <h1 className={styles.title}>问答题题库</h1>
        </header>
        <div className={styles.content}>
          <QuestionBank items={questions} basePath="/practice/short-answer" />
        </div>
      </div>
    )
  }

  // Has questionId → show question (with possible pending recovery)
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>问答题</h1>
        <button
          className={styles.backLink}
          onClick={handleBackToBank}
          type="button"
        >
          ← 返回题库
        </button>
      </header>
      <div className={styles.content}>
        <ShortAnswerQuestion
          key={pendingAttemptId ? `recovery-${pendingAttemptId}` : questionId}
          questionId={questionId}
          pendingAttemptId={pendingAttemptId}
          onDone={handleDone}
        />
      </div>
    </div>
  )
}

export default function ShortAnswerPracticePage() {
  return (
    <Suspense
      fallback={
        <div className={styles.page}>
          <header className={styles.header}>
            <h1 className={styles.title}>问答题题库</h1>
          </header>
          <div className={styles.loading}>加载中...</div>
        </div>
      }
    >
      <ShortAnswerPracticeContent />
    </Suspense>
  )
}