import { useState, useEffect, useCallback, useRef } from 'react'
import { API_URL, WS_URL } from '../config'

export default function useWebSocket(matchId, playerId) {
  const [connected, setConnected] = useState(false)
  const [gameState, setGameState] = useState(null)
  const [error, setError] = useState(null)
  const [lastMessage, setLastMessage] = useState(null)
  const [readyToConnect, setReadyToConnect] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const ensureMatch = useCallback(async () => {
    if (!matchId || !playerId) return false
    try {
      const res = await fetch(`${API_URL}/match/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: playerId, wallet: playerId, match_id: matchId })
      })
      if (!res.ok) {
        const message = res.status === 403 ? 'Match full' : 'Match not found'
        throw new Error(message)
      }
      setError(null)
      return true
    } catch (err) {
      setError(err.message || 'Failed to join match')
      return false
    }
  }, [matchId, playerId])

  const connect = useCallback(() => {
    if (!matchId || !playerId) return

    const ws = new WebSocket(`${WS_URL}/ws/${matchId}/${playerId}`)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
      setError(null)
      // Send ready signal
      ws.send(JSON.stringify({ type: 'ready' }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log('WS message:', data)
      setLastMessage(data)

      switch (data.type) {
        case 'state':
          setGameState(prev => {
            const next = prev ? { ...prev, ...data } : data
            if (data.state && data.state !== 'waiting') {
              next.started = true
            }
            return next
          })
          break
        case 'game_start':
          setGameState(prev => ({ ...prev, ...data, started: true }))
          break
        case 'move_result':
          setGameState(prev => ({ ...prev, ...data }))
          break
        case 'round_start':
          setGameState(prev => ({
            ...prev,
            ...data,
            round_end: false,
            round_over: false,
            round_winner: null,
            started: true
          }))
          break
        case 'error':
          setError(data.message)
          break
        case 'player_disconnected':
          setError('Opponent disconnected')
          break
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
      setError('Connection error')
    }

    ws.onclose = () => {
      console.log('WebSocket closed')
      setConnected(false)
      
      // Auto reconnect after 3s
      reconnectRef.current = setTimeout(() => {
        if (matchId && playerId) {
          connect()
        }
      }, 3000)
    }
  }, [matchId, playerId])

  useEffect(() => {
    let active = true

    const setup = async () => {
      const ok = await ensureMatch()
      if (active) {
        setReadyToConnect(ok)
      }
    }

    setup()

    return () => {
      active = false
      setReadyToConnect(false)
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
      }
    }
  }, [ensureMatch])

  useEffect(() => {
    if (readyToConnect) {
      connect()
    }
  }, [readyToConnect, connect])

  const sendMove = useCallback((row, col, cardIndex) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'move',
        row,
        col,
        card_index: cardIndex
      }))
    }
  }, [])

  const sendNextRound = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'next_round' }))
    }
  }, [])

  return {
    connected,
    gameState,
    error,
    lastMessage,
    sendMove,
    sendNextRound
  }
}
