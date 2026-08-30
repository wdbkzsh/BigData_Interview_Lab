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

interface GroupedItems {
  domainId: string
  domainName: string
  kps: {
    kpId: string
    kpName: string
    questions: QuestionListItem[]
  }[]
}

function groupByDomain(items: QuestionListItem[]): GroupedItems[] {
  const domainMap = new Map<string, Map<string, QuestionListItem[]>>()

  for (const item of items) {
    const domainId = item.domain?.id || "unknown"
    const domainName = item.domain?.name || domainId
    const kpId = item.primary_knowledge_point?.id || "unknown"
    const kpName = item.primary_knowledge_point?.name || kpId

    if (!domainMap.has(domainId)) {
      domainMap.set(domainId, new Map())
    }
    const kpMap = domainMap.get(domainId)!
    if (!kpMap.has(kpId)) {
      kpMap.set(kpId, [])
    }
    kpMap.get(kpId)!.push(item)
  }

  const result: GroupedItems[] = []
  for (const [domainId, kpMap] of domainMap) {
    const domainName = items.find((i) => i.domain?.id === domainId)?.domain?.name || domainId
    const kps = []
    for (const [kpId, questions] of kpMap) {
      const kpName = questions[0]?.primary_knowledge_point?.name || kpId
      kps.push({ kpId, kpName, questions })
    }
    result.push({ domainId, domainName, kps })
  }

  return result
}

function QuestionItem({
  item,
  basePath,
}: {
  item: QuestionListItem
  basePath: string
}) {
  const hasPending = item.pending_self_assessment_attempt_id != null
  const rs = item.review_state

  let statusLabel = "未开始"
  let statusClass = styles.statusNotStarted
  if (hasPending) {
    statusLabel = "待自评"
    statusClass = styles.statusPending
  } else if (rs) {
    statusLabel = MASTERY_LABELS[rs.mastery_state] ?? rs.mastery_state
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
    <div className={styles.item}>
      <div className={styles.itemLeft}>
        <div className={styles.itemTitle}>
          {item.title || item.id}
        </div>
        <div className={styles.itemMeta}>
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
}

export default function QuestionBank({ items, basePath }: Props) {
  if (items.length === 0) {
    return <div className={styles.empty}>暂无题目</div>
  }

  const grouped = groupByDomain(items)

  return (
    <div className={styles.groupedList}>
      {grouped.map((group) => (
        <div key={group.domainId} className={styles.domainGroup}>
          <h3 className={styles.domainTitle}>{group.domainName}</h3>
          {group.kps.map((kp) => (
            <div key={kp.kpId} className={styles.kpGroup}>
              <h4 className={styles.kpTitle}>{kp.kpName}</h4>
              <div className={styles.questionList}>
                {kp.questions.map((item) => (
                  <QuestionItem
                    key={item.id}
                    item={item}
                    basePath={basePath}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}