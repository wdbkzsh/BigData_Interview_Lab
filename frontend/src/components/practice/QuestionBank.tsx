"use client"

import Link from "next/link"
import type { QuestionListItem } from "@/lib/types"
import styles from "./QuestionBank.module.css"

interface Props {
  items: QuestionListItem[]
  basePath: string  // "/practice/choice" or "/practice/short-answer"
}

const DIFFICULTY_LABELS: Record<number, string> = {
  1: "★",
  2: "★★",
  3: "★★★",
  4: "★★★★",
  5: "★★★★★",
}

const MASTERY_LABELS: Record<string, string> = {
  unmastered: "不会",
  vague: "模糊",
  familiar: "基本掌握",
  mastered: "熟练掌握",
}

export default function QuestionBank({ items, basePath }: Props) {
  if (items.length === 0) {
    return <div className={styles.empty}>暂无题目</div>
  }

  return (
    <div className={styles.list}>
      {items.map((item) => {
        const hasPending = item.pending_self_assessment_attempt_id != null
        const rs = item.review_state

        let statusLabel = "未开始"
        let statusClass = styles.statusNotStarted
        if (hasPending) {
          statusLabel = "待自评"
          statusClass = styles.statusPending
        } else if (rs) {
          statusLabel =
            MASTERY_LABELS[rs.mastery_state] ?? rs.mastery_state
          statusClass =
            rs.mastery_state === "unmastered"
              ? styles.statusUnmastered
              : rs.mastery_state === "vague"
                ? styles.statusVague
                : rs.mastery_state === "familiar"
                  ? styles.statusFamiliar
                  : styles.statusMastered
        }

        let actionLabel = "开始答题"
        if (hasPending) actionLabel = "继续自评"
        else if (rs) actionLabel = "继续练习"

        return (
          <div key={item.id} className={styles.item}>
            <div className={styles.itemLeft}>
              <div className={styles.itemTitle}>
                {item.title || item.id}
              </div>
              <div className={styles.itemMeta}>
                <span>
                  {item.primary_knowledge_point?.name || item.primary_knowledge_point?.id}
                </span>
                <span>
                  难度: {DIFFICULTY_LABELS[item.difficulty] ?? item.difficulty}
                </span>
                <span className={`${styles.status} ${statusClass}`}>
                  {statusLabel}
                </span>
                {rs?.next_review_date && (
                  <span className={styles.nextReview}>
                    复习: {rs.next_review_date}
                  </span>
                )}
              </div>
            </div>
            <Link
              href={`${basePath}?id=${item.id}`}
              className={styles.actionButton}
            >
              {actionLabel}
            </Link>
          </div>
        )
      })}
    </div>
  )
}