"use client"

import { useState, useEffect, useCallback } from "react"
import { fetchKnowledgeCard, recordCardView } from "@/lib/api"
import type { KnowledgeCard as KnowledgeCardType } from "@/lib/types"
import styles from "./KnowledgeCard.module.css"

interface Props {
  knowledgePointId: string | null
  hasCard: boolean
}

export default function KnowledgeCard({ knowledgePointId, hasCard }: Props) {
  const [card, setCard] = useState<KnowledgeCardType | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [marking, setMarking] = useState(false)

  const loadCard = useCallback((kpId: string) => {
    setLoading(true)
    setError(null)
    fetchKnowledgeCard(kpId)
      .then((data) => setCard(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!knowledgePointId || !hasCard) {
      setCard(null)
      return
    }
    loadCard(knowledgePointId)
  }, [knowledgePointId, hasCard, loadCard])

  const handleMarkView = async () => {
    if (!card) return
    setMarking(true)
    try {
      await recordCardView(card.id)
      // Reload card to get updated progress
      loadCard(card.knowledge_point_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "标记失败")
    } finally {
      setMarking(false)
    }
  }

  if (!knowledgePointId) {
    return null
  }

  if (!hasCard) {
    return <div className={styles.empty}>该知识点暂无知识卡片</div>
  }

  if (loading) {
    return <div className={styles.placeholder}>加载卡片中...</div>
  }

  if (error) {
    return <div className={styles.error}>{error}</div>
  }

  if (!card) {
    return null
  }

  const { content, progress } = card

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>{content.title}</h3>
        <div className={styles.progress}>
          <span className={styles.progressStatus}>
            {progress.status === "read" ? "已阅读" : "未阅读"}
          </span>
          {progress.view_count > 0 && (
            <span className={styles.viewCount}>
              {progress.view_count} 次
            </span>
          )}
        </div>
      </div>

      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>一句话定义</h4>
        <p className={styles.sectionContent}>{content.one_line_definition}</p>
      </section>

      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>核心原理</h4>
        <p className={styles.sectionContent}>{content.core_principle}</p>
      </section>

      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>面试高频点</h4>
        <p className={styles.sectionContent}>{content.interview_highlights}</p>
      </section>

      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>常见易错点</h4>
        <p className={styles.sectionContent}>{content.common_mistakes}</p>
      </section>

      <button
        className={styles.markButton}
        onClick={handleMarkView}
        disabled={marking}
        type="button"
      >
        {marking ? "标记中..." : "标记阅读"}
      </button>
    </div>
  )
}