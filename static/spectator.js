// Punto Arena - Spectator Mode Client
// Read-only view of AI vs AI matches with live Socket.IO updates

(function () {
    'use strict';

    // ========================================================================
    // STATE
    // ========================================================================

    const state = {
        roomId: null,
        socket: null,
        connected: false,
        matchStarted: false,
        currentPlayer: null,  // 1 or 2
        moveHistory: [],      // {player, row, col, value, number}
        board: null,          // 6x6 array
        matchInfo: null,      // {agent1, agent2, wager, game_id}
    };

    const BOARD_SIZE = 6;
    const MAX_HISTORY_DISPLAY = 5;
    const MOVE_ANIMATION_DELAY = 500; // ms

    // ========================================================================
    // INITIALIZATION
    // ========================================================================

    function init() {
        extractRoomId();
        initializeBoard();
        connectSocket();
    }

    function extractRoomId() {
        // URL pattern: /spectate/<room_id>
        const match = window.location.pathname.match(/\/spectate\/(.+)/);
        if (match) {
            state.roomId = match[1];
            console.log('[Spectator] Room ID:', state.roomId);
        } else {
            console.error('[Spectator] No room_id found in URL');
            showWaitingMessage('Invalid spectator link', 'No room ID found in the URL.');
        }
    }

    function initializeBoard() {
        const board = document.getElementById('game-board');
        if (!board) return;
        board.innerHTML = '';

        for (let row = 0; row < BOARD_SIZE; row++) {
            for (let col = 0; col < BOARD_SIZE; col++) {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.row = row;
                cell.dataset.col = col;
                board.appendChild(cell);
            }
        }

        // Initialize empty board state
        state.board = Array.from({ length: BOARD_SIZE }, () =>
            Array.from({ length: BOARD_SIZE }, () => null)
        );
    }

    // ========================================================================
    // SOCKET.IO CONNECTION
    // ========================================================================

    function connectSocket() {
        if (!state.roomId) return;

        // Connect to same host the page was served from
        const serverUrl = window.location.protocol + '//' + window.location.host;

        state.socket = io(serverUrl, {
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 10000,
        });

        // Connection events
        state.socket.on('connect', onConnect);
        state.socket.on('disconnect', onDisconnect);
        state.socket.on('reconnect', onReconnect);
        state.socket.on('connect_error', onConnectError);

        // Game events
        state.socket.on('match_info', onMatchInfo);
        state.socket.on('game_start', onGameStart);
        state.socket.on('spectator_move', onSpectatorMove);
        state.socket.on('game_end', onGameEnd);

        // Fallback: also listen to generic move events in case server uses them
        state.socket.on('spectator_update', onSpectatorUpdate);
        state.socket.on('move_made', onMoveMade);
    }

    function onConnect() {
        console.log('[Spectator] Connected to server');
        state.connected = true;
        updateConnectionStatus(true);

        // Join room as spectator
        state.socket.emit('join_spectate', { room_id: state.roomId });
        console.log('[Spectator] Emitted join_spectate for room:', state.roomId);
    }

    function onDisconnect(reason) {
        console.log('[Spectator] Disconnected:', reason);
        state.connected = false;
        updateConnectionStatus(false);
    }

    function onReconnect(attemptNumber) {
        console.log('[Spectator] Reconnected after', attemptNumber, 'attempts');
        state.connected = true;
        updateConnectionStatus(true);

        // Rejoin room
        state.socket.emit('join_spectate', { room_id: state.roomId });
    }

    function onConnectError(error) {
        console.error('[Spectator] Connection error:', error.message);
        updateConnectionStatus(false);
    }

    // ========================================================================
    // EVENT HANDLERS
    // ========================================================================

    function onMatchInfo(data) {
        console.log('[Spectator] Match info received:', data);
        state.matchInfo = data;

        // Update match info bar
        const bar = document.getElementById('match-info-bar');
        if (bar) bar.style.display = 'flex';

        setTextContent('game-id-display', truncateId(data.game_id || data.room_id || '--'));
        setTextContent('wager-display', (data.wager || 0) + ' MON');
        setTextContent('engine1-display', data.agent1 ? data.agent1.engine || '--' : '--');
        setTextContent('engine2-display', data.agent2 ? data.agent2.engine || '--' : '--');

        // Update player addresses
        if (data.agent1 && data.agent1.address) {
            setTextContent('player1-address', truncateAddress(data.agent1.address));
        }
        if (data.agent2 && data.agent2.address) {
            setTextContent('player2-address', truncateAddress(data.agent2.address));
        }

        // Update engine names on player badges
        if (data.agent1 && data.agent1.engine) {
            setTextContent('player1-engine', data.agent1.engine);
        }
        if (data.agent2 && data.agent2.engine) {
            setTextContent('player2-engine', data.agent2.engine);
        }
    }

    function onGameStart(data) {
        console.log('[Spectator] Game started:', data);
        state.matchStarted = true;

        // Show game UI, hide waiting
        showElement('spectator-layout');
        hideElement('waiting-state');
        showLiveBadge();

        // Update board if provided
        if (data.board) {
            renderFullBoard(data.board);
        }

        // Update current player
        if (data.current_player) {
            state.currentPlayer = data.current_player;
            updateTurnIndicator(data.current_player);
        }

        // Update card counts
        if (data.hands) {
            setTextContent('player1-cards', data.hands[1] || data.hands['1'] || '--');
            setTextContent('player2-cards', data.hands[2] || data.hands['2'] || '--');
        }
    }

    function onSpectatorMove(data) {
        console.log('[Spectator] Move received:', data);
        handleMove(data);
    }

    function onSpectatorUpdate(data) {
        // Generic spectator update - handle the same as move if it contains move data
        console.log('[Spectator] Spectator update:', data);
        if (data.row !== undefined && data.col !== undefined) {
            handleMove(data);
        } else if (data.board) {
            renderFullBoard(data.board);
        }
    }

    function onMoveMade(data) {
        // Fallback listener for generic move_made events
        console.log('[Spectator] move_made event:', data);
        if (data.row !== undefined && data.col !== undefined) {
            handleMove(data);
        }
        if (data.board) {
            renderFullBoard(data.board);
        }
    }

    function handleMove(data) {
        // Ensure game UI is visible
        if (!state.matchStarted) {
            state.matchStarted = true;
            showElement('spectator-layout');
            hideElement('waiting-state');
            showLiveBadge();
        }

        const row = data.row;
        const col = data.col;
        const value = data.card_value;
        const player = normalizePlayer(data.player);
        const color = data.card_color || null;

        // Update local board state
        if (row !== undefined && col !== undefined) {
            if (!state.board) {
                state.board = Array.from({ length: BOARD_SIZE }, () =>
                    Array.from({ length: BOARD_SIZE }, () => null)
                );
            }
            state.board[row][col] = { value: value, player: player, color: color };
        }

        // If full board state is provided, use it
        if (data.board) {
            renderFullBoard(data.board);
        }

        // Animate the specific move cell
        if (row !== undefined && col !== undefined) {
            setTimeout(() => {
                animateCell(row, col, value, player, color);
            }, MOVE_ANIMATION_DELAY);
        }

        // Update turn indicator
        if (data.current_player) {
            state.currentPlayer = data.current_player;
            updateTurnIndicator(data.current_player);
        }

        // Update card counts
        if (data.hands) {
            setTextContent('player1-cards', data.hands[1] || data.hands['1'] || '--');
            setTextContent('player2-cards', data.hands[2] || data.hands['2'] || '--');
        }

        // Record move in history
        state.moveHistory.push({
            number: state.moveHistory.length + 1,
            player: player,
            row: row,
            col: col,
            value: value,
            color: color,
        });

        updateMoveHistory();
    }

    function onGameEnd(data) {
        console.log('[Spectator] Game ended:', data);

        // Hide live badge
        const badge = document.getElementById('live-badge');
        if (badge) {
            badge.textContent = 'FINISHED';
            badge.style.background = '#555';
            badge.style.animation = 'none';
        }

        // Determine winner display
        const modal = document.getElementById('result-modal-overlay');
        const titleEl = document.getElementById('result-title');
        const reasonEl = document.getElementById('result-reason');

        if (!modal || !titleEl) return;

        // Set winner text
        const winner = data.winner;
        if (winner === 1 || winner === '1' || winner === 'player1') {
            titleEl.textContent = 'Player 1 Wins';
            titleEl.className = 'result-title p1-wins';
        } else if (winner === 2 || winner === '2' || winner === 'player2') {
            titleEl.textContent = 'Player 2 Wins';
            titleEl.className = 'result-title p2-wins';
        } else if (winner === 'draw' || winner === 0) {
            titleEl.textContent = 'Draw';
            titleEl.className = 'result-title draw';
        } else {
            titleEl.textContent = 'Game Over';
            titleEl.className = 'result-title';
        }

        // Reason
        if (reasonEl && data.reason) {
            reasonEl.textContent = data.reason;
            reasonEl.style.display = 'block';
        }

        // Payout
        if (data.payout) {
            const payoutSection = document.getElementById('result-payout-section');
            const payoutAmount = document.getElementById('result-payout-amount');
            if (payoutSection && payoutAmount) {
                payoutAmount.textContent = data.payout + ' MON';
                payoutSection.style.display = 'block';
            }
        }

        // TX link
        if (data.tx_hash || data.explorer_link) {
            const txContainer = document.getElementById('result-tx-container');
            const txLink = document.getElementById('result-tx-link');
            if (txContainer && txLink) {
                const url = data.explorer_link || ('https://monadexplorer.com/tx/' + data.tx_hash);
                txLink.href = url;
                txLink.textContent = 'View TX: ' + truncateHash(data.tx_hash || url);
                txContainer.style.display = 'block';
            }
        }

        // Show modal
        modal.classList.add('visible');

        // Update turn indicator
        const turnIndicator = document.getElementById('turn-indicator');
        if (turnIndicator) {
            turnIndicator.textContent = 'Match Complete';
            turnIndicator.className = 'turn-indicator-bar';
        }

        // Deactivate player badges
        const p1Badge = document.getElementById('player1-badge');
        const p2Badge = document.getElementById('player2-badge');
        if (p1Badge) p1Badge.classList.remove('active');
        if (p2Badge) p2Badge.classList.remove('active');
    }

    // ========================================================================
    // UI UPDATES
    // ========================================================================

    // Normalize player to '1' or '2' (handles 'player1', 1, '1', etc.)
    function normalizePlayer(p) {
        if (p === 1 || p === '1') return '1';
        if (p === 2 || p === '2') return '2';
        if (typeof p === 'string') {
            if (p.includes('1') || p === 'player1' || p === 'claude') return '1';
            if (p.includes('2') || p === 'player2' || p === 'openai') return '2';
        }
        return String(p);
    }

    function renderFullBoard(boardData) {
        for (let row = 0; row < BOARD_SIZE; row++) {
            for (let col = 0; col < BOARD_SIZE; col++) {
                const cellData = boardData[row][col];
                const cell = getCell(row, col);
                if (!cell) continue;

                if (cellData) {
                    const value = cellData.value || cellData.card || cellData;
                    const player = normalizePlayer(cellData.player || cellData.owner);
                    const color = cellData.color || null;
                    cell.textContent = value;
                    cell.className = 'cell player' + player;
                    if (color) {
                        cell.classList.add('color-' + color);
                    }

                    // Update local state
                    if (state.board) {
                        state.board[row][col] = { value: value, player: player, color: color };
                    }
                } else {
                    cell.textContent = '';
                    cell.className = 'cell';
                    if (state.board) {
                        state.board[row][col] = null;
                    }
                }
            }
        }
    }

    function animateCell(row, col, value, player, color) {
        const cell = getCell(row, col);
        if (!cell) return;

        const p = normalizePlayer(player);
        cell.textContent = value;
        cell.className = 'cell player' + p + ' new-move flash-p' + p;
        if (color) {
            cell.classList.add('color-' + color);
        }

        // Remove animation classes after they complete
        setTimeout(() => {
            cell.classList.remove('new-move', 'flash-p1', 'flash-p2');
        }, 700);
    }

    function updateTurnIndicator(currentPlayer) {
        const indicator = document.getElementById('turn-indicator');
        const p1Badge = document.getElementById('player1-badge');
        const p2Badge = document.getElementById('player2-badge');

        if (!indicator) return;

        // Reset
        indicator.className = 'turn-indicator-bar';
        if (p1Badge) p1Badge.classList.remove('active');
        if (p2Badge) p2Badge.classList.remove('active');

        if (currentPlayer === 1 || currentPlayer === '1') {
            indicator.textContent = 'Player 1 thinking...';
            indicator.classList.add('p1-turn');
            if (p1Badge) p1Badge.classList.add('active');
        } else if (currentPlayer === 2 || currentPlayer === '2') {
            indicator.textContent = 'Player 2 thinking...';
            indicator.classList.add('p2-turn');
            if (p2Badge) p2Badge.classList.add('active');
        }
    }

    function updateMoveHistory() {
        const list = document.getElementById('move-list');
        if (!list) return;

        // Get last N moves
        const recent = state.moveHistory.slice(-MAX_HISTORY_DISPLAY).reverse();

        if (recent.length === 0) {
            list.innerHTML = '<li class="move-list-empty">No moves yet</li>';
            return;
        }

        list.innerHTML = '';
        recent.forEach((move, index) => {
            const li = document.createElement('li');
            if (index === 0) li.classList.add('new-entry');

            const dot = document.createElement('span');
            dot.className = 'move-dot p' + move.player;

            const num = document.createElement('span');
            num.className = 'move-number';
            num.textContent = '#' + move.number;

            const text = document.createElement('span');
            text.className = 'move-text';
            const rowLabel = String.fromCharCode(65 + move.row); // A-F
            const colLabel = move.col + 1; // 1-6
            text.textContent = 'P' + move.player + ' placed ' + move.value + ' at ' + rowLabel + colLabel;

            li.appendChild(dot);
            li.appendChild(num);
            li.appendChild(text);
            list.appendChild(li);
        });
    }

    function updateConnectionStatus(connected) {
        const dot = document.getElementById('connection-dot');
        const text = document.getElementById('connection-text');

        if (dot) {
            dot.className = 'connection-dot ' + (connected ? 'connected' : 'disconnected');
        }
        if (text) {
            text.textContent = connected ? 'Connected' : 'Reconnecting...';
        }
    }

    function showLiveBadge() {
        const badge = document.getElementById('live-badge');
        if (badge) {
            badge.style.display = 'inline-block';
            badge.textContent = 'LIVE';
            badge.style.background = '#ff0000';
            badge.style.animation = '';
        }
    }

    function showWaitingMessage(title, subtitle) {
        const container = document.getElementById('waiting-state');
        if (!container) return;
        container.innerHTML = '<h2 style="margin-bottom:12px;">' + escapeHtml(title) + '</h2>' +
            '<p>' + escapeHtml(subtitle) + '</p>';
    }

    // ========================================================================
    // MODAL
    // ========================================================================

    window.closeResultModal = function () {
        const modal = document.getElementById('result-modal-overlay');
        if (modal) modal.classList.remove('visible');
    };

    // ========================================================================
    // UTILITY
    // ========================================================================

    function truncateAddress(address) {
        if (!address) return '--';
        if (address.length <= 12) return address;
        return address.slice(0, 6) + '...' + address.slice(-4);
    }

    function truncateId(id) {
        if (!id) return '--';
        if (id.length <= 10) return id;
        return id.slice(0, 8) + '...';
    }

    function truncateHash(hash) {
        if (!hash) return '';
        if (hash.length <= 16) return hash;
        return hash.slice(0, 10) + '...' + hash.slice(-6);
    }

    function getCell(row, col) {
        return document.querySelector('#game-board [data-row="' + row + '"][data-col="' + col + '"]');
    }

    function setTextContent(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function showElement(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = '';
    }

    function hideElement(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ========================================================================
    // BOOT
    // ========================================================================

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
