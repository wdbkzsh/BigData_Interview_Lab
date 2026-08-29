"use client"

import type { KnowledgePointTreeNode } from "@/lib/types"
import styles from "./KnowledgeTree.module.css"

interface Props {
  nodes: KnowledgePointTreeNode[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function KnowledgeTree({ nodes, selectedId, onSelect }: Props) {
  if (nodes.length === 0) {
    return <div className={styles.empty}>暂无知识点</div>
  }

  return (
    <ul className={styles.tree}>
      {nodes.map((node) => (
        <TreeNode
          key={node.id}
          node={node}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </ul>
  )
}

function TreeNode({
  node,
  selectedId,
  onSelect,
}: {
  node: KnowledgePointTreeNode
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const isSelected = node.id === selectedId
  const hasChildren = node.children.length > 0

  return (
    <li className={styles.node}>
      <button
        className={`${styles.label} ${isSelected ? styles.selected : ""}`}
        onClick={() => onSelect(node.id)}
        type="button"
      >
        {hasChildren && <span className={styles.arrow}>▶</span>}
        {!hasChildren && <span className={styles.spacer} />}
        {node.name}
      </button>
      {hasChildren && (
        <ul className={styles.children}>
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  )
}