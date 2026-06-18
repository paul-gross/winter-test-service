import { useState, useEffect, useCallback } from 'react'

interface HealthStatus {
  status: string
  db: string
}

interface Item {
  id: number
  label: string
  source: string
  created_at: string
}

type ApiReachability = 'ok' | 'db-down' | 'unreachable'

function getHealthState(health: HealthStatus | null, error: boolean): ApiReachability {
  if (error || health === null) return 'unreachable'
  if (health.db !== 'ok') return 'db-down'
  return 'ok'
}

function HealthBadge({ state }: { state: ApiReachability }) {
  const configs: Record<ApiReachability, { bg: string; text: string; label: string }> = {
    ok: { bg: '#22c55e', text: '#fff', label: 'API ok / DB ok' },
    'db-down': { bg: '#eab308', text: '#fff', label: 'API ok / DB down' },
    unreachable: { bg: '#ef4444', text: '#fff', label: 'API unreachable' },
  }
  const { bg, text, label } = configs[state]
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '4px 12px',
        borderRadius: '9999px',
        background: bg,
        color: text,
        fontWeight: 600,
        fontSize: '0.875rem',
      }}
    >
      {label}
    </span>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthError, setHealthError] = useState(false)
  const [items, setItems] = useState<Item[]>([])
  const [newLabel, setNewLabel] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [crashPending, setCrashPending] = useState(false)
  const [crashMsg, setCrashMsg] = useState<string | null>(null)

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/api/health')
      if (!res.ok) throw new Error('non-ok')
      const data: HealthStatus = await res.json()
      setHealth(data)
      setHealthError(false)
    } catch {
      setHealth(null)
      setHealthError(true)
    }
  }, [])

  const fetchItems = useCallback(async () => {
    try {
      const res = await fetch('/api/items')
      if (!res.ok) return
      const data: Item[] = await res.json()
      setItems(data)
    } catch {
      // silently ignore — health badge covers API unreachability
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    fetchItems()
    const healthTimer = setInterval(fetchHealth, 3000)
    const itemsTimer = setInterval(fetchItems, 5000)
    return () => {
      clearInterval(healthTimer)
      clearInterval(itemsTimer)
    }
  }, [fetchHealth, fetchItems])

  async function handleAdd() {
    if (!newLabel.trim()) return
    setAdding(true)
    setAddError(null)
    try {
      const res = await fetch('/api/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: newLabel.trim() }),
      })
      if (!res.ok) {
        const body = await res.text()
        setAddError(`Error ${res.status}: ${body}`)
      } else {
        setNewLabel('')
        await fetchItems()
      }
    } catch {
      setAddError('Request failed — API may be unreachable')
    } finally {
      setAdding(false)
    }
  }

  async function handleCrash() {
    if (!confirm('This will hard-crash the API process (os._exit). Proceed?')) return
    setCrashPending(true)
    setCrashMsg(null)
    try {
      await fetch('/api/chaos/crash', { method: 'POST' })
      setCrashMsg('Crash sent — API should be down shortly')
    } catch {
      setCrashMsg('Request failed (API may have crashed before responding — expected)')
    } finally {
      setCrashPending(false)
    }
  }

  const healthState = getHealthState(health, healthError)

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: '32px 16px', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ marginBottom: 4 }}>winter-test-service</h1>
      <p style={{ marginTop: 0, marginBottom: 24, color: '#666', fontSize: '0.9rem' }}>
        React + FastAPI + Postgres + worker
      </p>

      <section style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Health</h2>
        <HealthBadge state={healthState} />
        {health && (
          <span style={{ marginLeft: 12, fontSize: '0.8rem', color: '#888' }}>
            status: {health.status} · db: {health.db}
          </span>
        )}
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Add item</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={newLabel}
            onChange={e => setNewLabel(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !adding && newLabel.trim() && handleAdd()}
            placeholder="Item label"
            style={{ flex: 1, padding: '6px 10px', fontSize: '0.95rem', border: '1px solid #ccc', borderRadius: 4 }}
            disabled={adding}
          />
          <button
            onClick={handleAdd}
            disabled={adding || !newLabel.trim()}
            style={{
              padding: '6px 16px',
              background: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              cursor: adding || !newLabel.trim() ? 'not-allowed' : 'pointer',
              opacity: adding || !newLabel.trim() ? 0.5 : 1,
            }}
          >
            {adding ? 'Adding…' : 'Add'}
          </button>
        </div>
        {addError && (
          <p style={{ marginTop: 6, color: '#ef4444', fontSize: '0.85rem' }}>{addError}</p>
        )}
      </section>

      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>
          Items{' '}
          <span style={{ fontWeight: 400, color: '#888', fontSize: '0.85rem' }}>
            (auto-refreshes every 5s)
          </span>
        </h2>
        {items.length === 0 ? (
          <p style={{ color: '#999', fontSize: '0.9rem' }}>No items yet.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '4px 8px' }}>ID</th>
                <th style={{ padding: '4px 8px' }}>Label</th>
                <th style={{ padding: '4px 8px' }}>Source</th>
                <th style={{ padding: '4px 8px' }}>Created at</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '4px 8px', color: '#9ca3af' }}>{item.id}</td>
                  <td style={{ padding: '4px 8px' }}>{item.label}</td>
                  <td style={{ padding: '4px 8px' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '1px 7px',
                        borderRadius: 9999,
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background: item.source === 'worker' ? '#ede9fe' : '#dbeafe',
                        color: item.source === 'worker' ? '#7c3aed' : '#1d4ed8',
                      }}
                    >
                      {item.source}
                    </span>
                  </td>
                  <td style={{ padding: '4px 8px', color: '#6b7280' }}>
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2 style={{ fontSize: '1rem', marginBottom: 4 }}>Chaos controls</h2>
        <p style={{ marginTop: 0, marginBottom: 12, color: '#888', fontSize: '0.85rem' }}>
          Trigger faults to see how the app responds.
        </p>
        <button
          onClick={handleCrash}
          disabled={crashPending}
          style={{
            padding: '7px 18px',
            background: '#dc2626',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            cursor: crashPending ? 'not-allowed' : 'pointer',
            fontWeight: 600,
            opacity: crashPending ? 0.6 : 1,
          }}
        >
          {crashPending ? 'Sending crash…' : 'Crash the API'}
        </button>
        <span style={{ marginLeft: 10, fontSize: '0.8rem', color: '#9ca3af' }}>
          POST /api/chaos/crash — hard-exits the API process
        </span>
        {crashMsg && (
          <p style={{ marginTop: 8, color: '#b45309', fontSize: '0.85rem' }}>{crashMsg}</p>
        )}
      </section>
    </div>
  )
}
