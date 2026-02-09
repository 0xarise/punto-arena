require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const monadMainnetRpc = process.env.MONAD_RPC_URL || "https://rpc.monad.xyz";
const monadTestnetRpc = process.env.MONAD_TESTNET_RPC_URL || "https://testnet-rpc.monad.xyz";
const mainnetDeployerKey = process.env.DEPLOYER_PRIVATE_KEY;
const testnetDeployerKey = process.env.TESTNET_DEPLOYER_PRIVATE_KEY || process.env.DEPLOYER_PRIVATE_KEY;

module.exports = {
  solidity: "0.8.20",
  networks: {
    "monad-mainnet": {
      url: monadMainnetRpc,
      chainId: 143,
      accounts: mainnetDeployerKey ? [mainnetDeployerKey] : []
    },
    "monad-testnet": {
      url: monadTestnetRpc,
      chainId: 10143,
      accounts: testnetDeployerKey ? [testnetDeployerKey] : []
    }
  },
  paths: {
    sources: "./contracts",
    artifacts: "./artifacts"
  }
};
