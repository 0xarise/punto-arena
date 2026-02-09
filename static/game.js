// Punto AI Web Game - Frontend JavaScript

let gameState = {
    gameId: null,
    selectedCard: null,
    humanCards: [],
    aiModel: null,
    turnCount: 0,
    costEstimate: 0
};

// Initialize game
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    setupEventListeners();
});

function setupEventListeners() {
    // AI model selection
    document.querySelectorAll('.ai-model-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const model = this.dataset.model;
            startNewGame(model);
        });
    });

    // Play again button
    document.getElementById('play-again-btn').addEventListener('click', function() {
        location.reload();
    });
}

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        document.getElementById('games-remaining').textContent = data.games_remaining;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function startNewGame(aiModel) {
    showLoading();

    try {
        const response = await fetch('/api/new_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ai_model: aiModel })
        });

        if (!response.ok) {
            const error = await response.json();
            alert(error.error || 'Failed to start game');
            hideLoading();
            return;
        }

        const data = await response.json();

        // Update game state
        gameState.gameId = data.game_id;
        gameState.humanCards = data.human_cards;
        gameState.aiModel = aiModel;
        gameState.costEstimate = data.cost_estimate;
        gameState.turnCount = 0;

        // Update UI
        document.getElementById('games-remaining').textContent = data.games_remaining;
        document.getElementById('game-cost').textContent = '$' + data.cost_estimate.toFixed(2);
        document.getElementById('ai-model-name').textContent = aiModel;

        // Hide setup, show game
        document.getElementById('game-setup').style.display = 'none';
        document.getElementById('game-area').style.display = 'grid';

        // Initialize board
        initializeBoard();
        renderPlayerCards();

        hideLoading();
    } catch (error) {
        console.error('Error starting game:', error);
        alert('Error starting game: ' + error.message);
        hideLoading();
    }
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

function renderPlayerCards() {
    const container = document.getElementById('player-cards');
    container.innerHTML = '';

    gameState.humanCards.forEach(card => {
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
    // Deselect previous card
    document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));

    // Select new card (cardObj is {value, color} dict)
    gameState.selectedCard = cardObj;
    cardElement.classList.add('selected');

    // Highlight valid moves on board
    highlightValidMoves();
}

function highlightValidMoves() {
    document.querySelectorAll('.cell').forEach(cell => {
        cell.classList.remove('valid-move');
    });

    if (!gameState.selectedCard) return;

    // selectedCard is now {value, color} - use .value for comparisons
    const selectedValue = gameState.selectedCard.value;

    // For simplicity, highlight all empty cells and cells with lower cards
    document.querySelectorAll('.cell').forEach(cell => {
        const cellValue = cell.textContent;
        if (!cellValue || parseInt(cellValue) < selectedValue) {
            cell.classList.add('valid-move');
        }
    });
}

async function handleCellClick(row, col) {
    if (!gameState.selectedCard) {
        alert('Please select a card first!');
        return;
    }

    showLoading();

    try {
        // selectedCard is now {value, color} dict
        const response = await fetch('/api/make_move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_id: gameState.gameId,
                card: gameState.selectedCard.value,
                card_value: gameState.selectedCard.value,
                card_color: gameState.selectedCard.color,
                row: row,
                col: col
            })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || 'Invalid move');
            hideLoading();
            return;
        }

        // Update board with human move
        updateBoard(data.board);

        if (data.status === 'game_over') {
            hideLoading();
            showGameOver(data);
            return;
        }

        // Show AI move info
        if (data.ai_move) {
            displayAIMove(data.ai_move);
            gameState.humanCards = data.human_cards;
            renderPlayerCards();
            document.getElementById('ai-cards-count').textContent = data.ai_cards_count;
        }

        // Update turn count
        gameState.turnCount++;
        document.getElementById('turn-count').textContent = Math.floor(gameState.turnCount / 2) + 1;

        // Clear selection
        gameState.selectedCard = null;
        document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
        document.querySelectorAll('.cell').forEach(c => c.classList.remove('valid-move'));

        hideLoading();

        // Check for game over after AI move
        if (data.status === 'game_over') {
            showGameOver(data);
        }

    } catch (error) {
        console.error('Error making move:', error);
        alert('Error making move: ' + error.message);
        hideLoading();
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

function displayAIMove(aiMove) {
    const aiMoveInfo = document.getElementById('ai-move-info');
    aiMoveInfo.style.display = 'block';

    // aiMove.card may be a dict {value, color} or plain integer
    const cardDisplay = (typeof aiMove.card === 'object' && aiMove.card !== null)
        ? aiMove.card.value : aiMove.card;
    document.getElementById('ai-card').textContent = cardDisplay;
    document.getElementById('ai-pos').textContent = aiMove.position.join(', ');
    document.getElementById('ai-confidence').textContent = aiMove.confidence;
    document.getElementById('ai-reasoning').textContent = aiMove.reasoning;
}

function showGameOver(data) {
    const modal = document.getElementById('game-over-modal');
    const title = document.getElementById('game-over-title');
    const message = document.getElementById('game-over-message');

    if (data.winner === 'human') {
        title.textContent = '🎉 You Won!';
        title.style.color = '#10b981';
    } else if (data.winner === 'ai') {
        title.textContent = '🤖 AI Won!';
        title.style.color = '#ef4444';
    } else {
        title.textContent = 'Draw!';
        title.style.color = '#f59e0b';
    }

    message.textContent = data.message;
    document.getElementById('final-turns').textContent = data.turns;

    modal.style.display = 'flex';
}

function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}
