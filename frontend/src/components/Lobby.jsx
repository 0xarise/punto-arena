import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_URL } from '../config'
import useContract from '../hooks/useContract'

export default function Lobby({ wallet }) {
  const [wager, setWager] = useState('0.01')
  const [matchId, setMatchId] = useState('')
  const [nickname, setNickname] = useState(() => {
    try {
      return localStorage.getItem('punto_nick') || ''
    } catch {
      return ''
    }
  })
  const [loading, setLoading] = useState(false)
  const [queueStatus, setQueueStatus] = useState(null)
  const [error, setError] = useState(null)
  const [txStatus, setTxStatus] = useState('')
  const [directGameId, setDirectGameId] = useState('')
  const navigate = useNavigate()
  const pollRef = useRef(null)
  const { createGame: createOnChain, loading: contractLoading } = useContract()
  const trimmedNickname = nickname.trim()

  useEffect(() => {
    const checkQueue = () => fetch(`${API_URL}/queue/status`).then(r => r.json()).then(setQueueStatus).catch(() => {})
    checkQueue()
    const id = setInterval(checkQueue, 5000)
    return () => { clearInterval(id); clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('punto_nick', nickname)
    } catch {
      // ignore
    }
  }, [nickname])

  const findMatch = async () => {
    if (!wallet) return setError('Connect wallet first')
    setLoading(true)
    setError(null)
    setTxStatus('')
    setDirectGameId('')

    try {
      setTxStatus('Joining matchmaking queue...')
      const res = await fetch(`${API_URL}/match/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: wallet, wallet, wager, nickname: trimmedNickname })
      })
      const data = await res.json()

      if (data.matched) {
        if (data.you_are === 'player1') {
          setTxStatus('Match found! Creating on-chain game...')
          const { gameId: onChainId } = await createOnChain(wager)
          await fetch(`${API_URL}/match/${data.match_id}/chain-id`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ on_chain_id: parseInt(onChainId), wager })
          })
          navigate(`/game/${data.match_id}?onChainId=${onChainId}&wager=${wager}&role=player1`)
          return
        }

        setTxStatus('Match found! Waiting for on-chain game...')
        const waitForChain = setInterval(async () => {
          const matchRes = await fetch(`${API_URL}/match/${data.match_id}`)
          if (!matchRes.ok) return
          const matchData = await matchRes.json()
          if (matchData.on_chain_id) {
            clearInterval(waitForChain)
            navigate(`/game/${data.match_id}?onChainId=${matchData.on_chain_id}&wager=${matchData.wager || wager}&role=player2`)
          }
        }, 2000)
        setTimeout(() => {
          clearInterval(waitForChain)
          setTxStatus('Timeout - waiting for on-chain game.')
        }, 300000)
        return
      }

      setTxStatus(`In queue (position ${data.queue_position}). Waiting...`)

      pollRef.current = setInterval(async () => {
        const r = await fetch(`${API_URL}/match/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: wallet, wallet, wager, nickname: trimmedNickname })
      })
        const d = await r.json()
        if (d.matched) {
          clearInterval(pollRef.current)
          if (d.you_are === 'player1') {
            setTxStatus('Match found! Creating on-chain game...')
            const { gameId: onChainId } = await createOnChain(wager)
            await fetch(`${API_URL}/match/${d.match_id}/chain-id`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ on_chain_id: parseInt(onChainId), wager })
            })
            navigate(`/game/${d.match_id}?onChainId=${onChainId}&wager=${wager}&role=player1`)
          } else {
            setTxStatus('Match found! Waiting for on-chain game...')
            const waitForChain = setInterval(async () => {
              const matchRes = await fetch(`${API_URL}/match/${d.match_id}`)
              if (!matchRes.ok) return
              const matchData = await matchRes.json()
              if (matchData.on_chain_id) {
                clearInterval(waitForChain)
                navigate(`/game/${d.match_id}?onChainId=${matchData.on_chain_id}&wager=${matchData.wager || wager}&role=player2`)
              }
            }, 2000)
            setTimeout(() => clearInterval(waitForChain), 300000)
          }
        }
      }, 3000)
      setTimeout(() => {
        clearInterval(pollRef.current)
        setTxStatus('Timeout - no opponent found.')
      }, 300000)
    } catch (e) {
      console.error('Create game error:', e)
      setError(e.message || 'Failed to create game')
      setTxStatus('')
    } finally {
      setLoading(false)
    }
  }

  const joinGame = async () => {
    if (!wallet) return setError('Connect wallet first')
    if (!matchId.trim()) return setError('Enter match ID or on-chain game ID')
    setLoading(true)
    setError(null)
    setTxStatus('')
    setDirectGameId('')
    
    try {
      // Check if it's a match_id (UUID) or on-chain gameId (number)
      const isOnChainId = /^\d+$/.test(matchId.trim())
      
      if (isOnChainId) {
        // Direct on-chain join - ensure backend session exists
        const chainId = matchId.trim()
        const directRes = await fetch(`${API_URL}/match/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ player_id: wallet, wallet, match_id: chainId, on_chain_id: parseInt(chainId), wager, nickname: trimmedNickname })
      })
        if (!directRes.ok) {
          const message = directRes.status === 403 ? 'Match full' : 'Match not found'
          throw new Error(message)
        }
        navigate(`/game/${chainId}?onChainId=${chainId}&wager=${wager}&role=player2`)
        return
      }
      
      // Existing match_id join
      const res = await fetch(`${API_URL}/match/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: wallet, wallet, match_id: matchId.trim(), nickname: trimmedNickname })
      })
      
      if (!res.ok) {
        const message = res.status === 403 ? 'Match full' : 'Match not found'
        throw new Error(message)
      }
      
      const data = await res.json()
      // Get on-chain ID and wager from response if available
      const onChainId = data.on_chain_id || ''
      const matchWager = data.wager || wager
      
      navigate(`/game/${matchId.trim()}?onChainId=${onChainId}&wager=${matchWager}&role=player2`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const createDirectGame = async () => {
    if (!wallet) return setError('Connect wallet first')
    setLoading(true)
    setError(null)
    setTxStatus('')
    setDirectGameId('')
    try {
      setTxStatus('Creating on-chain game...')
      const { gameId: onChainId } = await createOnChain(wager)
      // Create backend match using on-chain ID as match_id
      await fetch(`${API_URL}/match/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: wallet, wallet, match_id: onChainId, on_chain_id: parseInt(onChainId), wager, nickname: trimmedNickname })
      })
      setDirectGameId(onChainId)
      setTxStatus(`On-chain game created (ID ${onChainId}). Share it with opponent.`)
      navigate(`/game/${onChainId}?onChainId=${onChainId}&wager=${wager}&role=player1`)
    } catch (e) {
      console.error('Direct create error:', e)
      setError(e.message || 'Failed to create on-chain game')
      setTxStatus('')
    } finally {
      setLoading(false)
    }
  }

  const isLoading = loading || contractLoading

  return (
    <div className="lobby">
      {!wallet && <div className="info-msg">Connect your wallet to play Punto Arena</div>}

      <div className="section">
        <h2 className="section-title">🎮 Play</h2>
        <div className="create-game">
          <div className="input-group">
            <label>Nickname (optional)</label>
            <input
              type="text"
              value={nickname}
              onChange={e => setNickname(e.target.value)}
              placeholder="Enter your nickname"
              disabled={isLoading}
              maxLength={20}
            />
          </div>
          <div className="input-group">
            <label>Wager (MON)</label>
            <input 
              type="number" 
              step="0.001" 
              min="0.001" 
              value={wager} 
              onChange={e => setWager(e.target.value)} 
              disabled={isLoading}
            />
          </div>
          <button className="btn btn-primary" onClick={findMatch} disabled={isLoading || !wallet}>
            {isLoading ? 'Processing...' : `🎲 Find Match (Queue)`}
          </button>
          {txStatus && <p style={{ margin: '8px 0', color: 'var(--primary)', fontSize: '0.9em' }}>{txStatus}</p>}
          <p style={{ margin: '8px 0', color: 'var(--text-muted)', fontSize: '0.9em' }}>
            Joins matchmaking queue. On-chain game is created only after a match is found.
          </p>
        </div>
        {queueStatus && <p style={{ marginTop: 12, color: 'var(--text-muted)' }}>Players in queue: {queueStatus.queue_size}</p>}
      </div>

      <div className="section">
        <h2 className="section-title">🧾 Create Direct On-Chain Game</h2>
        <div className="create-game">
          <div className="input-group">
            <label>Wager (MON)</label>
            <input 
              type="number" 
              step="0.001" 
              min="0.001" 
              value={wager} 
              onChange={e => setWager(e.target.value)} 
              disabled={isLoading}
            />
          </div>
          <button className="btn btn-secondary" onClick={createDirectGame} disabled={isLoading || !wallet}>
            {isLoading ? 'Processing...' : `Create On-Chain Game (${wager} MON)`}
          </button>
          {directGameId && (
            <div style={{ marginTop: 12 }}>
              <div style={{ color: 'var(--text-muted)' }}>Game ID:</div>
              <div style={{ fontSize: '1.1em', fontWeight: 600 }}>{directGameId}</div>
              <button
                className="btn btn-secondary"
                style={{ marginTop: 8 }}
                onClick={() => navigator.clipboard.writeText(directGameId)}
              >
                Copy Game ID
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="section">
        <h2 className="section-title">🔗 Join Game</h2>
        <div className="create-game">
          <div className="input-group">
            <label>Game ID (on-chain) or Match ID</label>
            <input 
              type="text" 
              value={matchId} 
              onChange={e => setMatchId(e.target.value)} 
              placeholder="Enter ID (e.g. 1, 2, or UUID)" 
              disabled={isLoading}
            />
          </div>
          <div className="input-group">
            <label>Wager (must match creator)</label>
            <input 
              type="number" 
              step="0.001" 
              min="0.001" 
              value={wager} 
              onChange={e => setWager(e.target.value)}
              disabled={isLoading}
            />
          </div>
          <button className="btn btn-secondary" onClick={joinGame} disabled={isLoading || !wallet}>
            {isLoading ? 'Processing...' : 'Join Game'}
          </button>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      <div className="section">
        <h2 className="section-title">📜 Rules</h2>
        <ul style={{ lineHeight: 1.8, color: 'var(--text-muted)' }}>
          <li>Place cards on 6×6 grid adjacent to existing cards</li>
          <li>Same color: higher value beats lower</li>
          <li>Different color: can always place on top</li>
          <li>First to 2 round wins takes the match + wager!</li>
        </ul>
      </div>
    </div>
  )
}
