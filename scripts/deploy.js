const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  
  console.log("Deploying contracts with account:", deployer.address);
  console.log("Account balance:", (await deployer.provider.getBalance(deployer.address)).toString());

  // Oracle = deployer for now (BERU HOT)
  const oracleAddress = deployer.address;
  
  const PuntoArena = await hre.ethers.getContractFactory("PuntoArena");
  const contract = await PuntoArena.deploy(oracleAddress);

  await contract.waitForDeployment();
  
  const contractAddress = await contract.getAddress();
  console.log("PuntoArena deployed to:", contractAddress);
  console.log("Oracle address:", oracleAddress);
  
  // Verify deployment
  const owner = await contract.owner();
  const oracle = await contract.oracle();
  console.log("Contract owner:", owner);
  console.log("Contract oracle:", oracle);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
