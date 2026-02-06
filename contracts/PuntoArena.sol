// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/IPuntoArena.sol";

/**
 * @title PuntoArena
 * @notice On-chain wagering for Punto card game
 * @dev Escrow-based betting with oracle result verification
 */
contract PuntoArena is IPuntoArena, Ownable, ReentrancyGuard {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // ============ State Variables ============
    uint256 public gameCounter;
    uint256 public protocolFeeBps = 500; // 5% = 500 bps
    uint256 public minWager = 0.01 ether;
    uint256 public timeout = 24 hours;
    uint256 public accumulatedFees;
    address public oracle;

    mapping(uint256 => Game) public games;
    mapping(uint256 => bool) public winningsClaimed;

    // ============ Constants ============
    uint256 public constant MAX_FEE_BPS = 1000; // 10% max

    // ============ Constructor ============
    constructor(address _oracle) Ownable(msg.sender) {
        require(_oracle != address(0), "Invalid oracle");
        oracle = _oracle;
    }

    // ============ Game Functions ============
    function createGame() external payable returns (uint256 gameId) {
        require(msg.value >= minWager, "Wager below minimum");

        gameId = ++gameCounter;
        games[gameId] = Game({
            player1: msg.sender,
            player2: address(0),
            wager: msg.value,
            state: GameState.PENDING,
            winner: address(0),
            createdAt: block.timestamp
        });

        emit GameCreated(gameId, msg.sender, msg.value);
    }

    function joinGame(uint256 gameId) external payable {
        Game storage game = games[gameId];
        require(game.state == GameState.PENDING, "Game not pending");
        require(msg.sender != game.player1, "Cannot join own game");
        require(msg.value == game.wager, "Wager mismatch");

        game.player2 = msg.sender;
        game.state = GameState.ACTIVE;

        emit GameJoined(gameId, msg.sender);
    }

    function submitResult(
        uint256 gameId,
        address winner,
        bytes calldata signature
    ) external {
        Game storage game = games[gameId];
        require(game.state == GameState.ACTIVE, "Game not active");
        require(
            winner == game.player1 || winner == game.player2,
            "Invalid winner"
        );

        // Verify oracle signature
        bytes32 messageHash = keccak256(
            abi.encodePacked(gameId, winner, block.chainid)
        );
        bytes32 ethSignedHash = messageHash.toEthSignedMessageHash();
        address signer = ethSignedHash.recover(signature);
        require(signer == oracle, "Invalid signature");

        game.winner = winner;
        game.state = GameState.FINISHED;

        // Calculate payout
        uint256 totalPot = game.wager * 2;
        uint256 fee = (totalPot * protocolFeeBps) / 10000;
        uint256 payout = totalPot - fee;
        accumulatedFees += fee;

        emit GameFinished(gameId, winner, payout);
    }

    function claimWinnings(uint256 gameId) external nonReentrant {
        Game storage game = games[gameId];
        require(game.state == GameState.FINISHED, "Game not finished");
        require(msg.sender == game.winner, "Not winner");
        require(!winningsClaimed[gameId], "Already claimed");

        winningsClaimed[gameId] = true;

        uint256 totalPot = game.wager * 2;
        uint256 fee = (totalPot * protocolFeeBps) / 10000;
        uint256 payout = totalPot - fee;

        (bool success, ) = msg.sender.call{value: payout}("");
        require(success, "Transfer failed");

        emit WinningsClaimed(gameId, msg.sender, payout);
    }

    function claimTimeout(uint256 gameId) external nonReentrant {
        Game storage game = games[gameId];
        require(
            game.state == GameState.PENDING || game.state == GameState.ACTIVE,
            "Game ended"
        );
        require(
            block.timestamp >= game.createdAt + timeout,
            "Timeout not reached"
        );
        require(
            msg.sender == game.player1 || msg.sender == game.player2,
            "Not player"
        );

        game.state = GameState.CANCELLED;

        // Refund both players
        uint256 refund = game.wager;
        if (game.player1 != address(0)) {
            (bool s1, ) = game.player1.call{value: refund}("");
            require(s1, "Refund p1 failed");
        }
        if (game.player2 != address(0)) {
            (bool s2, ) = game.player2.call{value: refund}("");
            require(s2, "Refund p2 failed");
        }

        emit GameCancelled(gameId, "timeout");
    }

    // ============ View Functions ============
    function getGame(uint256 gameId) external view returns (Game memory) {
        return games[gameId];
    }

    function getProtocolFee() external view returns (uint256) {
        return protocolFeeBps;
    }

    function getMinWager() external view returns (uint256) {
        return minWager;
    }

    function getTimeout() external view returns (uint256) {
        return timeout;
    }

    function getAccumulatedFees() external view returns (uint256) {
        return accumulatedFees;
    }

    // ============ Admin Functions ============
    function setProtocolFee(uint256 feeBps) external onlyOwner {
        require(feeBps <= MAX_FEE_BPS, "Fee too high");
        emit ProtocolFeeUpdated(protocolFeeBps, feeBps);
        protocolFeeBps = feeBps;
    }

    function setOracle(address _oracle) external onlyOwner {
        require(_oracle != address(0), "Invalid oracle");
        emit OracleUpdated(oracle, _oracle);
        oracle = _oracle;
    }

    function setMinWager(uint256 _minWager) external onlyOwner {
        minWager = _minWager;
    }

    function setTimeout(uint256 _timeout) external onlyOwner {
        timeout = _timeout;
    }

    function withdrawFees(address to) external onlyOwner nonReentrant {
        require(to != address(0), "Invalid address");
        uint256 amount = accumulatedFees;
        accumulatedFees = 0;

        (bool success, ) = to.call{value: amount}("");
        require(success, "Withdraw failed");

        emit FeesWithdrawn(to, amount);
    }
}
