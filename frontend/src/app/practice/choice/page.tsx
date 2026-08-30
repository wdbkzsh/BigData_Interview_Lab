"use client"

import { Suspense } from "react"
import { useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { fetchQuestions } from "@/lib/api"
import type { QuestionListItem } from "@/lib/types"
import ChoiceQuestion from "@/components/practice/ChoiceQuestion"
import styles from "./page.module.css"

function ChoicePracticeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const [questions, setQuestions] = useState<QuestionListItem[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)

  // Load question list on mount
  useEffect(() => {
    fetchQuestions({ question_type: "choice", page: 1, page_size: 20 })
      .then((data) => {
        setQuestions(data.items)
        if (data.items.length === 0) {
          setFinished(true)
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // Sync currentIndex with URL ?id=
  useEffect(() => {
    if (questions.length === 0) return
    const urlId = searchParams.get("id")
    if (urlId) {
      const idx = questions.findIndex((q) => q.id === urlId)
      if (idx >= 0) {
        setCurrentIndex(idx)
        return
      }
    }
    // Default: first question, update URL
    router.replace(`/practice/choice?id=${questions[0].id}`)
  }, [questions, searchParams, router])

  const handleDone = useCallback(() => {
    const nextIndex = currentIndex + 1
    if (nextIndex >= questions.length) {
      setFinished(true)
    } else {
      const nextId = questions[nextIndex].id
      router.push(`/practice/choice?id=${nextId}`)
    }
  }, [currentIndex, questions, router])

  // --- Render ---

  if (loading) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>选择题练习</h1>
        </header>
        <div className={styles.loading}>加载题目列表...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>选择题练习</h1>
        </header>
        <div className={styles.error}>{error}</div>
      </div>
    )
  }

  if (finished) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>选择题练习</h1>
        </header>
        <div className={styles.done}>
          <p>本页练习已完成</p>
          <button
            className={styles.backButton}
            onClick={() => router.push("/")}
            type="button"
          >
            返回首页
          </button>
        </div>
      </div>
    )
  }

  const currentQuestion = questions[currentIndex]
  if (!currentQuestion) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>选择题练习</h1>
        </header>
        <div className={styles.error}>题目不存在</div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>选择题练习</h1>
        <div className={styles.progress}>
          {currentIndex + 1} / {questions.length}
        </div>
      </header>

      <ChoiceQuestion
        key={currentQuestion.id}
        questionId={currentQuestion.id}
        onDone={handleDone}
      />
    </div>
  )
}

export default function ChoicePracticePage() {
  return (
    <Suspense
      fallback={
        <div className={styles.page}>
          <header className={styles.header}>
            <h1 className={styles.title}>选择题练习</h1>
          </header>
          <div className={styles.loading}>加载中...</div>
        </div>
      }
    >
      <ChoicePracticeContent />
    </Suspense>
  )
}