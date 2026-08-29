"use client"

import { useState, useEffect } from "react"
import { fetchKnowledgePointDetail } from "@/lib/api"
import type { KnowledgePointDetail } from "@/lib/types"
import styles from "./KnowledgeDetail.module.css"

interface Props {
  knowledgePointId: string | null
}

export default function KnowledgeDetail({ knowledgePointId }: Props) {
  const [detail, setDetail] = useState<KnowledgePointDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!knowledgePointId) {
      setDetail(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchKnowledgePointDetail(knowledgePointId)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [knowledgePointId])

  if (!knowledgePointId) {
    return <div className={styles.placeholder}>选择知识点查看详情</div>
  }

  if (loading) {
    return <div className={styles.placeholder}>加载中...</div>
  }

  if (error) {
    return <div className={styles.error}>{error}</div>
  }

  if (!detail) {
    return null
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.name}>{detail.name}</h2>
      {detail.description && (
        <p className={styles.description}>{detail.description}</p>
      )}
      <div className={styles.stats}>
        <span className={styles.stat}>
          题目数量: <strong>{detail.question_count}</strong>
        </span>
        <span className={styles.stat}>
          知识卡片: <strong>{detail.has_card ? "有" : "无"}</strong>
        </span>
      </div>
    </div>
  )
}