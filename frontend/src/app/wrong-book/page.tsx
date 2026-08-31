"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { fetchWrongBook, setWrongBookPreference } from "@/lib/api"
import type { WrongBookItem } from "@/lib/types"
import styles from "./page.module.css"

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

export default function WrongBookPage() {
  const [items, setItems] = useState<WrongBookItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  // Filters
  const [filterType, setFilterType] = useState("")
  const [filterMastery, setFilterMastery] = useState("")

  const loadWrongBook = useCallback(() => {
    setLoading(true)
    fetchWrongBook({
      question_type: filterType || undefined,
      mastery_state: filterMastery || undefined,
      page,
      page_size: 20,
    })
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .catch(() => {
        setItems([])
        setTotal(0)
      })
      .finally(() => setLoading(false))
  }, [filterType, filterMastery, page])

  useEffect(() => {
    loadWrongBook()
  }, [loadWrongBook])

  const handlePreference = async (
    questionId: string,
    mode: "auto" | "follow" | "ignore"
  ) => {
    try {
      await setWrongBookPreference(questionId, { mode })
      loadWrongBook()
    } catch {
      // silently fail
    }
  }

  const getRedoHref = (item: WrongBookItem) => {
    if (item.question_type === "choice") {
      return `/practice/choice?id=${item.question_id}`
    }
    if (item.question_type === "short_answer") {
      return `/practice/short-answer?id=${item.question_id}`
    }
    if (item.question_type === "sql") {
      return `/practice/sql?id=${item.question_id}&source=wrong_book`
    }
    return null
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>错题本</h1>
      </header>

      {/* Filters */}
      <div className={styles.filters}>
        <select
          className={styles.filterSelect}
          value={filterType}
          onChange={(e) => {
            setFilterType(e.target.value)
            setPage(1)
          }}
        >
          <option value="">全部题型</option>
          <option value="choice">选择题</option>
          <option value="short_answer">问答题</option>
          <option value="sql">SQL</option>
        </select>

        <select
          className={styles.filterSelect}
          value={filterMastery}
          onChange={(e) => {
            setFilterMastery(e.target.value)
            setPage(1)
          }}
        >
          <option value="">全部状态</option>
          <option value="unmastered">不会</option>
          <option value="vague">模糊</option>
        </select>
      </div>

      {/* List */}
      <div className={styles.list}>
        {loading && <div className={styles.loading}>加载中...</div>}

        {!loading && items.length === 0 && (
          <div className={styles.empty}>暂无错题</div>
        )}

        {items.map((item) => (
          <div key={item.question_id} className={styles.item}>
            <div className={styles.itemLeft}>
              <div className={styles.itemTitle}>
                {item.title || item.question_id}
              </div>
              <div className={styles.itemMeta}>
                <span>
                  难度: {DIFFICULTY_LABELS[item.difficulty] ?? item.difficulty}
                </span>
                {item.mastery_state && (
                  <span
                    className={`${styles.badge} ${
                      item.mastery_state === "unmastered"
                        ? styles.badgeUnmastered
                        : item.mastery_state === "vague"
                          ? styles.badgeVague
                          : ""
                    }`}
                  >
                    {MASTERY_LABELS[item.mastery_state] ?? item.mastery_state}
                  </span>
                )}
                {item.wrong_book_mode !== "auto" && (
                  <span
                    className={`${styles.badge} ${
                      item.wrong_book_mode === "follow"
                        ? styles.badgeFollow
                        : styles.badgeIgnore
                    }`}
                  >
                    {item.wrong_book_mode === "follow" ? "关注" : "忽略"}
                  </span>
                )}
                {item.next_review_date && (
                  <span>复习: {item.next_review_date}</span>
                )}
                {item.has_card && (
                  <Link
                    href={`/knowledge?id=${item.primary_knowledge_point_id}`}
                    style={{ color: "#0070f3" }}
                  >
                    知识卡
                  </Link>
                )}
              </div>
            </div>

            <div className={styles.itemActions}>
              {/* Preference buttons */}
              {item.wrong_book_mode !== "follow" && (
                <button
                  className={styles.actionButton}
                  onClick={() => handlePreference(item.question_id, "follow")}
                  type="button"
                >
                  关注
                </button>
              )}
              {item.wrong_book_mode !== "ignore" && (
                <button
                  className={styles.actionButton}
                  onClick={() => handlePreference(item.question_id, "ignore")}
                  type="button"
                >
                  忽略
                </button>
              )}
              {item.wrong_book_mode !== "auto" && (
                <button
                  className={styles.actionButton}
                  onClick={() => handlePreference(item.question_id, "auto")}
                  type="button"
                >
                  恢复
                </button>
              )}

              {/* Redo */}
              {getRedoHref(item) ? (
                <Link
                  href={getRedoHref(item)!}
                  className={styles.actionButton}
                >
                  重做
                </Link>
              ) : (
                <button
                  className={styles.actionButton}
                  disabled
                  type="button"
                  title="SQL 练习尚未实现"
                >
                  重做
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageButton}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            type="button"
          >
            上一页
          </button>
          <span style={{ fontSize: 14, color: "var(--text-secondary, #999)" }}>
            {page} / {totalPages}
          </span>
          <button
            className={styles.pageButton}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            type="button"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}