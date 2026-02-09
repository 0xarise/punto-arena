// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PuntoArena
 * @notice On-chain wagering for Punto game
 * @dev Single oracle for beta, upgradeable to multi-sig
 * @custom:version 2.0.0 - Added player refund mechanism
 */
contract PuntoArena {
    // ============================================================================
    // STATE VARIABLES
    // ============================================================================

    address public oracle;      // Server that signs game results
    address public owner;       // Contract owner (for admin)
    uint256 public protocolFeeBps = 500;  // 5% fee (in basis points)
    uint256 public gameCounter;
    uint256 public minimumWager = 0.001 ether;  // Prevent spam
    
    // Refund timeout: players can claim refund after this delay
    uint256 public constant REFUND_DELAY = 30 minutes;

    enum GameState { PENDING, ACTIVE, FINISHED, CANCELLED }

    struct Game {
        address player1;
        address player2;
        uint256 wager;
        GameState state;
        address winner;
        uint256 createdAt;
        string roomId;  // Link to off-chain game room
    }

    mapping(uint256 => Game) public games;
    mapping(string => uint256) public roomIdToGameId;  // Lookup by room ID

    // ============================================================================
    // EVENTS
    // ============================================================================

    event GameCreated(
        uint256 indexed gameId,
        address indexed player1,
        uint256 wager,
        string roomId
    );

    event GameJoined(
        uint256 indexed gameId,
        address indexed player2
    );

    event GameFinished(
        uint256 indexed gameId,
        address indexed winner,
        uint256 payout,
        uint256 fee
    );

    event GameCancelled(uint256 indexed gameId, string reason);
    
    event GameRefunded(
        uint256 indexed gameId,
        address indexed player1,
        address indexed player2,
        uint256 refundAmount
    );

    event OracleUpdated(address oldOracle, address newOracle);
    event ProtocolFeeUpdated(uint256 oldFee, uint256 newFee);

    // ============================================================================
    // MODIFIERS
    // ============================================================================

    modifier onlyOracle() {
        require(msg.sender == oracle, "Only oracle");
        _;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    // ============================================================================
    // CONSTRUCTOR
    // ============================================================================

    constructor(address _oracle) {
        require(_oracle != address(0), "Invalid oracle");
        oracle = _oracle;
        owner = msg.sender;
    }

    // ============================================================================
    // CORE FUNCTIONS
    // ============================================================================

    /**
     * @notice Create a new wagered game
     * @param roomId Off-chain game room identifier
     * @return gameId On-chain game ID
     */
    function createGame(string calldata roomId)
        external
        payable
        returns (uint256)
    {
        require(msg.value >= minimumWager, "Wager too low");
        require(bytes(roomId).length > 0, "Room ID required");
        require(roomIdToGameId[roomId] == 0, "Room already exists");

        uint256 gameId = ++gameCounter;

        games[gameId] = Game({
            player1: msg.sender,
            player2: address(0),
            wager: msg.value,
            state: GameState.PENDING,
            winner: address(0),
            createdAt: block.timestamp,
            roomId: roomId
        });

        roomIdToGameId[roomId] = gameId;

        emit GameCreated(gameId, msg.sender, msg.value, roomId);
        return gameId;
    }

    /**
     * @notice Join an existing game
     * @param gameId Game to join
     */
    function joinGame(uint256 gameId) external payable {
        Game storage game = games[gameId];

        require(game.state == GameState.PENDING, "Game not joinable");
        require(msg.value == game.wager, "Wrong wager amount");
        require(msg.sender != game.player1, "Cannot play yourself");

        game.player2 = msg.sender;
        game.state = GameState.ACTIVE;

        emit GameJoined(gameId, msg.sender);
    }

    /**
     * @notice Submit game result (called by oracle)
     * @param gameId Game ID
     * @param winner Winner address
     */
    function submitResult(uint256 gameId, address winner)
        external
        onlyOracle
    {
        Game storage game = games[gameId];

        require(game.state == GameState.ACTIVE, "Game not active");
        require(
            winner == game.player1 || winner == game.player2,
            "Invalid winner"
        );

        game.winner = winner;
        game.state = GameState.FINISHED;

        // Calculate payout
        uint256 totalPot = game.wager * 2;
        uint256 fee = (totalPot * protocolFeeBps) / 10000;
        uint256 payout = totalPot - fee;

        // Transfer funds
        (bool successWinner, ) = payable(winner).call{value: payout}("");
        require(successWinner, "Payout failed");

        (bool successFee, ) = payable(owner).call{value: fee}("");
        require(successFee, "Fee transfer failed");

        emit GameFinished(gameId, winner, payout, fee);
    }

    /**
     * @notice Claim refund after timeout (callable by players, no owner required)
     * @param gameId Game to refund
     * @dev Players can call this after REFUND_DELAY if game is stuck
     */
    function claimRefund(uint256 gameId) external {
        Game storage game = games[gameId];
        
        // Only players can claim refund
        require(
            msg.sender == game.player1 || msg.sender == game.player2,
            "Not a player in this game"
        );
        
        // Must wait for timeout
        require(
            block.timestamp > game.createdAt + REFUND_DELAY,
            "Refund not available yet"
        );
        
        // Game must be in refundable state
        require(
            game.state == GameState.PENDING || game.state == GameState.ACTIVE,
            "Game not refundable"
        );

        game.state = GameState.CANCELLED;
        
        uint256 refundAmount = game.wager;
        address p1 = game.player1;
        address p2 = game.player2;

        // Refund both players if player2 joined
        if (p2 != address(0)) {
            (bool success1, ) = payable(p1).call{value: refundAmount}("");
            (bool success2, ) = payable(p2).call{value: refundAmount}("");
            require(success1 && success2, "Refund failed");
        } else {
            // Only player1 deposited
            (bool success, ) = payable(p1).call{value: refundAmount}("");
            require(success, "Refund failed");
        }

        emit GameRefunded(gameId, p1, p2, refundAmount);
        emit GameCancelled(gameId, "Player claimed refund");
    }

    /**
     * @notice Emergency refund by owner (legacy, kept for compatibility)
     * @param gameId Game to refund
     */
    function emergencyRefund(uint256 gameId) external onlyOwner {
        Game storage game = games[gameId];

        require(
            game.state == GameState.PENDING ||
            game.state == GameState.ACTIVE,
            "Cannot refund finished game"
        );

        game.state = GameState.CANCELLED;

        // Refund both players
        if (game.player2 != address(0)) {
            (bool success1, ) = payable(game.player1).call{value: game.wager}("");
            (bool success2, ) = payable(game.player2).call{value: game.wager}("");
            require(success1 && success2, "Refund failed");
        } else {
            (bool success, ) = payable(game.player1).call{value: game.wager}("");
            require(success, "Refund failed");
        }

        emit GameCancelled(gameId, "Emergency refund by owner");
    }

    // ============================================================================
    // ADMIN FUNCTIONS
    // ============================================================================

    function setOracle(address newOracle) external onlyOwner {
        require(newOracle != address(0), "Invalid oracle");
        address oldOracle = oracle;
        oracle = newOracle;
        emit OracleUpdated(oldOracle, newOracle);
    }

    function setProtocolFee(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= 1000, "Fee too high (max 10%)");
        uint256 oldFee = protocolFeeBps;
        protocolFeeBps = newFeeBps;
        emit ProtocolFeeUpdated(oldFee, newFeeBps);
    }

    function setMinimumWager(uint256 newMinimum) external onlyOwner {
        minimumWager = newMinimum;
    }

    // ============================================================================
    // VIEW FUNCTIONS
    // ============================================================================

    function getGame(uint256 gameId)
        external
        view
        returns (Game memory)
    {
        return games[gameId];
    }

    function getGameByRoomId(string calldata roomId)
        external
        view
        returns (Game memory)
    {
        uint256 gameId = roomIdToGameId[roomId];
        require(gameId != 0, "Room not found");
        return games[gameId];
    }
    
    /**
     * @notice Get game ID by room ID (for backend event listening)
     * @param roomId Off-chain room identifier
     * @return gameId On-chain game ID (0 if not found)
     */
    function getGameIdByRoomId(string calldata roomId)
        external
        view
        returns (uint256)
    {
        return roomIdToGameId[roomId];
    }

    function calculatePayout(uint256 wager)
        external
        view
        returns (uint256 payout, uint256 fee)
    {
        uint256 totalPot = wager * 2;
        fee = (totalPot * protocolFeeBps) / 10000;
        payout = totalPot - fee;
    }
    
    /**
     * @notice Check if refund is available for a game
     * @param gameId Game to check
     * @return canRefund Whether refund can be claimed
     * @return timeUntilRefund Seconds until refund available (0 if available)
     */
    function canClaimRefund(uint256 gameId)
        external
        view
        returns (bool canRefund, uint256 timeUntilRefund)
    {
        Game storage game = games[gameId];
        
        if (game.state != GameState.PENDING && game.state != GameState.ACTIVE) {
            return (false, 0);
        }
        
        uint256 refundTime = game.createdAt + REFUND_DELAY;
        if (block.timestamp >= refundTime) {
            return (true, 0);
        } else {
            return (false, refundTime - block.timestamp);
        }
    }
}
