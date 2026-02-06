import { useState, useCallback } from 'react'
import { BrowserProvider, Contract, parseEther, formatEther } from 'ethers'
import { CONTRACTS, MONAD_CHAIN } from '../config'
import PuntoArenaArtifact from '../abi/PuntoArena.json'

export default function useContract() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const getContract = useCallback(async (needSigner = true) => {
    if (!window.ethereum) throw new Error('No wallet found')
    
    const provider = new BrowserProvider(window.ethereum)
    
    // Ensure correct network
    const network = await provider.getNetwork()
    if (Number(network.chainId) !== MONAD_CHAIN.chainId) {
      throw new Error(`Wrong network. Please switch to ${MONAD_CHAIN.name}`)
    }
    
    if (needSigner) {
      const signer = await provider.getSigner()
      return new Contract(CONTRACTS.puntoArena, PuntoArenaArtifact.abi, signer)
    }
    return new Contract(CONTRACTS.puntoArena, PuntoArenaArtifact.abi, provider)
  }, [])

  const createGame = useCallback(async (wagerMON) => {
    setLoading(true)
    setError(null)
    try {
      const contract = await getContract(true)
      const wagerWei = parseEther(wagerMON.toString())
      
      console.log(`Creating game with wager: ${wagerMON} MON`)
      const tx = await contract.createGame({ value: wagerWei })
      console.log('Transaction sent:', tx.hash)
      
      const receipt = await tx.wait()
      console.log('Transaction confirmed:', receipt)
      
      // Find GameCreated event
      const event = receipt.logs.find(log => {
        try {
          const parsed = contract.interface.parseLog(log)
          return parsed?.name === 'GameCreated'
        } catch { return false }
      })
      
      if (!event) throw new Error('GameCreated event not found')
      
      const parsed = contract.interface.parseLog(event)
      const gameId = parsed.args[0] // gameId is first arg
      
      console.log('Game created with ID:', gameId.toString())
      return { gameId: gameId.toString(), txHash: tx.hash }
    } catch (e) {
      console.error('createGame error:', e)
      setError(e.message || 'Failed to create game')
      throw e
    } finally {
      setLoading(false)
    }
  }, [getContract])

  const joinGame = useCallback(async (gameId, wagerMON) => {
    setLoading(true)
    setError(null)
    try {
      const contract = await getContract(true)
      const wagerWei = parseEther(wagerMON.toString())
      
      console.log(`Joining game ${gameId} with wager: ${wagerMON} MON`)
      const tx = await contract.joinGame(gameId, { value: wagerWei })
      console.log('Transaction sent:', tx.hash)
      
      const receipt = await tx.wait()
      console.log('Game joined:', receipt)
      
      return { txHash: tx.hash }
    } catch (e) {
      console.error('joinGame error:', e)
      setError(e.message || 'Failed to join game')
      throw e
    } finally {
      setLoading(false)
    }
  }, [getContract])

  const submitResult = useCallback(async (gameId, winner, signature) => {
    setLoading(true)
    setError(null)
    try {
      const contract = await getContract(true)
      
      console.log(`Submitting result for game ${gameId}, winner: ${winner}`)
      const tx = await contract.submitResult(gameId, winner, signature)
      const receipt = await tx.wait()
      
      console.log('Result submitted:', receipt)
      return { txHash: tx.hash }
    } catch (e) {
      console.error('submitResult error:', e)
      setError(e.message || 'Failed to submit result')
      throw e
    } finally {
      setLoading(false)
    }
  }, [getContract])

  const claimWinnings = useCallback(async (gameId) => {
    setLoading(true)
    setError(null)
    try {
      const contract = await getContract(true)
      
      console.log(`Claiming winnings for game ${gameId}`)
      const tx = await contract.claimWinnings(gameId)
      const receipt = await tx.wait()
      
      console.log('Winnings claimed:', receipt)
      return { txHash: tx.hash }
    } catch (e) {
      console.error('claimWinnings error:', e)
      setError(e.message || 'Failed to claim winnings')
      throw e
    } finally {
      setLoading(false)
    }
  }, [getContract])

  const claimTimeout = useCallback(async (gameId) => {
    setLoading(true)
    setError(null)
    try {
      const contract = await getContract(true)
      const tx = await contract.claimTimeout(gameId)
      const receipt = await tx.wait()
      return { txHash: tx.hash, receipt }
    } catch (e) {
      console.error('claimTimeout error:', e)
      setError(e.message || 'Failed to claim timeout')
      throw e
    } finally {
      setLoading(false)
    }
  }, [getContract])

  const getGameInfo = useCallback(async (gameId) => {
    try {
      const contract = await getContract(false)
      const game = await contract.getGame(gameId)
      return {
        player1: game[0],
        player2: game[1],
        wager: formatEther(game[2]),
        state: Number(game[3]), // 0=Created, 1=Active, 2=Finished, 3=Cancelled
        winner: game[4],
        createdAt: Number(game[5])
      }
    } catch (e) {
      console.error('getGameInfo error:', e)
      return null
    }
  }, [getContract])

  const getTimeout = useCallback(async () => {
    try {
      const contract = await getContract(false)
      const timeout = await contract.getTimeout()
      return Number(timeout)
    } catch (e) {
      console.error('getTimeout error:', e)
      return null
    }
  }, [getContract])

  const getMinWager = useCallback(async () => {
    try {
      const contract = await getContract(false)
      const minWager = await contract.getMinWager()
      return formatEther(minWager)
    } catch (e) {
      return '0.001' // default
    }
  }, [getContract])

  return {
    loading,
    error,
    createGame,
    joinGame,
    submitResult,
    claimWinnings,
    claimTimeout,
    getGameInfo,
    getTimeout,
    getMinWager
  }
}
