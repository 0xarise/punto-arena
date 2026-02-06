// API Configuration
export const API_URL = import.meta.env.VITE_API_URL || 'https://analyst-named-carry-epson.trycloudflare.com'
export const WS_URL = import.meta.env.VITE_WS_URL || 'wss://analyst-named-carry-epson.trycloudflare.com'

// Monad Network Configuration
export const MONAD_CHAIN = {
  chainId: 143,
  chainIdHex: '0x8f',
  name: 'Monad Mainnet',
  rpcUrl: 'https://rpc.monad.xyz',
  currency: {
    name: 'MON',
    symbol: 'MON',
    decimals: 18
  },
  explorer: 'https://monadvision.com'
}

// Contract addresses
export const CONTRACTS = {
  puntoArena: '0x85AeB20d5EdC1032B7E4F4c6aA8b7a1Da94793A7'
}

// Card colors
export const CARD_COLORS = {
  red: '#ef4444',
  blue: '#3b82f6',
  green: '#22c55e',
  yellow: '#eab308'
}
