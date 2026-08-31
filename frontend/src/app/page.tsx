'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { fetchDashboard, fetchTodayTask, skipDailyTaskItem, restoreDailyTaskItem } from '@/lib/api'
import type { DashboardData, DailyTaskData, DailyTaskItem } from '@/lib/types'
import styles from './page.module.css'

const DIFFICULTY_LABELS: Record<number, string> = {
  1: '★', 2: '★★', 3: '★★★', 4: '★★★★', 5: '★★★★★',
}

// DailyTaskItem doesn't include difficulty from backend
// We'll show it only if available

export default function Home() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [task, setTask] = useState<DailyTaskData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([fetchDashboard(), fetchTodayTask()])
      .then(([d, t]) => {
        setDashboard(d)
        setTask(t)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSkip = async (itemId: number) => {
    try {
      await skipDailyTaskItem(itemId)
      loadData()
    } catch { /* ignore */ }
  }

  const handleRestore = async (itemId: number) => {
    try {
      await restoreDailyTaskItem(itemId)
      loadData()
    } catch { /* ignore */ }
  }

  const getItemHref = (item: DailyTaskItem) => {
    const base = item.question_type === 'choice' ? '/practice/choice' : '/practice/short-answer'
    return `${base}?id=${item.question_id}&revision=${item.question_revision}&attempt_type=${item.item_type}&source=daily`
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <h1 className={styles.title}>BigData Interview Lab</h1>
        <p className={styles.loading}>加载中...</p>
      </main>
    )
  }

  if (error) {
    return (
      <main className={styles.page}>
        <h1 className={styles.title}>BigData Interview Lab</h1>
        <p className={styles.error}>{error}</p>
        <button className={styles.retryBtn} onClick={loadData} type="button">重试</button>
      </main>
    )
  }

  const today = dashboard?.today
  const review = dashboard?.review
  const week = dashboard?.week
  const pending = dashboard?.pending

  const reviewItems = task?.items.filter((i) => i.item_type === 'review') ?? []
  const newItems = task?.items.filter((i) => i.item_type === 'new') ?? []

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>BigData Interview Lab</h1>

      {/* Today Summary */}
      {today && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>今日学习</h2>
          <div className={styles.statsRow}>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>复习</div>
              <div className={styles.statValue}>{today.review_completed} / {today.review_total}</div>
              {today.review_skipped > 0 && <div className={styles.statSub}>跳过 {today.review_skipped}</div>}
            </div>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>新题</div>
              <div className={styles.statValue}>{today.new_completed} / {today.new_total}</div>
              {today.new_skipped > 0 && <div className={styles.statSub}>跳过 {today.new_skipped}</div>}
            </div>
          </div>
        </section>
      )}

      {/* Today Task Items */}
      {task && task.items.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>今日任务</h2>

          {reviewItems.length > 0 && (
            <div className={styles.itemGroup}>
              <h3 className={styles.groupTitle}>待复习</h3>
              {reviewItems.map((item) => (
                <TaskItemRow
                  key={item.id}
                  item={item}
                  onSkip={handleSkip}
                  onRestore={handleRestore}
                  getItemHref={getItemHref}
                />
              ))}
            </div>
          )}

          {newItems.length > 0 && (
            <div className={styles.itemGroup}>
              <h3 className={styles.groupTitle}>新题</h3>
              {newItems.map((item) => (
                <TaskItemRow
                  key={item.id}
                  item={item}
                  onSkip={handleSkip}
                  onRestore={handleRestore}
                  getItemHref={getItemHref}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {task && task.items.length === 0 && (
        <section className={styles.section}>
          <p className={styles.emptyText}>今天没有待完成任务</p>
        </section>
      )}

      {/* Review Status */}
      {review && (review.due_count > 0 || review.overdue_count > 0) && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>复习状态</h2>
          <div className={styles.statsRow}>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>待复习</div>
              <div className={styles.statValue}>{review.due_count}</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>已逾期</div>
              <div className={styles.statValue}>{review.overdue_count}</div>
            </div>
          </div>
        </section>
      )}

      {/* Weekly Stats */}
      {week && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>本周</h2>
          <div className={styles.statsRow}>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>完成</div>
              <div className={styles.statValue}>{week.completed_attempts}</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>学习天数</div>
              <div className={styles.statValue}>{week.study_days}</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statLabel}>选择题正确率</div>
              <div className={styles.statValue}>{week.choice_accuracy !== null ? `${Math.round(week.choice_accuracy * 100)}%` : '暂无数据'}</div>
            </div>
          </div>
        </section>
      )}

      {/* Pending */}
      {pending && pending.short_answer_self_assessment > 0 && (
        <section className={styles.section}>
          <p className={styles.pendingNotice}>有 {pending.short_answer_self_assessment} 道问答题等待自评</p>
        </section>
      )}

      {/* Quick Links */}
      <nav className={styles.nav}>
        <Link href="/practice/choice" className={styles.navLink}>选择题题库 →</Link>
        <Link href="/practice/short-answer" className={styles.navLink}>问答题题库 →</Link>
        <Link href="/practice/sql" className={styles.navLink}>SQL 题库 →</Link>
        <Link href="/wrong-book" className={styles.navLink}>错题本 →</Link>
        <Link href="/knowledge" className={styles.navLink}>知识库 →</Link>
      </nav>
    </main>
  )
}

function TaskItemRow({
  item,
  onSkip,
  onRestore,
  getItemHref,
}: {
  item: DailyTaskItem
  onSkip: (id: number) => void
  onRestore: (id: number) => void
  getItemHref: (item: DailyTaskItem) => string
}) {
  const isPending = item.status === 'pending'
  const isSkipped = item.status === 'skipped'
  const isCompleted = item.status === 'completed'
  const isSql = item.question_type === 'sql'

  return (
    <div className={`${styles.taskItem} ${isCompleted ? styles.taskItemDone : ''}`}>
      <div className={styles.taskItemLeft}>
        <div className={styles.taskItemTitle}>{item.title || item.question_id}</div>
        <div className={styles.taskItemMeta}>
          {item.primary_knowledge_point?.name && <span>{item.primary_knowledge_point.name}</span>}
          {item.domain?.name && <span>{item.domain.name}</span>}
          {item.due_date_snapshot && <span>到期: {item.due_date_snapshot}</span>}
        </div>
      </div>
      <div className={styles.taskItemActions}>
        {isPending && !isSql && (
          <Link href={getItemHref(item)} className={styles.actionBtn}>开始</Link>
        )}
        {isPending && isSql && (
          <span className={styles.sqlDisabled}>Phase 8 开放</span>
        )}
        {isPending && (
          <button className={styles.skipBtn} onClick={() => onSkip(item.id)} type="button">跳过</button>
        )}
        {isSkipped && (
          <button className={styles.restoreBtn} onClick={() => onRestore(item.id)} type="button">恢复</button>
        )}
        {isCompleted && (
          <span className={styles.completedBadge}>✓ 已完成</span>
        )}
      </div>
    </div>
  )
}