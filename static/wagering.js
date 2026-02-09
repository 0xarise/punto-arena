// Punto Arena - Wagering Frontend with MetaMask
// UX Overhaul: Refresh resilience, turn indicators, wallet-only login

// ============================================================================
// SOUND EFFECTS (Web Audio API - no files needed)
// ============================================================================

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx;

function getAudioCtx() {
    if (!audioCtx) audioCtx = new AudioCtx();
    return audioCtx;
}

function playTone(freq, duration, type = 'sine', volume = 0.3) {
    try {
        const ctx = getAudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.value = freq;
        gain.gain.value = volume;
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + duration);
    } catch (e) { /* audio not available */ }
}

function soundCardPlace() { playTone(880, 0.06, 'sine', 0.15); }
function soundOpponentMove() { playTone(587, 0.08, 'triangle', 0.12); }
function soundYourTurn() { playTone(1047, 0.04, 'sine', 0.1); setTimeout(() => playTone(1319, 0.04, 'sine', 0.1), 50); }
function soundInvalid() { playTone(180, 0.15, 'sawtooth', 0.12); }
function soundWin() {
    // Victory fanfare — triumphant ascending chord
    playTone(523, 0.15, 'sine', 0.25);
    setTimeout(() => playTone(659, 0.15, 'sine', 0.25), 100);
    setTimeout(() => playTone(784, 0.15, 'sine', 0.25), 200);
    setTimeout(() => { playTone(1047, 0.4, 'sine', 0.3); playTone(523, 0.4, 'sine', 0.15); }, 300);
    setTimeout(() => playTone(1047, 0.3, 'triangle', 0.15), 600);
}
function soundRekt() {
    // REKT — heavy bass drop + distorted descend
    playTone(80, 0.5, 'sawtooth', 0.3);
    playTone(120, 0.4, 'square', 0.15);
    setTimeout(() => playTone(60, 0.6, 'sawtooth', 0.25), 200);
    setTimeout(() => playTone(40, 0.8, 'sawtooth', 0.2), 500);
}

let provider, signer, contract, walletAddress;
let socket;
let gameState = {
    roomId: null,
    playerRole: null,
    playerName: null,
    selectedCard: null,
    myTurn: false,
    wager: 0,
    opponentAddress: null,
    boardState: null,
    myCards: [],
    status: 'idle', // idle, waiting, playing, finished
    mode: null // 'pvp' or 'ai'
};

const SESSION_KEY = 'punto_wager_session';
const GAME_STATE_KEY = 'punto_game_state';

// Contract ABI (minimal - just what we need)
const CONTRACT_ABI = [
    "function createGame(string roomId) payable returns (uint256)",
    "function joinGame(uint256 gameId) payable",
    "function getGameByRoomId(string roomId) view returns (tuple(address player1, address player2, uint256 wager, uint8 state, address winner, uint256 createdAt, string roomId))",
    "function roomIdToGameId(string roomId) view returns (uint256)",
    "function calculatePayout(uint256 wager) view returns (uint256 payout, uint256 fee)",
    "event GameCreated(uint256 indexed gameId, address indexed player1, uint256 wager, string roomId)",
    "event GameJoined(uint256 indexed gameId, address indexed player2)",
    "event GameFinished(uint256 indexed gameId, address indexed winner, uint256 payout, uint256 fee)"
];

const CONTRACT_ADDRESS = "0x8B55cAB0051b542cB56D46d06E65CE8C0eFe48A5"; // Monad mainnet v1

// Monad Network Config
const MONAD_NETWORK = {
    chainId: '0x8F', // 143 in hex
    chainName: 'Monad',
    rpcUrls: ['https://rpc.monad.xyz'],
    nativeCurrency: {
        name: 'MON',
        symbol: 'MON',
        decimals: 18
    },
    blockExplorerUrls: ['https://monadexplorer.com']
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function normalizeAddress(address) {
    return (address || '').toLowerCase();
}

function truncateAddress(address) {
    if (!address) return 'Unknown';
    return address.slice(0, 6) + '...' + address.slice(-4);
}

function saveSession() {
    if (!gameState.roomId || !walletAddress) return;
    const session = {
        roomId: gameState.roomId,
        address: walletAddress,
        role: gameState.playerRole,
        wager: gameState.wager,
        opponentAddress: gameState.opponentAddress,
        status: gameState.status,
        timestamp: Date.now()
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

function saveGameState() {
    if (!gameState.roomId) return;
    const state = {
        roomId: gameState.roomId,
        boardState: gameState.boardState,
        myCards: gameState.myCards,
        myTurn: gameState.myTurn,
        status: gameState.status,
        timestamp: Date.now()
    };
    localStorage.setItem(GAME_STATE_KEY, JSON.stringify(state));
}

function loadSession() {
    try {
        const raw = localStorage.getItem(SESSION_KEY);
        if (!raw) return null;
        const session = JSON.parse(raw);
        // Expire after 1 hour
        if (Date.now() - session.timestamp > 3600000) {
            clearSession();
            return null;
        }
        return session;
    } catch (error) {
        console.warn('Failed to load session:', error);
        return null;
    }
}

function loadGameState() {
    try {
        const raw = localStorage.getItem(GAME_STATE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (error) {
        return null;
    }
}

function clearSession() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(GAME_STATE_KEY);
}

// ============================================================================
// WALLET CONNECTION (Auto-reconnect on refresh)
// ============================================================================

document.getElementById('connect-wallet').addEventListener('click', connectWallet);

// No auto-connect — user must explicitly click "Connect Wallet"
// (auto-connecting is bad web3 UX practice)

async function connectWallet() {
    if (typeof window.ethereum === 'undefined') {
        alert('MetaMask not installed! Please install MetaMask.');
        return;
    }

    try {
        showLoading('Connecting wallet...');
        
        // Request account access
        await window.ethereum.request({ method: 'eth_requestAccounts' });

        provider = new ethers.providers.Web3Provider(window.ethereum);
        signer = provider.getSigner();
        walletAddress = await signer.getAddress();

        // Check network (Monad mainnet)
        const network = await provider.getNetwork();
        console.log('Connected to network:', network);

        // Switch to Monad if not already
        if (network.chainId !== 143) {
            showLoading('Switching to Monad network...');
            try {
                await window.ethereum.request({
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: MONAD_NETWORK.chainId }],
                });
            } catch (switchError) {
                // Chain not added, add it
                if (switchError.code === 4902) {
                    await window.ethereum.request({
                        method: 'wallet_addEthereumChain',
                        params: [MONAD_NETWORK],
                    });
                } else {
                    throw switchError;
                }
            }
            // Refresh provider after network switch
            provider = new ethers.providers.Web3Provider(window.ethereum);
            signer = provider.getSigner();
        }

        // Get balance
        const balance = await provider.getBalance(walletAddress);
        const balanceInMON = ethers.utils.formatEther(balance);

        // Update UI - use truncated address as name
        document.getElementById('wallet-address').textContent = truncateAddress(walletAddress);
        document.getElementById('wallet-balance').textContent = parseFloat(balanceInMON).toFixed(4);

        document.getElementById('connect-wallet').style.display = 'none';
        document.getElementById('wallet-info').style.display = 'block';
        document.getElementById('mode-selection').style.display = 'block';

        // Initialize contract
        contract = new ethers.Contract(CONTRACT_ADDRESS, CONTRACT_ABI, signer);

        console.log('✅ Wallet connected:', walletAddress);
        hideLoading();

        // Initialize socket and check for session restore
        initializeSocket();

        // Check for existing session to restore
        const session = loadSession();
        
        if (window.JOIN_ROOM_ID) {
            // Auto-join from URL
            console.log('Auto-joining room:', window.JOIN_ROOM_ID);
            await autoJoinWageredRoom(window.JOIN_ROOM_ID);
        } else if (session && normalizeAddress(session.address) === normalizeAddress(walletAddress)) {
            // Restore previous session
            console.log('🔄 Restoring session:', session.roomId);
            await rejoinWageredRoom(session);
        }

    } catch (error) {
        console.error('Error connecting wallet:', error);
        hideLoading();
        alert('Failed to connect wallet: ' + error.message);
    }
}

// Handle account changes
if (typeof window.ethereum !== 'undefined') {
    window.ethereum.on('accountsChanged', (accounts) => {
        if (accounts.length === 0) {
            // User disconnected
            clearSession();
            location.reload();
        } else if (walletAddress && normalizeAddress(accounts[0]) !== normalizeAddress(walletAddress)) {
            // User switched accounts
            clearSession();
            location.reload();
        }
    });
}

// ============================================================================
// LOADING SPINNER
// ============================================================================

function showToast(message) {
    soundInvalid();

    // Shake the board
    const board = document.getElementById('game-board-wager');
    if (board) {
        board.classList.add('shake');
        setTimeout(() => board.classList.remove('shake'), 400);
    }

    // Show toast
    let toast = document.getElementById('game-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'game-toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
}

function showLoading(message = 'Loading...') {
    let loader = document.getElementById('loading-overlay');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'loading-overlay';
        loader.className = 'loading';
        loader.innerHTML = `
            <div class="spinner"></div>
            <p id="loading-message">${message}</p>
        `;
        document.body.appendChild(loader);
    } else {
        document.getElementById('loading-message').textContent = message;
        loader.style.display = 'flex';
    }
}

function hideLoading() {
    const loader = document.getElementById('loading-overlay');
    if (loader) {
        loader.style.display = 'none';
    }
}

// ============================================================================
// WAGER CALCULATION
// ============================================================================

document.getElementById('wager-amount').addEventListener('input', updateWagerCalculation);

function updateWagerCalculation() {
    const wager = parseFloat(document.getElementById('wager-amount').value) || 0;
    const totalPot = wager * 2;
    const fee = totalPot * 0.05;  // 5% fee
    const payout = totalPot - fee;

    document.getElementById('total-pot').textContent = totalPot.toFixed(4);
    document.getElementById('winner-payout').textContent = payout.toFixed(4);
    document.getElementById('protocol-fee').textContent = fee.toFixed(4);
}

updateWagerCalculation();

// ============================================================================
// SESSION + JOIN FLOW
// ============================================================================

async function autoJoinWageredRoom(roomId) {
    gameState.roomId = roomId;
    gameState.playerRole = 'player2';
    gameState.status = 'joining';
    saveSession();

    showLoading('Joining game...');
    updateTxStatus('Checking on-chain game...');
    
    try {
        await ensureOnChainJoin(roomId);
        emitJoin(roomId);
    } catch (error) {
        hideLoading();
        updateTxStatus('❌ ' + error.message);
    }
}

async function rejoinWageredRoom(session) {
    gameState.roomId = session.roomId;
    gameState.playerRole = session.role;
    gameState.wager = session.wager || 0;
    gameState.opponentAddress = session.opponentAddress;
    gameState.status = session.status || 'waiting';
    
    showLoading('Reconnecting to game...');
    updateTxStatus('Rejoining room...');
    
    // If we were player2, ensure on-chain join
    if (gameState.playerRole === 'player2') {
        try {
            await ensureOnChainJoin(session.roomId);
        } catch (error) {
            console.warn('On-chain rejoin check failed:', error);
        }
    }
    
    emitJoin(session.roomId);
}

function emitJoin(roomId) {
    socket.emit('join_wagered_room', {
        room_id: roomId,
        name: truncateAddress(walletAddress),
        address: walletAddress
    });
}

async function ensureOnChainJoin(roomId) {
    if (!contract) return;

    const gameId = await contract.roomIdToGameId(roomId);
    if (gameId.eq(0)) {
        throw new Error('Room not found on-chain');
    }

    const game = await contract.getGameByRoomId(roomId);
    const wagerWei = game.wager;
    gameState.wager = parseFloat(ethers.utils.formatEther(wagerWei));

    const player2Address = normalizeAddress(game.player2);
    if (player2Address && player2Address !== normalizeAddress(ethers.constants.AddressZero)) {
        // Already joined on-chain
        socket.emit('wager_confirmed', { room_id: roomId });
        return;
    }

    updateTxStatus('Depositing wager on-chain...');
    showLoading('Confirm transaction in MetaMask...');
    
    const tx = await contract.joinGame(gameId, { value: wagerWei });
    updateTxStatus(`Transaction sent: ${tx.hash.slice(0, 10)}...`);
    showLoading('Waiting for confirmation...');
    
    await tx.wait();
    updateTxStatus('✅ Wager confirmed! Waiting for game to start...');
    socket.emit('wager_confirmed', { room_id: roomId });
}

// ============================================================================
// CREATE WAGERED ROOM (Wallet-only login - no nickname)
// ============================================================================

async function createWageredRoom() {
    const wagerAmount = parseFloat(document.getElementById('wager-amount').value);

    if (!walletAddress) {
        alert('Please connect wallet first!');
        return;
    }

    if (wagerAmount <= 0) {
        alert('Wager must be greater than 0!');
        return;
    }

    try {
        // Step 1: Check balance before doing anything
        if (provider) {
            const balance = await provider.getBalance(walletAddress);
            const wagerWei = ethers.utils.parseEther(wagerAmount.toString());
            if (balance.lt(wagerWei)) {
                const balMon = parseFloat(ethers.utils.formatEther(balance)).toFixed(4);
                showToast(`Insufficient balance: ${balMon} MON (need ${wagerAmount} MON)`);
                return;
            }
        }

        showLoading('Creating game room...');

        // Step 2: Create room on server
        const response = await fetch('/api/create_wagered_room', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wager: wagerAmount })
        });

        const data = await response.json();
        gameState.roomId = data.room_id;
        gameState.wager = wagerAmount;
        gameState.playerRole = 'player1';
        gameState.status = 'waiting';
        saveSession();

        document.getElementById('wager-setup').style.display = 'none';

        updateTxStatus('Creating on-chain game...');
        showLoading('Confirm transaction in MetaMask...');

        // Step 3: Create game on blockchain (before showing invite link)
        if (contract) {
            const tx = await contract.createGame(data.room_id, {
                value: ethers.utils.parseEther(wagerAmount.toString())
            });

            updateTxStatus(`Transaction sent: ${tx.hash.slice(0, 10)}...`);
            showLoading('Waiting for confirmation...');

            await tx.wait();

            updateTxStatus('✅ Wager deposited! Waiting for opponent...');
        }

        // Step 4: Only show invite link AFTER successful on-chain deposit
        document.getElementById('invite-link-wager').value = data.invite_link;
        document.getElementById('invite-section-wager').style.display = 'block';
        updateOpponentStatus('Share the invite link above');

        hideLoading();

        // Step 5: Join room via WebSocket
        emitJoin(data.room_id);

    } catch (error) {
        console.error('Error creating wagered room:', error);
        hideLoading();
        // If tx failed, clean up — show wager setup again so user can retry
        if (gameState.status === 'waiting') {
            document.getElementById('wager-setup').style.display = 'block';
            document.getElementById('invite-section-wager').style.display = 'none';
            gameState.roomId = null;
            gameState.status = null;
            saveSession();
        }
        showToast(error.reason || error.message || 'Transaction failed');
    }
}

function updateTxStatus(message) {
    const el = document.getElementById('tx-status');
    if (el) {
        el.innerHTML = `<p>${message}</p>`;
    }
}

function updateOpponentStatus(message) {
    const el = document.getElementById('opponent-status-wager');
    if (el) {
        el.textContent = message;
    }
}

function copyInviteWager() {
    const inviteLink = document.getElementById('invite-link-wager');
    inviteLink.select();
    document.execCommand('copy');
    
    // Visual feedback
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = originalText, 1500);
}

// ============================================================================
// SOCKET.IO
// ============================================================================

function initializeSocket() {
    if (socket && socket.connected) return;
    
    socket = io(window.location.origin, {
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000
    });

    socket.on('connect', () => {
        console.log('✅ Connected to server');
        hideLoading();
        
        // If we have a session, rejoin automatically
        if (gameState.roomId && gameState.status !== 'finished') {
            console.log('🔄 Socket reconnected, rejoining room...');
            emitJoin(gameState.roomId);
        }
    });

    socket.on('disconnect', () => {
        console.log('❌ Disconnected from server');
        updateOpponentStatus('⚠️ Connection lost, reconnecting...');
    });

    socket.on('reconnect', () => {
        console.log('🔄 Reconnected to server');
        if (gameState.roomId) {
            emitJoin(gameState.roomId);
        }
    });

    socket.on('player_joined', (data) => {
        console.log('Player joined:', data);
        hideLoading();
        
        if (data.wager) {
            gameState.wager = data.wager;
        }
        
        // Update opponent info
        if (data.role && data.role !== gameState.playerRole) {
            const opponentName = data.name || 'Opponent';
            gameState.opponentAddress = data.address;
            updateOpponentStatus(`✅ ${opponentName} joined!`);
            updateTxStatus('Both players ready! Starting game...');
            saveSession();
        }
    });

    socket.on('ai_room_created', (data) => {
        console.log('🤖 AI room created:', data);
        gameState.roomId = data.room_id;
        gameState.mode = 'ai';
        gameState.playerRole = 'player1';
        gameState.status = 'playing';
        saveSession();
    });

    socket.on('game_start', (data) => {
        console.log('🎮 Game starting:', data);
        hideLoading();

        if (data.mode) {
            gameState.mode = data.mode;
        }
        if (data.wager !== undefined) {
            gameState.wager = data.wager;
        }
        gameState.status = 'playing';
        saveSession();

        startGameUI(data);
    });

    socket.on('move_made', (data) => {
        console.log('Move made:', data);
        updateGameState(data);
    });

    socket.on('game_state_restored', (data) => {
        console.log('🔄 State restored:', data);
        hideLoading();
        
        if (data.your_role) {
            gameState.playerRole = data.your_role;
        }
        if (data.wager) {
            gameState.wager = data.wager;
        }
        gameState.status = 'playing';
        saveSession();
        
        startGameUI(data);
    });

    socket.on('waiting_for_wager', (data) => {
        updateTxStatus(data.message);
    });

    socket.on('player_status', (data) => {
        console.log('Player status:', data);
        
        // Skip if it's our own status
        if (data.role === gameState.playerRole) return;
        
        const statusLabel = data.status === 'disconnected'
            ? '⚠️ Opponent disconnected'
            : data.status === 'reconnected'
                ? '✅ Opponent reconnected'
                : '✅ Opponent connected';
        
        const name = data.name || truncateAddress(gameState.opponentAddress);
        updateOpponentStatus(`${statusLabel} (${name})`);
    });

    socket.on('error', (data) => {
        hideLoading();
        console.error('Socket error:', data);
        // Restore turn state if game is in progress (invalid move rejected by server)
        if (gameState.status === 'playing') {
            gameState.myTurn = true;
            updateTurnIndicator();
        }
        showToast(data.message);
    });
}

// ============================================================================
// GAME UI
// ============================================================================

function startGameUI(data) {
    document.getElementById('invite-section-wager').style.display = 'none';
    document.getElementById('wager-setup').style.display = 'none';
    document.getElementById('mode-selection').style.display = 'none';
    document.getElementById('game-area-wager').style.display = 'block';

    // Update wager display — hide in AI mode
    const wagerDisplay = document.querySelector('.wager-display');
    if (gameState.mode === 'ai') {
        const engineName = gameState.aiEngine === 'claude' ? 'Claude' : gameState.aiEngine === 'openai' ? 'OpenAI' : 'Heuristic';
        if (wagerDisplay) wagerDisplay.innerHTML = `<h3><span class="ai-mode-badge">vs ${engineName} AI</span></h3><p>Practice mode — no wager</p>`;
    } else {
        gameState.wager = data.wager || gameState.wager;
        document.getElementById('current-wager').textContent = gameState.wager;
        const payout = gameState.wager * 2 * 0.95;
        document.getElementById('game-winner-payout').textContent = payout.toFixed(4);
    }

    // Set player names (use wallet addresses)
    const p1Name = data.player1.name;
    const p2Name = data.player2.name;
    document.getElementById('player1-name-wager').textContent = p1Name;
    document.getElementById('player2-name-wager').textContent = p2Name;

    // Initialize board
    initializeBoard();
    
    // Restore board state if available
    if (data.board) {
        updateBoard(data.board);
        gameState.boardState = data.board;
        saveGameState();
    }

    // Set cards based on role
    if (gameState.playerRole === 'player1') {
        const myCards = data.your_cards || data.player1.cards;
        renderMyCards(myCards);
        gameState.myCards = myCards;
        document.getElementById('player2-cards-count-wager').textContent = 
            (data.player2.cards || []).length;
        gameState.myTurn = (data.current_turn === 'player1');
    } else {
        const myCards = data.your_cards || data.player2.cards;
        renderMyCards(myCards);
        gameState.myCards = myCards;
        document.getElementById('player2-cards-count-wager').textContent = 
            (data.player1.cards || []).length;
        gameState.myTurn = (data.current_turn === 'player2');
    }

    // Store opponent info
    const opponentData = gameState.playerRole === 'player1' ? data.player2 : data.player1;
    updateOpponentStatus(`✅ vs ${opponentData.name}`);

    updateTurnIndicator();
    saveGameState();
}

function initializeBoard() {
    const board = document.getElementById('game-board-wager');
    board.innerHTML = '';

    for (let row = 0; row < 6; row++) {
        for (let col = 0; col < 6; col++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.row = row;
            cell.dataset.col = col;
            cell.addEventListener('click', () => handleCellClick(row, col));
            board.appendChild(cell);
        }
    }
}

function renderMyCards(cards) {
    const container = document.getElementById('player1-cards-wager');
    container.innerHTML = '';

    cards.forEach(card => {
        // Support both new dict format {value, color} and legacy integer format
        const cardValue = (typeof card === 'object' && card !== null) ? card.value : card;
        const cardColor = (typeof card === 'object' && card !== null) ? card.color : null;
        const cardObj = (typeof card === 'object' && card !== null) ? card : { value: card, color: null };

        const cardEl = document.createElement('div');
        cardEl.className = 'card';
        if (cardColor) {
            cardEl.classList.add('color-' + cardColor);
        }
        cardEl.textContent = cardValue;
        cardEl.addEventListener('click', () => selectCard(cardObj, cardEl));
        container.appendChild(cardEl);
    });
}

function selectCard(cardObj, cardElement) {
    if (!gameState.myTurn) {
        // Visual feedback that it's not their turn
        cardElement.classList.add('shake');
        setTimeout(() => cardElement.classList.remove('shake'), 300);
        return;
    }

    document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
    // cardObj is {value, color} dict
    gameState.selectedCard = cardObj;
    cardElement.classList.add('selected');
}

function handleCellClick(row, col) {
    if (!gameState.myTurn) return;

    if (!gameState.selectedCard) {
        // Hint to select a card first
        const indicator = document.getElementById('turn-indicator-wager');
        indicator.textContent = '👆 Select a card first!';
        setTimeout(updateTurnIndicator, 1500);
        return;
    }

    // Send card_value + card_color (selectedCard is now {value, color} dict)
    const moveEvent = gameState.mode === 'ai' ? 'ai_make_move' : 'make_move';
    const movePayload = {
        card: gameState.selectedCard.value,
        card_value: gameState.selectedCard.value,
        card_color: gameState.selectedCard.color,
        row: row,
        col: col
    };
    if (gameState.mode === 'ai') {
        movePayload.room_id = gameState.roomId;
    }
    socket.emit(moveEvent, movePayload);

    gameState.selectedCard = null;
    gameState.myTurn = false;
    document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
    updateTurnIndicator();
}

function updateGameState(data) {
    // Update board
    updateBoard(data.board);
    gameState.boardState = data.board;

    // Update cards
    if (gameState.playerRole === 'player1') {
        renderMyCards(data.player1_cards);
        gameState.myCards = data.player1_cards;
        document.getElementById('player2-cards-count-wager').textContent = data.player2_cards.length;
    } else {
        renderMyCards(data.player2_cards);
        gameState.myCards = data.player2_cards;
        document.getElementById('player2-cards-count-wager').textContent = data.player1_cards.length;
    }

    // Update turn
    const wasMyTurn = gameState.myTurn;
    gameState.myTurn = (data.next_turn === gameState.playerRole);

    // Sound feedback
    if (data.player === gameState.playerRole) {
        soundCardPlace();
    } else {
        soundOpponentMove();
        if (gameState.myTurn) setTimeout(soundYourTurn, 150);
    }

    updateTurnIndicator();
    saveGameState();

    // Check for winner
    if (data.winner) {
        gameState.status = 'finished';
        saveSession();
        setTimeout(() => showGameOver(data), 500);
    }
}

function updateBoard(boardState) {
    for (let row = 0; row < 6; row++) {
        for (let col = 0; col < 6; col++) {
            const cell = document.querySelector(`#game-board-wager [data-row="${row}"][data-col="${col}"]`);
            const cellData = boardState[row][col];

            if (cellData) {
                cell.textContent = cellData.card;
                cell.className = 'cell ' + cellData.player;
                if (cellData.color) {
                    cell.classList.add('color-' + cellData.color);
                }
            } else {
                cell.textContent = '';
                cell.className = 'cell';
            }
        }
    }
}

function updateTurnIndicator() {
    const indicator = document.getElementById('turn-indicator-wager');
    const p1Name = document.getElementById('player1-name-wager');
    const p2Name = document.getElementById('player2-name-wager');
    
    // Remove all pulse classes
    p1Name.classList.remove('pulse-name');
    p2Name.classList.remove('pulse-name');
    indicator.classList.remove('my-turn');
    
    if (gameState.myTurn) {
        indicator.textContent = '🟢 YOUR TURN!';
        indicator.style.color = '#10b981';
        indicator.classList.add('my-turn');
        
        // Highlight my name
        if (gameState.playerRole === 'player1') {
            p1Name.classList.add('pulse-name');
        } else {
            p2Name.classList.add('pulse-name');
        }
    } else {
        indicator.textContent = '🔴 Waiting for opponent...';
        indicator.style.color = '#ef4444';
        
        // Highlight opponent's name with pulse
        if (gameState.playerRole === 'player1') {
            p2Name.classList.add('pulse-name');
        } else {
            p1Name.classList.add('pulse-name');
        }
    }
}

function showGameOver(data) {
    const modal = document.getElementById('game-over-modal-wager');
    const winnerText = document.getElementById('winner-text-wager');

    const didIWin = (data.winner === gameState.playerRole);

    if (didIWin) {
        soundWin();
        winnerText.innerHTML = 'VICTORY';
        winnerText.style.cssText = 'font-family: Orbitron, monospace; font-size: 48px; font-weight: 900; letter-spacing: 6px; color: #fbbf24; text-shadow: 0 0 30px rgba(251,191,36,0.6), 0 0 60px rgba(251,191,36,0.3); animation: victory-glow 1.5s ease-in-out infinite;';
        modal.style.background = 'rgba(0, 0, 0, 0.85)';

        if (gameState.mode !== 'ai' && gameState.wager > 0) {
            const payout = gameState.wager * 2 * 0.95;
            document.getElementById('final-payout').textContent = payout.toFixed(4);
            document.getElementById('payout-display').style.display = 'block';
        } else {
            document.getElementById('payout-display').style.display = 'none';
        }
    } else {
        soundRekt();
        winnerText.innerHTML = 'REKT';
        winnerText.style.cssText = 'font-family: Orbitron, monospace; font-size: 64px; font-weight: 900; letter-spacing: 8px; color: #ef4444; text-shadow: 0 0 40px rgba(239,68,68,0.8), 0 0 80px rgba(239,68,68,0.4); animation: rekt-shake 0.5s ease-in-out;';
        modal.style.background = 'rgba(40, 0, 0, 0.92)';
        document.getElementById('payout-display').style.display = 'none';
    }

    // Clear session on game over
    clearSession();

    modal.style.display = 'flex';
}

// ============================================================================
// MODE SELECTION
// ============================================================================

function showAIDifficulty() {
    document.getElementById('ai-difficulty').style.display = 'block';
}

function selectMode(mode, engine) {
    gameState.mode = mode;

    if (mode === 'pvp') {
        document.getElementById('ai-difficulty').style.display = 'none';
        document.getElementById('mode-selection').style.display = 'none';
        document.getElementById('wager-setup').style.display = 'block';
    } else if (mode === 'ai') {
        document.getElementById('mode-selection').style.display = 'none';
        const engineLabel = engine === 'heuristic' ? 'Easy AI' : engine === 'claude' ? 'Claude AI' : 'OpenAI';
        showLoading(`Starting game vs ${engineLabel}...`);
        gameState.aiEngine = engine || 'heuristic';
        socket.emit('create_ai_room', { wallet_address: walletAddress, engine: engine || 'heuristic' });
    }
}

function playAgain() {
    // Reset game state but keep wallet connected
    gameState.roomId = null;
    gameState.playerRole = null;
    gameState.status = null;
    gameState.myTurn = false;
    gameState.mode = null;
    gameState.aiEngine = null;
    clearSession();

    // Hide everything game-related
    document.getElementById('game-over-modal-wager').style.display = 'none';
    document.getElementById('game-area-wager').style.display = 'none';
    document.getElementById('invite-section-wager').style.display = 'none';
    document.getElementById('wager-setup').style.display = 'none';
    const aiDiff = document.getElementById('ai-difficulty');
    if (aiDiff) aiDiff.style.display = 'none';

    // Show mode selection (wallet is still connected)
    document.getElementById('mode-selection').style.display = 'block';
}

// Expose functions to global scope for HTML onclick handlers
window.createWageredRoom = createWageredRoom;
window.copyInviteWager = copyInviteWager;
window.selectMode = selectMode;
window.showAIDifficulty = showAIDifficulty;
window.playAgain = playAgain;
