'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

export default function Home() {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    fetch('http://127.0.0.1:8000/health')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Backend request failed')
        }
        return response.json()
      })
      .then((data) => {
        if (data.status === 'ok') {
          setStatus('ok')
        } else {
          setStatus('error')
        }
      })
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main>
      <h1>BigData Interview Lab</h1>
      {status === 'loading' && <p>Checking backend...</p>}
      {status === 'ok' && <p>Backend status: ok</p>}
      {status === 'error' && <p>Backend unavailable</p>}
      <nav style={{ marginTop: 24 }}>
        <Link href="/knowledge" style={{ color: '#0070f3', textDecoration: 'underline' }}>
          进入知识点 →
        </Link>
      </nav>
    </main>
  )
}