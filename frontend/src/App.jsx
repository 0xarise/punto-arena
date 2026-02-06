import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom'
import WalletConnect from './components/WalletConnect'
import Lobby from './components/Lobby'
import GameBoard from './components/GameBoard'

function AppContent() {
  const [wallet, setWallet] = useState(null)
  const [signer, setSigner] = useState(null)
  const navigate = useNavigate()

  return (
    <div className="app">
      <header className="header">
        <div className="logo" onClick={() => navigate('/')}>🃏 Punto Arena</div>
        <WalletConnect 
          wallet={wallet} 
          setWallet={setWallet} 
          signer={signer}
          setSigner={setSigner}
        />
      </header>

      <Routes>
        <Route 
          path="/" 
          element={
            <Lobby 
              wallet={wallet} 
              signer={signer} 
            />
          } 
        />
        <Route 
          path="/game/:matchId" 
          element={
            <GameBoard 
              wallet={wallet} 
              signer={signer}
            />
          } 
        />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
