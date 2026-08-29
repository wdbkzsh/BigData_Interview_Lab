"use client"

import { useState, useEffect } from "react"
import { fetchKnowledgeTree, fetchKnowledgePointDetail } from "@/lib/api"
import type { KnowledgePointTreeNode, KnowledgePointDetail } from "@/lib/types"
import KnowledgeTree from "@/components/knowledge/KnowledgeTree"
import KnowledgeDetail from "@/components/knowledge/KnowledgeDetail"
import KnowledgeCard from "@/components/knowledge/KnowledgeCard"
import styles from "./page.module.css"

export default function KnowledgePage() {
  const [tree, setTree] = useState<KnowledgePointTreeNode[]>([])
  const [treeLoading, setTreeLoading] = useState(true)
  const [treeError, setTreeError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<KnowledgePointDetail | null>(null)

  // Load knowledge tree on mount
  useEffect(() => {
    fetchKnowledgeTree()
      .then((data) => setTree(data))
      .catch((err) => setTreeError(err.message))
      .finally(() => setTreeLoading(false))
  }, [])

  // Load detail when selection changes
  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    let cancelled = false
    fetchKnowledgePointDetail(selectedId)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch(() => {
        // Error handled in KnowledgeDetail component
      })
    return () => {
      cancelled = true
    }
  }, [selectedId])

  const handleSelect = (id: string) => {
    setSelectedId(id)
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>知识点</h1>
      </header>

      <div className={styles.layout}>
        {/* Left: Knowledge Tree */}
        <aside className={styles.sidebar}>
          <h2 className={styles.sidebarTitle}>知识树</h2>
          {treeLoading && <div className={styles.loading}>加载中...</div>}
          {treeError && <div className={styles.error}>{treeError}</div>}
          {!treeLoading && !treeError && (
            <KnowledgeTree
              nodes={tree}
              selectedId={selectedId}
              onSelect={handleSelect}
            />
          )}
        </aside>

        {/* Right: Detail + Card */}
        <main className={styles.content}>
          <KnowledgeDetail knowledgePointId={selectedId} />
          {selectedId && detail && (
            <KnowledgeCard
              knowledgePointId={selectedId}
              hasCard={detail.has_card}
            />
          )}
        </main>
      </div>
    </div>
  )
}