import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import Card from './Card'
import useWebSocket from '../hooks/useWebSocket'
import useContract from '../hooks/useContract'
import { API_URL } from '../config'

export default function GameBoard({ wallet }) {
  const { matchId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  
  const onChainId = searchParams.get('onChainId')
  const wager = searchParams.get('wager') || '0.01'
  const role = searchParams.get('role') || 'player2'

  const [resolvedOnChainId, setResolvedOnChainId] = useState(onChainId)
  const [resolvedWager, setResolvedWager] = useState(wager)
  const [resolvedRole, setResolvedRole] = useState(role)
  
  const { connected, gameState, error, sendMove, sendNextRound } = useWebSocket(matchId, wallet)
  const { joinGame, submitResult, claimWinnings, claimTimeout, getGameInfo, getTimeout, loading: contractLoading, error: contractError } = useContract()
  
  const [selectedCardIndex, setSelectedCardIndex] = useState(null)
  const [joinedOnChain, setJoinedOnChain] = useState(role === 'player1') // Player1 already joined
  const [joiningOnChain, setJoiningOnChain] = useState(false)
  const [autoJoinAttempted, setAutoJoinAttempted] = useState(false)
  const [claimStatus, setClaimStatus] = useState('')
  const [claimed, setClaimed] = useState(false)
  const [chainInfo, setChainInfo] = useState(null)
  const [chainTimeout, setChainTimeout] = useState(null)
  const [refundStatus, setRefundStatus] = useState('')
  const [nowTs, setNowTs] = useState(Date.now())

  const localNickname = useMemo(() => {
    try {
      return localStorage.getItem('punto_nick') || ''
    } catch {
      return ''
    }
  }, [])

  const effectiveRole = gameState?.you_are || resolvedRole
  const isPlayer1 = effectiveRole === 'player1'
  const myTurn = gameState?.current_player === (isPlayer1 ? 1 : 2)
  const roundOver = gameState?.round_over || gameState?.round_end || gameState?.state === 'round_end'
  const matchOver = gameState?.match_over || gameState?.match_end || gameState?.state === 'finished'
  const iWon = matchOver && gameState?.you_are === `player${gameState.match_winner || gameState.winner}`
  const normalizedWallet = wallet?.toLowerCase()
  const isParticipantOnChain = chainInfo && (
    normalizedWallet === chainInfo.player1?.toLowerCase() ||
    normalizedWallet === chainInfo.player2?.toLowerCase()
  )

  const chainStateLabel = chainInfo?.state === 0 ? 'Pending' :
    chainInfo?.state === 1 ? 'Active' :
    chainInfo?.state === 2 ? 'Finished' :
    chainInfo?.state === 3 ? 'Cancelled' : 'Unknown'

  const opponentDepositConfirmed = chainInfo?.state === 1 && chainInfo?.player2 && chainInfo?.player2 !== '0x0000000000000000000000000000000000000000'
  const depositStatus = isPlayer1
    ? (opponentDepositConfirmed ? 'Opponent deposit confirmed' : 'Waiting for opponent deposit')
    : (joinedOnChain ? 'Deposit confirmed' : 'Deposit required')

  const timeoutRemaining = useMemo(() => {
    if (!chainInfo || !chainTimeout) return null
    const remaining = (chainInfo.createdAt + chainTimeout) - Math.floor(nowTs / 1000)
    return remaining
  }, [chainInfo, chainTimeout, nowTs])

  const myHand = useMemo(() => {
    if (!gameState?.hands) return []
    return isPlayer1 ? gameState.hands.player1 || [] : gameState.hands.player2 || []
  }, [gameState?.hands, isPlayer1])

  const nicknames = gameState?.nicknames || {}
  const myNickname = nicknames[effectiveRole] || localNickname
  const opponentRole = isPlayer1 ? 'player2' : 'player1'
  const opponentNickname = nicknames[opponentRole]
  const myLabel = myNickname ? `You (${myNickname})` : 'You'
  const opponentLabel = opponentNickname ? `Opponent (${opponentNickname})` : 'Opponent'

  const selectedCard = selectedCardIndex !== null ? myHand[selectedCardIndex] : null

  const validMoves = useMemo(() => {
    if (!gameState?.grid || !selectedCard) return []
    const grid = gameState.grid, card = selectedCard, valid = []
    const hasCards = grid.some(r => r.some(c => c))
    
    for (let row = 0; row < 6; row++) {
      for (let col = 0; col < 6; col++) {
        if (!hasCards) { valid.push({ row, col }); continue }
        const adj = [[row-1,col],[row+1,col],[row,col-1],[row,col+1],[row-1,col-1],[row-1,col+1],[row+1,col-1],[row+1,col+1]]
        const hasAdj = adj.some(([r,c]) => r>=0 && r<6 && c>=0 && c<6 && grid[r]?.[c])
        if (!hasAdj) continue
        const cell = grid[row][col]
        if (!cell || (cell.color === card.color ? card.value > cell.value : true)) valid.push({ row, col })
      }
    }
    return valid
  }, [gameState?.grid, selectedCard])

  const gameStarted = gameState?.started || ['active', 'round_end', 'finished'].includes(gameState?.state)

  const gameCode = resolvedOnChainId || matchId
  const inviteLink = useMemo(() => {
    if (!matchId || typeof window === 'undefined') return ''
    const params = new URLSearchParams()
    if (resolvedOnChainId) params.set('onChainId', resolvedOnChainId)
    if (resolvedWager) params.set('wager', resolvedWager)
    if (resolvedRole) params.set('role', resolvedRole)
    const qs = params.toString()
    return `${window.location.origin}/game/${matchId}${qs ? `?${qs}` : ''}`
  }, [matchId, resolvedOnChainId, resolvedWager, resolvedRole])

  const handleCopyGameId = useCallback(() => {
    if (!gameCode) return
    navigator.clipboard.writeText(gameCode)
  }, [gameCode])

  const handleCopyInvite = useCallback(() => {
    if (!inviteLink) return
    navigator.clipboard.writeText(inviteLink)
  }, [inviteLink])
  
  // Status with on-chain info
  let status = !connected ? 'Connecting...' : !gameStarted ? 'Waiting for opponent...'
    : matchOver ? (iWon ? '🎉 You Won!' : '😔 You Lost')
    : roundOver ? `Round over! ${gameState.round_winner === (isPlayer1 ? 1 : 2) ? 'You won!' : 'Opponent won!'}`
    : myTurn ? 'Your Turn' : "Opponent's Turn"
  
  if (resolvedOnChainId && !chainInfo) {
    status = 'Waiting for on-chain game...'
  } else if (!joinedOnChain && resolvedOnChainId) {
    status = 'Join game on-chain to play'
  }
  if (joiningOnChain) {
    status = 'Joining on-chain...'
  }

  const handleJoinOnChain = useCallback(async () => {
    if (!resolvedOnChainId || joinedOnChain || joiningOnChain) return
    setJoiningOnChain(true)
    try {
      await joinGame(resolvedOnChainId, resolvedWager)
      setJoinedOnChain(true)
    } catch (e) {
      console.error('Failed to join on-chain:', e)
    } finally {
      setJoiningOnChain(false)
    }
  }, [resolvedOnChainId, joinedOnChain, joiningOnChain, joinGame, resolvedWager])

  const handleClaimWinnings = useCallback(async () => {
    if (!resolvedOnChainId || !iWon || claimed) return
    setClaimStatus('Getting signature from oracle...')
    
    try {
      // Get signature from backend
      const signRes = await fetch(`${API_URL}/sign-result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          match_id: matchId,
          on_chain_id: parseInt(resolvedOnChainId),
          chain_id: 143 // Monad
        })
      })
      
      if (!signRes.ok) throw new Error('Failed to get signature')
      const payload = await signRes.json()
      const rawSignature = typeof payload.signature === 'string'
        ? payload.signature
        : payload.signature?.signature
      if (!rawSignature) {
        throw new Error('Invalid signature payload')
      }
      const signature = rawSignature.startsWith('0x') ? rawSignature : `0x${rawSignature}`
      
      setClaimStatus('Submitting result to contract...')
      await submitResult(resolvedOnChainId, wallet, signature)
      
      setClaimStatus('Claiming winnings...')
      await claimWinnings(resolvedOnChainId)
      
      setClaimStatus('🎉 Winnings claimed!')
      setClaimed(true)
    } catch (e) {
      console.error('Claim failed:', e)
      setClaimStatus(`Error: ${e.message}`)
    }
  }, [resolvedOnChainId, iWon, claimed, matchId, submitResult, claimWinnings, wallet])

  const handleClaimTimeout = useCallback(async () => {
    if (!resolvedOnChainId || !isParticipantOnChain) return
    setRefundStatus('Submitting refund claim...')
    try {
      await claimTimeout(resolvedOnChainId)
      setRefundStatus('✅ Refund claimed')
    } catch (e) {
      setRefundStatus(`Error: ${e.message}`)
    }
  }, [resolvedOnChainId, isParticipantOnChain, claimTimeout])

  // Auto-join on-chain for player2 when they load the page
  useEffect(() => {
    if (effectiveRole === 'player1') {
      setJoinedOnChain(true)
    }
  }, [effectiveRole])

  useEffect(() => {
    if (effectiveRole !== 'player2') return
    if (!resolvedOnChainId || joinedOnChain || joiningOnChain || !wallet) return
    if (autoJoinAttempted) return
    if (!chainInfo) return
    if (chainInfo?.player2 && chainInfo.player2 !== '0x0000000000000000000000000000000000000000') {
      if (chainInfo.player2.toLowerCase() === wallet.toLowerCase()) {
        setJoinedOnChain(true)
        setAutoJoinAttempted(true)
      }
      return
    }
    if (chainInfo.state !== 0) return
    setAutoJoinAttempted(true)
    handleJoinOnChain()
  }, [effectiveRole, resolvedOnChainId, joinedOnChain, joiningOnChain, wallet, chainInfo, handleJoinOnChain, autoJoinAttempted])

  useEffect(() => {
    if (resolvedOnChainId || !matchId) return
    const loadMatch = async () => {
      try {
        const res = await fetch(`${API_URL}/match/${matchId}`)
        if (!res.ok) return
        const data = await res.json()
        if (data.on_chain_id) {
          setResolvedOnChainId(String(data.on_chain_id))
        }
        if (data.wager) {
          setResolvedWager(String(data.wager))
        }
      } catch {
        // ignore
      }
    }
    loadMatch()
  }, [resolvedOnChainId, matchId])

  useEffect(() => {
    if (gameState?.on_chain_id && !resolvedOnChainId) {
      setResolvedOnChainId(String(gameState.on_chain_id))
    }
    if (gameState?.wager && resolvedWager === wager) {
      setResolvedWager(String(gameState.wager))
    }
  }, [gameState?.on_chain_id, gameState?.wager, resolvedOnChainId, resolvedWager, wager])

  useEffect(() => {
    if (gameState?.you_are && gameState?.you_are !== resolvedRole) {
      setResolvedRole(gameState.you_are)
    }
  }, [gameState?.you_are, resolvedRole])

  useEffect(() => {
    if (!matchId) return
    const key = `punto_match_${matchId}`
    const payload = {
      onChainId: resolvedOnChainId,
      wager: resolvedWager,
      role: resolvedRole
    }
    localStorage.setItem(key, JSON.stringify(payload))
  }, [matchId, resolvedOnChainId, resolvedWager, resolvedRole])

  useEffect(() => {
    if (!matchId || resolvedOnChainId) return
    const key = `punto_match_${matchId}`
    try {
      const stored = JSON.parse(localStorage.getItem(key) || '{}')
      if (stored.onChainId) setResolvedOnChainId(String(stored.onChainId))
      if (stored.wager) setResolvedWager(String(stored.wager))
      if (stored.role) setResolvedRole(String(stored.role))
    } catch {
      // ignore
    }
  }, [matchId, resolvedOnChainId])

  useEffect(() => {
    if (!resolvedOnChainId) return
    let mounted = true
    const loadChainInfo = async () => {
      const info = await getGameInfo(resolvedOnChainId)
      if (mounted) setChainInfo(info)
    }
    loadChainInfo()
    const id = setInterval(loadChainInfo, 5000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [resolvedOnChainId, getGameInfo])

  useEffect(() => {
    const id = setInterval(() => setNowTs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!resolvedOnChainId) return
    const loadTimeout = async () => {
      const timeout = await getTimeout()
      if (timeout) setChainTimeout(timeout)
    }
    loadTimeout()
  }, [resolvedOnChainId, getTimeout])

  useEffect(() => {
    if (selectedCardIndex === null) return
    if (!myHand[selectedCardIndex]) {
      setSelectedCardIndex(null)
    }
  }, [myHand, selectedCardIndex])

  useEffect(() => {
    if (!myTurn || roundOver) {
      setSelectedCardIndex(null)
    }
  }, [myTurn, roundOver])


  if (!wallet) return (
    <div className="section">
      <div className="error-msg">Connect wallet to play</div>
      <button className="btn btn-secondary" onClick={() => navigate('/')}>Back</button>
    </div>
  )

  // Show join on-chain button for player2
  if (!joinedOnChain && resolvedOnChainId && effectiveRole === 'player2') {
    return (
      <div className="section" style={{ textAlign: 'center', padding: '40px 20px' }}>
        <h2>Join Game #{resolvedOnChainId}</h2>
        <p style={{ color: 'var(--text-muted)', margin: '20px 0' }}>
          Wager: <strong>{resolvedWager} MON</strong>
        </p>
        {chainInfo && (
          <p style={{ color: 'var(--text-muted)' }}>On-chain status: {chainStateLabel}</p>
        )}
        <button 
          className="btn btn-primary" 
          onClick={handleJoinOnChain}
          disabled={joiningOnChain || contractLoading}
          style={{ fontSize: '1.2em', padding: '16px 32px' }}
        >
          {joiningOnChain ? 'Joining...' : `Join Game (${resolvedWager} MON)`}
        </button>
        {contractError && <div className="error-msg" style={{ marginTop: 20 }}>{contractError}</div>}
        <button className="btn btn-secondary" onClick={() => navigate('/')} style={{ marginTop: 20 }}>
          Cancel
        </button>
      </div>
    )
  }

  if (!gameStarted) {
    return (
      <div className="section">
        <div className="game-status">{status}</div>
        {resolvedOnChainId && (
          <p style={{ color: 'var(--text-muted)' }}>
            Game #{resolvedOnChainId} • Wager: {resolvedWager} MON • On-chain: {chainStateLabel} • {depositStatus}
          </p>
        )}
        {error && <div className="error-msg">{error}</div>}
        {isParticipantOnChain && chainInfo && chainTimeout && (chainInfo.state === 0 || chainInfo.state === 1) && (
          <div style={{ marginTop: 12 }}>
            {timeoutRemaining !== null && timeoutRemaining > 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>
                Refund available in {Math.ceil(timeoutRemaining / 60)} min
              </p>
            ) : (
              <button className="btn btn-secondary" onClick={handleClaimTimeout} disabled={contractLoading}>
                Claim Timeout Refund
              </button>
            )}
            {refundStatus && <p style={{ marginTop: 8, color: 'var(--primary)' }}>{refundStatus}</p>}
          </div>
        )}
        <button className="btn btn-secondary" onClick={() => navigate('/')}>Back</button>
      </div>
    )
  }

  return (
    <div className="game-container">
      <div className="game-header">
        <button className="btn btn-secondary" onClick={() => navigate('/')}>← Leave</button>
        <div className="score-board">
          <div className="score-item"><span className="score-label">{myLabel}</span>
            <span className="score-value">{isPlayer1 ? gameState?.score?.player1 || 0 : gameState?.score?.player2 || 0}</span></div>
          <div className="score-item"><span className="score-label">{opponentLabel}</span>
            <span className="score-value">{isPlayer1 ? gameState?.score?.player2 || 0 : gameState?.score?.player1 || 0}</span></div>
        </div>
      </div>

      {resolvedOnChainId && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9em', marginBottom: 8 }}>
          Game #{resolvedOnChainId} • Wager: {resolvedWager} MON • On-chain: {chainStateLabel} • {depositStatus}
        </div>
      )}
      {gameCode && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={handleCopyGameId}>
            Copy Game ID
          </button>
          <button className="btn btn-secondary" onClick={handleCopyInvite}>
            Copy Invite Link
          </button>
        </div>
      )}

      <div className={`game-status ${myTurn && !roundOver ? 'your-turn' : ''}`}>{status}</div>
      {error && <div className="error-msg">{error}</div>}
      {roundOver && !matchOver && <button className="btn btn-primary" onClick={sendNextRound}>Next Round</button>}
      
      {/* Claim winnings button */}
      {matchOver && iWon && resolvedOnChainId && !claimed && (
        <div style={{ textAlign: 'center', margin: '20px 0' }}>
          <button 
            className="btn btn-primary"
            onClick={handleClaimWinnings}
            disabled={contractLoading}
            style={{ fontSize: '1.1em' }}
          >
            💰 Claim Winnings ({parseFloat(resolvedWager) * 2 * 0.95} MON)
          </button>
          {claimStatus && <p style={{ marginTop: 10, color: 'var(--primary)' }}>{claimStatus}</p>}
        </div>
      )}
      
      {claimed && (
        <div style={{ textAlign: 'center', margin: '20px 0', color: 'var(--success)' }}>
          ✅ Winnings claimed successfully!
        </div>
      )}

      <div className="board-section">
        <div className="grid">
          {Array(6).fill(0).map((_, row) => Array(6).fill(0).map((_, col) => {
            const cell = gameState?.grid?.[row]?.[col]
            const isValid = validMoves.some(m => m.row === row && m.col === col)
            const canClick = myTurn && isValid && !roundOver && selectedCardIndex !== null
            return (
              <div key={`${row}-${col}`} className={`cell ${isValid && myTurn ? 'valid' : ''} ${!canClick ? 'disabled' : ''}`}
                onClick={() => {
                  if (!canClick) return
                  sendMove(row, col, selectedCardIndex)
                  setSelectedCardIndex(null)
                }}>
                {cell && <Card color={cell.color} value={cell.value} />}
              </div>
            )
          }))}
        </div>

        {myHand.length > 0 && myTurn && !roundOver && (
          <div className="current-card-section">
            <div className="current-card-label">Your Cards</div>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center' }}>
              {myHand.map((card, index) => (
                <div key={`${card.color}-${card.value}-${index}`}
                  className={`card-select ${selectedCardIndex === index ? 'selected' : ''}`}
                  onClick={() => setSelectedCardIndex(index)}>
                  <Card color={card.color} value={card.value} size="large" />
                </div>
              ))}
            </div>
            <p style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 14 }}>
              Select a card, then click a highlighted cell
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
