import "@nomicfoundation/hardhat-toolbox";

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    compilers: [
      {
        version: "0.8.20",
        settings: {
          optimizer: {
            enabled: true,
            runs: 1,
          },
          viaIR: true,
        },
      },
      {
        version: "0.7.6",
        settings: {
          optimizer: {
            enabled: true,
            runs: 800,
          },
        },
      },
    ],
  },
  networks: {
    hardhat: {
      hardfork: "shanghai",
      chainId: 31337,
      chains: {
        167012: {
          hardforkHistory: {
            shanghai: 0,
          },
        },
      },
      forking: {
        url: "https://rpc.kasplextest.xyz",
        enabled: true,
      },
    },
    kasplex_testnet: {
      url: "https://rpc.kasplextest.xyz",
      chainId: 167012,
      accounts: process.env.ORACLE_PRIVATE_KEY ? [process.env.ORACLE_PRIVATE_KEY] : [],
      gasPrice: "auto",
    },
    kasplex_mainnet: {
      url: process.env.MAINNET_RPC_URL || "https://evmrpc.kasplex.org",
      chainId: parseInt(process.env.MAINNET_CHAIN_ID) || 202555,
      accounts: process.env.MAINNET_PRIVATE_KEY ? [process.env.MAINNET_PRIVATE_KEY] : [],
      gasPrice: "auto",
    },
  },
  etherscan: {
    apiKey: {
      kasplex_testnet: "no-api-key-needed",
      kasplex_mainnet: "no-api-key-needed",
    },
    customChains: [
      {
        network: "kasplex_testnet",
        chainId: 167012,
        urls: {
          apiURL: "http://explorer.testnet.kasplextest.xyz/api",
          browserURL: "http://explorer.testnet.kasplextest.xyz"
        }
      },
      {
        network: "kasplex_mainnet",
        chainId: 202555,
        urls: {
          apiURL: "https://explorer.kasplex.org/api",
          browserURL: "https://explorer.kasplex.org"
        }
      }
    ]
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  }
};
