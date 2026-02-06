const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("PuntoArena", function () {
  let arena, owner, oracle, player1, player2;
  const WAGER = ethers.parseEther("1");
  const FEE_BPS = 500n; // 5%

  beforeEach(async function () {
    [owner, oracle, player1, player2] = await ethers.getSigners();
    const PuntoArena = await ethers.getContractFactory("PuntoArena");
    arena = await PuntoArena.deploy(oracle.address);
    await arena.waitForDeployment();
  });

  // ============ Helper Functions ============
  async function signResult(gameId, winner, signer) {
    const chainId = (await ethers.provider.getNetwork()).chainId;
    const messageHash = ethers.solidityPackedKeccak256(
      ["uint256", "address", "uint256"],
      [gameId, winner, chainId]
    );
    return signer.signMessage(ethers.getBytes(messageHash));
  }

  // ============ Game Creation ============
  describe("createGame", function () {
    it("creates a game with correct wager", async function () {
      const tx = await arena.connect(player1).createGame({ value: WAGER });
      await expect(tx)
        .to.emit(arena, "GameCreated")
        .withArgs(1, player1.address, WAGER);

      const game = await arena.getGame(1);
      expect(game.player1).to.equal(player1.address);
      expect(game.wager).to.equal(WAGER);
      expect(game.state).to.equal(0); // PENDING
    });

    it("rejects wager below minimum", async function () {
      await expect(
        arena.connect(player1).createGame({ value: ethers.parseEther("0.001") })
      ).to.be.revertedWith("Wager below minimum");
    });
  });

  // ============ Game Joining ============
  describe("joinGame", function () {
    beforeEach(async function () {
      await arena.connect(player1).createGame({ value: WAGER });
    });

    it("allows player2 to join with matching wager", async function () {
      const tx = await arena.connect(player2).joinGame(1, { value: WAGER });
      await expect(tx).to.emit(arena, "GameJoined").withArgs(1, player2.address);

      const game = await arena.getGame(1);
      expect(game.player2).to.equal(player2.address);
      expect(game.state).to.equal(1); // ACTIVE
    });

    it("rejects player1 joining own game", async function () {
      await expect(
        arena.connect(player1).joinGame(1, { value: WAGER })
      ).to.be.revertedWith("Cannot join own game");
    });

    it("rejects mismatched wager", async function () {
      await expect(
        arena.connect(player2).joinGame(1, { value: ethers.parseEther("0.5") })
      ).to.be.revertedWith("Wager mismatch");
    });
  });

  // ============ Result Submission ============
  describe("submitResult", function () {
    beforeEach(async function () {
      await arena.connect(player1).createGame({ value: WAGER });
      await arena.connect(player2).joinGame(1, { value: WAGER });
    });

    it("accepts valid oracle signature", async function () {
      const signature = await signResult(1, player1.address, oracle);
      const tx = await arena.submitResult(1, player1.address, signature);

      await expect(tx).to.emit(arena, "GameFinished");
      const game = await arena.getGame(1);
      expect(game.winner).to.equal(player1.address);
      expect(game.state).to.equal(2); // FINISHED
    });

    it("rejects invalid signature", async function () {
      const signature = await signResult(1, player1.address, player2); // wrong signer
      await expect(
        arena.submitResult(1, player1.address, signature)
      ).to.be.revertedWith("Invalid signature");
    });

    it("rejects invalid winner", async function () {
      const signature = await signResult(1, owner.address, oracle);
      await expect(
        arena.submitResult(1, owner.address, signature)
      ).to.be.revertedWith("Invalid winner");
    });
  });

  // ============ Claiming Winnings ============
  describe("claimWinnings", function () {
    beforeEach(async function () {
      await arena.connect(player1).createGame({ value: WAGER });
      await arena.connect(player2).joinGame(1, { value: WAGER });
      const signature = await signResult(1, player1.address, oracle);
      await arena.submitResult(1, player1.address, signature);
    });

    it("pays winner minus protocol fee", async function () {
      const balanceBefore = await ethers.provider.getBalance(player1.address);
      const tx = await arena.connect(player1).claimWinnings(1);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;

      const balanceAfter = await ethers.provider.getBalance(player1.address);
      const totalPot = WAGER * 2n;
      const fee = (totalPot * FEE_BPS) / 10000n;
      const expectedPayout = totalPot - fee;

      expect(balanceAfter - balanceBefore + gasCost).to.equal(expectedPayout);
    });

    it("accumulates protocol fees", async function () {
      await arena.connect(player1).claimWinnings(1);
      const totalPot = WAGER * 2n;
      const expectedFee = (totalPot * FEE_BPS) / 10000n;
      expect(await arena.accumulatedFees()).to.equal(expectedFee);
    });

    it("prevents double claiming", async function () {
      await arena.connect(player1).claimWinnings(1);
      await expect(
        arena.connect(player1).claimWinnings(1)
      ).to.be.revertedWith("Already claimed");
    });
  });

  // ============ Timeout Refund ============
  describe("claimTimeout", function () {
    beforeEach(async function () {
      await arena.setTimeout(60); // 60 seconds for testing
      await arena.connect(player1).createGame({ value: WAGER });
    });

    it("refunds after timeout (pending game)", async function () {
      await ethers.provider.send("evm_increaseTime", [61]);
      await ethers.provider.send("evm_mine");

      const balanceBefore = await ethers.provider.getBalance(player1.address);
      const tx = await arena.connect(player1).claimTimeout(1);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;

      const balanceAfter = await ethers.provider.getBalance(player1.address);
      expect(balanceAfter - balanceBefore + gasCost).to.equal(WAGER);
    });

    it("rejects timeout before time", async function () {
      await expect(
        arena.connect(player1).claimTimeout(1)
      ).to.be.revertedWith("Timeout not reached");
    });
  });

  // ============ Admin Functions ============
  describe("admin", function () {
    it("owner can update fee", async function () {
      await arena.setProtocolFee(300);
      expect(await arena.protocolFeeBps()).to.equal(300);
    });

    it("rejects fee above max", async function () {
      await expect(arena.setProtocolFee(1500)).to.be.revertedWith("Fee too high");
    });

    it("owner can withdraw fees", async function () {
      // Setup: complete a game
      await arena.connect(player1).createGame({ value: WAGER });
      await arena.connect(player2).joinGame(1, { value: WAGER });
      const signature = await signResult(1, player1.address, oracle);
      await arena.submitResult(1, player1.address, signature);
      await arena.connect(player1).claimWinnings(1);

      const fees = await arena.accumulatedFees();
      const balanceBefore = await ethers.provider.getBalance(owner.address);

      const tx = await arena.withdrawFees(owner.address);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;

      const balanceAfter = await ethers.provider.getBalance(owner.address);
      expect(balanceAfter - balanceBefore + gasCost).to.equal(fees);
    });
  });
});
