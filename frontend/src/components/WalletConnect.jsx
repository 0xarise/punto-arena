import { useState } from 'react'
import { BrowserProvider } from 'ethers'
import { MONAD_CHAIN } from '../config'

export default function WalletConnect({ wallet, setWallet, signer, setSigner }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const connectWallet = async () => {
    if (!window.ethereum) {
      setError('Please install MetaMask')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const provider = new BrowserProvider(window.ethereum)
      const accounts = await provider.send('eth_requestAccounts', [])
      
      // Switch to Monad network
      try {
        await window.ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: MONAD_CHAIN.chainIdHex }]
        })
      } catch (switchError) {
        // Chain not added, add it
        if (switchError.code === 4902) {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: MONAD_CHAIN.chainIdHex,
              chainName: MONAD_CHAIN.name,
              rpcUrls: [MONAD_CHAIN.rpcUrl],
              nativeCurrency: MONAD_CHAIN.currency,
              blockExplorerUrls: [MONAD_CHAIN.explorer]
            }]
          })
        } else {
          throw switchError
        }
      }

      const newSigner = await provider.getSigner()
      const address = await newSigner.getAddress()
      
      setWallet(address)
      setSigner(newSigner)
    } catch (err) {
      console.error('Connect error:', err)
      setError(err.message || 'Failed to connect')
    } finally {
      setLoading(false)
    }
  }

  const disconnect = () => {
    setWallet(null)
    setSigner(null)
  }

  const formatAddress = (addr) => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  if (wallet) {
    return (
      <div className="wallet-connected">
        <span className="status-dot"></span>
        <span className="wallet-address">{formatAddress(wallet)}</span>
        <button className="btn btn-secondary" onClick={disconnect}>
          Disconnect
        </button>
      </div>
    )
  }

  return (
    <div>
      <button 
        className="btn btn-primary wallet-btn" 
        onClick={connectWallet}
        disabled={loading}
      >
        {loading ? (
          <span className="loading">
            <span className="spinner"></span>
            Connecting...
          </span>
        ) : (
          '🔗 Connect Wallet'
        )}
      </button>
      {error && <div className="error-msg" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  )
}
