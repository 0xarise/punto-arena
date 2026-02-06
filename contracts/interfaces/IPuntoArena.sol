// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IPuntoArena {
    // ============ Enums ============
    enum GameState {
        PENDING,    // Waiting for player 2
        ACTIVE,     // Both players joined, game in progress
        FINISHED,   // Game completed, winner declared
        CANCELLED   // Timeout or cancelled
    }

    // ============ Structs ============
    struct Game {
        address player1;
        address player2;
        uint256 wager;
        GameState state;
        address winner;
        uint256 createdAt;
    }

    // ============ Events ============
    event GameCreated(uint256 indexed gameId, address indexed player1, uint256 wager);
    event GameJoined(uint256 indexed gameId, address indexed player2);
    event GameFinished(uint256 indexed gameId, address indexed winner, uint256 payout);
    event GameCancelled(uint256 indexed gameId, string reason);
    event WinningsClaimed(uint256 indexed gameId, address indexed winner, uint256 amount);
    event ProtocolFeeUpdated(uint256 oldFee, uint256 newFee);
    event OracleUpdated(address oldOracle, address newOracle);
    event FeesWithdrawn(address indexed to, uint256 amount);

    // ============ Game Functions ============
    function createGame() external payable returns (uint256 gameId);
    function joinGame(uint256 gameId) external payable;
    function submitResult(uint256 gameId, address winner, bytes calldata signature) external;
    function claimWinnings(uint256 gameId) external;
    function claimTimeout(uint256 gameId) external;

    // ============ View Functions ============
    function getGame(uint256 gameId) external view returns (Game memory);
    function getProtocolFee() external view returns (uint256);
    function getMinWager() external view returns (uint256);
    function getTimeout() external view returns (uint256);
    function getAccumulatedFees() external view returns (uint256);

    // ============ Admin Functions ============
    function setProtocolFee(uint256 feeBps) external;
    function setOracle(address oracle) external;
    function setMinWager(uint256 minWager) external;
    function setTimeout(uint256 timeout) external;
    function withdrawFees(address to) external;
}
