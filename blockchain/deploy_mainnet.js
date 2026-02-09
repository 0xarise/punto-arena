/**
 * Deploy PuntoArena contract to Monad MAINNET
 */

const { ethers } = require('ethers');
const fs = require('fs');
require('dotenv').config();

async function main() {
    console.log('\n🚀 Deploying PuntoArena to Monad MAINNET...\n');

    // Monad Mainnet
    const rpcUrl = process.env.MONAD_RPC_URL || 'https://rpc.monad.xyz';
    const privateKey = process.env.DEPLOYER_PRIVATE_KEY;

    if (!privateKey) {
        throw new Error('Missing DEPLOYER_PRIVATE_KEY in environment');
    }

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);

    console.log(`📍 Deployer: ${wallet.address}`);
    
    const balance = await provider.getBalance(wallet.address);
    console.log(`💰 Balance: ${ethers.formatEther(balance)} MON\n`);

    if (balance < ethers.parseEther("1")) {
        console.log("⚠️  Low balance warning!");
    }

    // Load compiled contract
    const compiled = JSON.parse(
        fs.readFileSync('contracts/PuntoArena.json', 'utf8')
    );

    // Deploy
    const PuntoArena = new ethers.ContractFactory(
        compiled.abi,
        compiled.bytecode,
        wallet
    );

    // Oracle = same as deployer for now
    const oracleAddress = wallet.address;

    console.log(`🔮 Oracle: ${oracleAddress}`);
    console.log(`📝 Deploying contract...\n`);

    const contract = await PuntoArena.deploy(oracleAddress);
    console.log(`⏳ Waiting for deployment...`);
    
    await contract.waitForDeployment();
    const contractAddress = await contract.getAddress();

    console.log(`\n✅ Contract deployed!`);
    console.log(`📍 Address: ${contractAddress}`);
    console.log(`🔗 Explorer: https://monadexplorer.com/address/${contractAddress}`);

    // Save deployment info
    const deployment = {
        network: 'monad-mainnet',
        chainId: 143,
        contractAddress: contractAddress,
        oracleAddress: oracleAddress,
        deployer: wallet.address,
        deployedAt: new Date().toISOString(),
        txHash: contract.deploymentTransaction().hash
    };

    fs.writeFileSync('blockchain/deployment_mainnet.json', JSON.stringify(deployment, null, 2));
    console.log(`\n📄 Saved to deployment_mainnet.json`);
    
    console.log(`\n🎉 DEPLOYMENT COMPLETE!\n`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error('❌ Deploy failed:', error);
        process.exit(1);
    });
