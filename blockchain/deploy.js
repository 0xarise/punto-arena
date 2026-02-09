/**
 * Deploy PuntoArena contract to Monad
 * Usage: node deploy.js
 */

const { ethers } = require('ethers');
const fs = require('fs');
require('dotenv').config();

async function main() {
    console.log('\n🚀 Deploying PuntoArena to Monad...\n');

    // Setup provider and wallet
    const provider = new ethers.JsonRpcProvider(process.env.MONAD_RPC_URL);
    const wallet = new ethers.Wallet(process.env.DEPLOYER_PRIVATE_KEY, provider);

    console.log(`📍 Deployer: ${wallet.address}`);
    console.log(`💰 Balance: ${ethers.formatEther(await provider.getBalance(wallet.address))} MON\n`);

    // Read contract
    const contractSource = fs.readFileSync('../contracts/PuntoArena.sol', 'utf8');

    // Compile (assuming you have compiled JSON)
    const compiledContract = JSON.parse(
        fs.readFileSync('../contracts/PuntoArena.json', 'utf8')
    );

    // Deploy
    const PuntoArena = new ethers.ContractFactory(
        compiledContract.abi,
        compiledContract.bytecode,
        wallet
    );

    const oracleAddress = process.env.ORACLE_ADDRESS || wallet.address;

    console.log(`🔮 Oracle address: ${oracleAddress}`);
    console.log(`📝 Deploying contract...`);

    const contract = await PuntoArena.deploy(oracleAddress);
    await contract.waitForDeployment();

    const contractAddress = await contract.getAddress();

    console.log(`\n✅ Contract deployed!`);
    console.log(`📍 Address: ${contractAddress}`);

    // Save deployment info
    const deployment = {
        network: 'monad-testnet',
        contractAddress: contractAddress,
        oracleAddress: oracleAddress,
        deployer: wallet.address,
        deployedAt: new Date().toISOString(),
        transactionHash: contract.deploymentTransaction().hash
    };

    fs.writeFileSync(
        '../blockchain/deployment.json',
        JSON.stringify(deployment, null, 2)
    );

    // Save ABI
    fs.writeFileSync(
        '../blockchain/PuntoArena_ABI.json',
        JSON.stringify(compiledContract.abi, null, 2)
    );

    console.log(`\n📄 Deployment info saved to deployment.json`);
    console.log(`📄 ABI saved to PuntoArena_ABI.json`);

    console.log(`\n🎉 Deployment complete!\n`);
    console.log(`Add to .env:`);
    console.log(`CONTRACT_ADDRESS=${contractAddress}`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
