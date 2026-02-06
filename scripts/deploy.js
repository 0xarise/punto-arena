const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying PuntoArena with account:", deployer.address);
  console.log("Balance:", hre.ethers.formatEther(await hre.ethers.provider.getBalance(deployer.address)), "MON");

  // Use ORACLE_ADDRESS from env or default to deployer
  const oracleAddress = process.env.ORACLE_ADDRESS || deployer.address;
  console.log("Oracle address:", oracleAddress);

  const PuntoArena = await hre.ethers.getContractFactory("PuntoArena");
  const arena = await PuntoArena.deploy(oracleAddress);
  await arena.waitForDeployment();

  const address = await arena.getAddress();
  console.log("\n✅ PuntoArena deployed to:", address);
  console.log("\nVerify with:");
  console.log(`npx hardhat verify --network monad ${address} ${oracleAddress}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
