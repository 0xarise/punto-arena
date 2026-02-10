// Punto AI - Multiplayer WebSocket Client

let socket;
let gameState = {
    roomId: null,
    playerRole: null,
    selectedCard: null,
    myTurn: false
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // Check if joining via invite link
    const pathMatch = window.location.pathname.match(/\/join\/(.+)/);
    if (pathMatch) {
        const roomId = pathMatch[1];
        autoJoinRoom(roomId);
    }

    initializeSocket();
});

function initializeSocket() {
    socket = io(window.location.origin);

    socket.on('connect', () => {
        console.log('✅ Connected:', socket.id);
    });

    socket.on('player_joined', (data) => {
        console.log('Player joined:', data);
        if (data.players_count === 2) {
            document.getElementById('invite-section').style.display = 'none';
        }
    });

    socket.on('game_start', (data) => {
        console.log('Game starting:', data);
        startGameUI(data);
    });

    socket.on('move_made', (data) => {
        console.log('Move made:', data);
        updateGameState(data);
    });

    socket.on('game_end', (data) => {
        console.log('Game ended:', data);
        showGameOver(data);
    });

    socket.on('error', (data) => {
        alert('Error: ' + data.message);
    });
}

async function createRoom(mode) {
    const playerName = document.getElementById('player-name')?.value || 'Player1';
    const aiModel = document.getElementById('ai-model-select')?.value;

    const response = await fetch('/api/create_room', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            mode: mode,
            ai_model: aiModel,
            wager: 0
        })
    });

    const data = await response.json();
    gameState.roomId = data.room_id;

    // Join the room
    socket.emit('join_room', {
        room_id: data.room_id,
        name: playerName
    });

    gameState.playerRole = 'player1';

    // Show invite link for PvP
    if (mode === 'pvp') {
        document.getElementById('invite-link').value = data.invite_link;
        document.getElementById('invite-section').style.display = 'block';
    }
}

function autoJoinRoom(roomId) {
    const playerName = prompt('Enter your name:', 'Player2');
    gameState.roomId = roomId;

    socket.emit('join_room', {
        room_id: roomId,
        name: playerName || 'Player2'
    });

    gameState.playerRole = 'player2';
    document.getElementById('setup-screen').style.display = 'none';
}

function copyInvite() {
    const inviteLink = document.getElementById('invite-link');
    inviteLink.select();
    document.execCommand('copy');
    alert('Invite link copied!');
}

function startGameUI(data) {
    // Hide setup, show game
    document.getElementById('setup-screen').style.display = 'none';
    document.getElementById('game-area').style.display = 'block';

    // Set player names
    document.getElementById('player1-name').textContent = data.player1.name;
    document.getElementById('player2-name').textContent = data.player2.name;

    // Initialize board
    initializeBoard();

    // Set cards based on role
    if (gameState.playerRole === 'player1') {
        renderMyCards(data.player1.cards);
        document.getElementById('player2-cards-count').textContent = data.player2.cards.length;
        gameState.myTurn = true;
    } else {
        renderMyCards(data.player2.cards);
        document.getElementById('player2-cards-count').textContent = data.player1.cards.length;
        gameState.myTurn = false;
    }

    updateTurnIndicator();
}

function initializeBoard() {
    const board = document.getElementById('game-board');
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
    const container = document.getElementById('player1-cards');
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
        alert('Not your turn!');
        return;
    }

    document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
    // cardObj is {value, color} dict
    gameState.selectedCard = cardObj;
    cardElement.classList.add('selected');
}

function handleCellClick(row, col) {
    if (!gameState.myTurn) {
        alert('Not your turn!');
        return;
    }

    if (!gameState.selectedCard) {
        alert('Select a card first!');
        return;
    }

    // Send move to server (selectedCard is now {value, color} dict)
    socket.emit('make_move', {
        card: gameState.selectedCard.value,
        card_value: gameState.selectedCard.value,
        card_color: gameState.selectedCard.color,
        row: row,
        col: col
    });

    gameState.selectedCard = null;
    gameState.myTurn = false;
}

function updateGameState(data) {
    // Update board
    updateBoard(data.board);

    // Update cards
    if (gameState.playerRole === 'player1') {
        renderMyCards(data.player1_cards);
        document.getElementById('player2-cards-count').textContent = data.player2_cards.length;
    } else {
        renderMyCards(data.player2_cards);
        document.getElementById('player2-cards-count').textContent = data.player1_cards.length;
    }

    // Update turn
    gameState.myTurn = (data.next_turn === gameState.playerRole);
    updateTurnIndicator();

    // Check for winner
    if (data.winner) {
        setTimeout(() => showGameOver(data), 500);
    }
}

function updateBoard(boardState) {
    for (let row = 0; row < 6; row++) {
        for (let col = 0; col < 6; col++) {
            const cell = document.querySelector(`[data-row="${row}"][data-col="${col}"]`);
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
    const indicator = document.getElementById('turn-indicator');
    indicator.textContent = gameState.myTurn ? '🟢 YOUR TURN - MAKE A MOVE!' : '🔴 Opponent\'s turn';
    indicator.style.color = gameState.myTurn ? '#10b981' : '#ef4444';

    // Add/remove pulse animation
    if (gameState.myTurn) {
        indicator.classList.add('my-turn');
    } else {
        indicator.classList.remove('my-turn');
    }

    if (gameState.myTurn) {
        // Browser notification
        if (Notification.permission === 'granted') {
            new Notification('🎮 Punto AI', {
                body: 'Your turn to play!',
                icon: '/static/punto-icon.png'
            });
        }

        // Sound alert
        playTurnSound();

        // Flash tab title
        flashTabTitle();
    }
}

function playTurnSound() {
    // Simple beep using Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (e) {
        console.log('Sound not available');
    }
}

let titleFlashInterval;
function flashTabTitle() {
    // Stop any existing flash
    if (titleFlashInterval) {
        clearInterval(titleFlashInterval);
    }

    const originalTitle = document.title;
    let isFlashing = false;

    titleFlashInterval = setInterval(() => {
        document.title = isFlashing ? originalTitle : '🎮 YOUR TURN!';
        isFlashing = !isFlashing;
    }, 1000);

    // Stop flashing after 10 seconds or when user makes move
    setTimeout(() => {
        clearInterval(titleFlashInterval);
        document.title = originalTitle;
    }, 10000);
}

function showGameOver(data) {
    const modal = document.getElementById('game-over-modal');
    const winnerText = document.getElementById('winner-text');

    const didIWin = (data.winner === gameState.playerRole);

    winnerText.textContent = didIWin ? '🎉 You Won!' : '😔 You Lost';
    winnerText.style.color = didIWin ? '#10b981' : '#ef4444';

    if (data.payout > 0) {
        document.getElementById('payout-text').textContent =
            `Payout: $${data.payout}`;
        document.getElementById('payout-text').style.display = 'block';
    }

    modal.style.display = 'flex';
}

function rematch() {
    socket.emit('rematch', {});
    document.getElementById('game-over-modal').style.display = 'none';
}
