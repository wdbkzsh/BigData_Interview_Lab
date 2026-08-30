"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { fetchQuestions, fetchPendingAttempts } from "@/lib/api"
import type { QuestionListItem, PendingAttemptItem } from "@/lib/types"
import ShortAnswerQuestion from "@/components/practice/ShortAnswerQuestion"
import styles from "./page.module.css"

function ShortAnswerPracticeContent() {
  const router = useRouter()

  const [questions, setQuestions] = useState<QuestionListItem[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [pendingAttempt, setPendingAttempt] = useState<PendingAttemptItem | null>(
    null
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)
  const [recovering, setRecovering] = useState(false)

  // Load question list and check for pending attempts
  useEffect(() => {
    const init = async () => {
      try {
        // Check for pending attempts first
        const pending = await fetchPendingAttempts()
        if (pending.short_answer_self_assessment.length > 0) {
          setPendingAttempt(pending.short_answer_self_assessment[0])
          setRecovering(true)
        }

        // Load question list
        const data = await fetchQuestions({
          question_type: "short_answer",
          page: 1,
          page_size: 20,
        })
        setQuestions(data.items)
        if (data.items.length === 0 && !pending.short_answer_self_assessment.length) {
          setFinished(true)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败")
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  const handleDone = useCallback(() => {
    setPendingAttempt(null)
    setRecovering(false)

    const nextIndex = currentIndex + 1
    if (nextIndex >= questions.length) {
      setFinished(true)
    } else {
      setCurrentIndex(nextIndex)
    }
  }, [currentIndex, questions])

  // --- Render ---

  if (loading) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题练习</h1>
        </header>
        <div className={styles.loading}>加载题目列表...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题练习</h1>
        </header>
        <div className={styles.error}>{error}</div>
      </div>
    )
  }

  if (finished) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题练习</h1>
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

  // Recovery mode: pending attempt exists
  if (recovering && pendingAttempt) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题练习</h1>
        </header>
        <div className={styles.content}>
          <div className={styles.recoveryBanner}>
            恢复未完成的自评：{pendingAttempt.question_id}
          </div>
          <ShortAnswerQuestion
            key={`recovery-${pendingAttempt.attempt_id}`}
            questionId={pendingAttempt.question_id}
            pendingAttemptId={pendingAttempt.attempt_id}
            onDone={handleDone}
          />
        </div>
      </div>
    )
  }

  // Normal practice mode
  const currentQuestion = questions[currentIndex]
  if (!currentQuestion) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h1 className={styles.title}>问答题练习</h1>
        </header>
        <div className={styles.error}>题目不存在</div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>问答题练习</h1>
        <div className={styles.progress}>
          {currentIndex + 1} / {questions.length}
        </div>
      </header>
      <div className={styles.content}>
        <ShortAnswerQuestion
          key={currentQuestion.id}
          questionId={currentQuestion.id}
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
            <h1 className={styles.title}>问答题练习</h1>
          </header>
          <div className={styles.loading}>加载中...</div>
        </div>
      }
    >
      <ShortAnswerPracticeContent />
    </Suspense>
  )
}