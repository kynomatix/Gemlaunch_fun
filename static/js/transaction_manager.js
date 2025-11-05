/**
 * TransactionManager - Orchestrates wallet-driven blockchain transactions
 * Dependencies: WalletManager (wallet_manager.js), ModalManager (utils/modal.js)
 * 
 * This class implements the 5-phase transaction lifecycle:
 * Phase 1: Get Quote - Retrieve pricing and fee estimates
 * Phase 2: Build Transaction - Construct unsigned transaction data
 * Phase 3: Sign & Submit - Wallet-specific signing (MetaMask vs Kaspa wallets)
 * Phase 4: Relay Transaction - Submit to blockchain (for non-MetaMask wallets)
 * Phase 5: Monitor Transaction - Real-time status updates via SSE
 * 
 * Critical Fixes Implemented:
 * - H-5: AbortController signal propagation for request cancellation
 * - H-2: SSE cleanup on page unload (beforeunload, pagehide, popstate listeners)
 * - Network validation with chain switching support
 * - Wallet-specific transaction branching (MetaMask auto-submits, others need relay)
 */
class TransactionManager {
    constructor(walletManager) {
        this.walletManager = walletManager;
        this.activeTransactions = new Map(); // Track pending txs for cleanup
        
        // ⚠️ H-2 FIX: Cleanup SSE connections on page unload
        window.addEventListener('beforeunload', () => {
            this.closeAllConnections();
        });
        
        // H-2 FIX: Also cleanup on pagehide (mobile Safari compatibility)
        window.addEventListener('pagehide', () => {
            this.closeAllConnections();
        });
        
        // Cleanup on navigation (for SPAs)
        window.addEventListener('popstate', () => {
            this.closeAllConnections();
        });
    }
    
    // ===== PHASE 1: GET QUOTE =====
    /**
     * Get price quote for buy/sell transactions
     * ⚠️ H-5 FIX: Add signal parameter for AbortController support
     * ✨ Graduated Token Support: Routes to DEX endpoints for graduated tokens
     * 
     * @param {string} quoteType - 'buy' | 'sell'
     * @param {Object} params - {token_address, kas_amount, is_graduated} for buy | {token_address, token_amount, is_graduated} for sell
     * @param {AbortSignal} signal - Optional AbortController signal for canceling requests
     * @returns {Promise<Object>} Quote data with tokens_out, fees, slippage, price_impact
     */
    async getQuote(quoteType, params, signal = null) {
        // Check if token is graduated
        const isGraduated = params.is_graduated || false;
        
        let endpoint;
        if (isGraduated) {
            // Use DEX quote endpoint for graduated tokens
            endpoint = '/api/dex/quote';
            // Add side parameter for DEX endpoint (backend expects 'side', not 'trade_type')
            params.side = quoteType;
            
            // Map bonding curve params to DEX params
            // Detect forward vs reverse calculation based on which parameter is provided
            if (quoteType === 'buy') {
                if (params.kas_amount) {
                    // Forward: Have KAS, want tokens → amount_in
                    params.amount_in = params.kas_amount;
                    delete params.kas_amount;
                } else if (params.token_amount) {
                    // Reverse: Want tokens, need KAS → amount_out
                    params.amount_out = params.token_amount;
                    delete params.token_amount;
                }
            } else if (quoteType === 'sell') {
                if (params.token_amount) {
                    // Forward: Have tokens, want KAS → amount_in
                    params.amount_in = params.token_amount;
                    delete params.token_amount;
                } else if (params.kas_amount) {
                    // Reverse: Want KAS, need tokens → amount_out
                    params.amount_out = params.kas_amount;
                    delete params.kas_amount;
                }
            }
        } else {
            // Use bonding curve endpoints for active tokens
            endpoint = quoteType === 'buy' 
                ? '/api/trade/quote-buy' 
                : '/api/trade/quote-sell';
        }
        
        const fetchOptions = {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(params)
        };
        
        // ⚠️ H-5 FIX: Add signal if provided for request cancellation
        if (signal) {
            fetchOptions.signal = signal;
        }
        
        const response = await fetch(endpoint, fetchOptions);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.message || 'Request failed');
        }
        
        return await response.json();
    }
    
    // ===== PHASE 2: BUILD UNSIGNED TX =====
    /**
     * Build unsigned transaction data from backend
     * ✨ Graduated Token Support: Routes to DEX endpoints for graduated tokens
     * 
     * @param {string} txType - 'create_token' | 'buy' | 'sell' | 'claim_fees'
     * @param {Object} params - Transaction-specific parameters (includes is_graduated for buy/sell)
     * @returns {Promise<Object>} {success, tx_data: {to, value, data, gas}, estimated_gas}
     */
    async buildTransaction(txType, params) {
        // Build endpoint URL - handle claim_fees dynamically
        let endpoint;
        if (txType === 'claim_fees') {
            if (!params.token_address) {
                throw new Error('token_address is required for claim_fees transaction');
            }
            endpoint = `/api/token/${params.token_address}/claim-creator-fees`;
        } else if ((txType === 'buy' || txType === 'sell') && params.is_graduated) {
            // Use DEX endpoints for graduated tokens
            endpoint = txType === 'buy' ? '/api/dex/buy' : '/api/dex/sell';
        } else {
            // Use bonding curve endpoints for active tokens or token creation
            const endpoints = {
                'create_token': '/api/token/create',
                'buy': '/api/trade/buy',
                'sell': '/api/trade/sell'
            };
            endpoint = endpoints[txType];
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(params)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.message || 'Request failed');
        }
        
        return await response.json();
    }
    
    /**
     * Extract deployed contract address from transaction receipt
     * Calls backend to verify and extract from blockchain
     * 
     * @param {string} txHash - Transaction hash from wallet signing
     * @param {number} tokenId - Token ID from database
     * @returns {Promise<Object>} {success, contractAddress, token} or {success: false, error}
     */
    async extractContractAddressFromReceipt(txHash, tokenId) {
        try {
            const response = await fetch(`/api/token/${tokenId}/confirm-deployment`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tx_hash: txHash
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to extract contract address');
            }

            if (!data.success) {
                throw new Error(data.error || 'Contract address extraction failed');
            }

            return {
                success: true,
                contractAddress: data.contract_address,
                token: data.token
            };

        } catch (error) {
            console.error('Contract extraction error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    /**
     * Simple ERC20 token transfer (for poll voting, etc.)
     * Builds and submits a transfer transaction directly via MetaMask
     * 
     * @param {string} tokenAddress - ERC20 token contract address
     * @param {string} toAddress - Recipient address
     * @param {string} amount - Amount in wei (as string)
     * @param {string} description - Optional description for logging
     * @returns {Promise<string>} Transaction hash
     */
    async transfer(tokenAddress, toAddress, amount, description = 'Token transfer') {
        if (!this.walletManager.isConnected()) {
            throw new Error('Wallet not connected. Please connect your wallet first.');
        }
        
        const wallet = this.walletManager.getConnectedWallet();
        if (wallet.wallet_type !== 'metamask') {
            throw new Error('Token transfers currently only supported with MetaMask');
        }
        
        // Build ERC20 transfer calldata
        // Function signature: transfer(address,uint256)
        // Function selector: 0xa9059cbb
        const methodId = '0xa9059cbb';
        
        // Pad address to 32 bytes (remove 0x prefix, pad left with zeros)
        const addressParam = toAddress.slice(2).padStart(64, '0');
        
        // Convert amount to hex and pad to 32 bytes
        const amountBigInt = BigInt(amount);
        const amountHex = amountBigInt.toString(16).padStart(64, '0');
        
        const data = methodId + addressParam + amountHex;
        
        // Build transaction
        const txData = {
            to: tokenAddress,
            value: '0x0',
            data: data
        };
        
        console.log(`🔄 Submitting ${description}:`, {
            token: tokenAddress,
            to: toAddress,
            amount: amount
        });
        
        // Sign and submit via MetaMask
        const result = await this._signWithMetaMask(txData);
        
        if (!result.tx_hash) {
            throw new Error('Transaction failed - no hash returned');
        }
        
        console.log(`✅ ${description} submitted:`, result.tx_hash);
        return result.tx_hash;
    }
    
    // ===== PHASE 3: SIGN & SUBMIT WITH WALLET =====
    /**
     * Sign and submit transaction using wallet-specific method
     * 
     * @param {Object} txData - {to, value, data, gas} from backend
     * @returns {Promise<Object>} {tx_hash, needs_relay} for MetaMask | {signed_tx, needs_relay: true} for others
     */
    async signAndSubmitTransaction(txData) {
        if (!this.walletManager.isConnected()) {
            throw new Error('Wallet not connected. Please connect your wallet first.');
        }
        
        const wallet = this.walletManager.getConnectedWallet();
        const walletType = wallet.wallet_type; // 'metamask' | 'kastle' | 'kasware'
        
        // Use wallet-specific method
        switch(walletType) {
            case 'metamask':
                return await this._signWithMetaMask(txData);
            case 'kastle':
            case 'kasware':
                return await this._signWithKaspa(txData, walletType);
            default:
                throw new Error(`Unsupported wallet type: ${walletType}`);
        }
    }
    
    /**
     * Sign and submit transaction with MetaMask
     * MetaMask signs AND broadcasts in one step - no relay needed
     * 
     * Following Uniswap V3 pattern: send ONLY required params, let MetaMask handle gas/chainId/nonce
     * 
     * @private
     * @param {Object} txData - {to, value, data, gas}
     * @returns {Promise<Object>} {tx_hash, needs_relay: false}
     */
    async _signWithMetaMask(txData) {
        const provider = this.walletManager.getMetaMaskProvider();
        const accounts = await provider.request({method: 'eth_accounts'});
        
        // Build transaction params
        const txParams = {
            from: accounts[0],
            to: txData.to,
            value: txData.value || '0x0',
            data: txData.data
        };
        
        // Include gas limit if backend provides it (for DEX swaps)
        if (txData.gas) {
            txParams.gas = txData.gas;
            console.log('✅ DEX TX: Using backend gas limit:', parseInt(txData.gas, 16), 'units');
        }
        
        // Include transaction type if backend specifies it
        if (txData.type) {
            txParams.type = txData.type;
            console.log('✅ DEX TX: Using backend transaction type:', txData.type);
        }
        
        // Include gas pricing params from backend
        if (txData.gasPrice) {
            // Legacy gas pricing (like bonding curve)
            txParams.gasPrice = txData.gasPrice;
            console.log('✅ DEX TX: Using backend legacy gas price:', txData.gasPrice);
        } else if (txData.maxFeePerGas && txData.maxPriorityFeePerGas) {
            // EIP-1559 gas pricing
            txParams.maxFeePerGas = txData.maxFeePerGas;
            txParams.maxPriorityFeePerGas = txData.maxPriorityFeePerGas;
            console.log('✅ DEX TX: Using backend EIP-1559 gas params', {
                maxFeePerGas: txData.maxFeePerGas,
                maxPriorityFeePerGas: txData.maxPriorityFeePerGas
            });
        }
        
        console.log('📤 Sending to MetaMask:', txParams);
        
        // eth_sendTransaction signs AND submits to blockchain
        const txHash = await provider.request({
            method: 'eth_sendTransaction',
            params: [txParams]
        });
        
        console.log('✅ MetaMask returned tx hash:', txHash);
        
        return {
            tx_hash: txHash,
            needs_relay: false  // Already on blockchain
        };
    }
    
    /**
     * Sign transaction with Kaspa wallets (Kastle/KasWare)
     * These wallets sign transactions that need backend relay
     * 
     * @private
     * @param {Object} txData - {to, value, data, gas}
     * @param {string} walletType - 'kastle' | 'kasware'
     * @returns {Promise<Object>} {signed_tx, needs_relay: true}
     */
    async _signWithKaspa(txData, walletType) {
        const wallet = this.walletManager.getConnectedWallet();
        
        let signedTx;
        
        if (walletType === 'kastle') {
            // Try window.kastle API first
            if (typeof window.kastle !== 'undefined') {
                signedTx = await window.kastle.request({
                    method: 'kas_signTransaction',
                    params: {
                        to: txData.to,
                        value: txData.value || '0x0',
                        data: txData.data,
                        gas: txData.gas
                    }
                });
            } 
            // Fallback to window.kasware if kastle not available
            else if (typeof window.kasware !== 'undefined') {
                signedTx = await window.kasware.signTransaction({
                    to: txData.to,
                    value: txData.value || '0x0',
                    data: txData.data,
                    gas: txData.gas
                });
            } else {
                throw new Error('Kastle wallet not available for signing');
            }
        } else if (walletType === 'kasware') {
            // Use KasWare API
            if (typeof window.kasware !== 'undefined') {
                signedTx = await window.kasware.signTransaction({
                    to: txData.to,
                    value: txData.value || '0x0',
                    data: txData.data,
                    gas: txData.gas
                });
            } else {
                throw new Error('KasWare wallet not available for signing');
            }
        } else {
            throw new Error(`Unsupported Kaspa wallet type: ${walletType}`);
        }
        
        if (!signedTx) {
            throw new Error('Transaction signing was cancelled or failed');
        }
        
        return {
            signed_tx: signedTx,
            needs_relay: true  // Needs backend to submit to blockchain
        };
    }
    
    // ===== PHASE 4: RELAY TO BLOCKCHAIN =====
    /**
     * Relay signed transaction to blockchain via backend
     * Only called if wallet returns needs_relay: true
     * MetaMask transactions skip this phase entirely
     * 
     * @param {string} signedTx - Signed transaction hex string
     * @returns {Promise<Object>} {success, tx_hash}
     */
    async relayTransaction(signedTx) {
        const response = await fetch('/api/relay/transaction', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({signed_tx: signedTx})
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.message || 'Request failed');
        }
        
        return await response.json();
    }
    
    // ===== PHASE 5: MONITOR VIA SSE =====
    /**
     * Monitor transaction confirmation via Server-Sent Events with fallback polling
     * ⚠️ H-2 FIX: Properly cleanup SSE connections to prevent memory leaks
     * ⚠️ NEW FIX: Fallback to polling if SSE connection fails
     * 
     * @param {string} txHash - Transaction hash to monitor
     * @param {Object} callbacks - {onUpdate, onConfirm, onError}
     */
    async monitorTransaction(txHash, callbacks) {
        const eventSource = new EventSource(`/api/tx/${txHash}/stream`);
        let receivedTerminalStatus = false;
        let fallbackActivated = false;
        
        // Listen for 'status' events (default event type from backend)
        eventSource.addEventListener('status', (event) => {
            const data = JSON.parse(event.data);
            
            if (data.status === 'confirmed') {
                receivedTerminalStatus = true;
                callbacks.onConfirm(data);
                eventSource.close();
                this.activeTransactions.delete(txHash);
            } else if (data.status === 'failed') {
                receivedTerminalStatus = true;
                callbacks.onError(data.error);
                eventSource.close();
                this.activeTransactions.delete(txHash);
            } else {
                callbacks.onUpdate(data);
            }
        });
        
        // Listen for 'complete' event (clean shutdown signal from backend)
        eventSource.addEventListener('complete', (event) => {
            receivedTerminalStatus = true;
            eventSource.close();
            this.activeTransactions.delete(txHash);
        });
        
        eventSource.onerror = async () => {
            eventSource.close();
            this.activeTransactions.delete(txHash);
            
            // If we haven't received terminal status, fall back to polling
            if (!receivedTerminalStatus && !fallbackActivated) {
                fallbackActivated = true;
                console.log(`SSE connection lost for ${txHash}, falling back to polling...`);
                callbacks.onUpdate({
                    status: 'pending',
                    message: 'Connection lost, checking transaction status...'
                });
                
                // Fall back to polling
                await this._pollTransactionStatus(txHash, callbacks);
            }
        };
        
        // ⚠️ H-2 FIX: Store for cleanup on page unload
        this.activeTransactions.set(txHash, eventSource);
    }
    
    /**
     * Fallback polling method when SSE fails
     * Polls transaction status endpoint directly
     * 
     * @param {string} txHash - Transaction hash to monitor
     * @param {Object} callbacks - {onUpdate, onConfirm, onError}
     * @private
     */
    async _pollTransactionStatus(txHash, callbacks) {
        const maxAttempts = 60;  // 2 minutes max (2s interval * 60)
        const pollInterval = 2000;  // 2 seconds
        
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
                const response = await fetch(`/api/tx/${txHash}/status`);
                if (!response.ok) {
                    throw new Error('Failed to fetch status');
                }
                
                const status = await response.json();
                
                if (status.status === 'confirmed') {
                    callbacks.onConfirm(status);
                    return;
                } else if (status.status === 'failed') {
                    callbacks.onError(status.error || 'Transaction failed');
                    return;
                } else {
                    callbacks.onUpdate(status);
                }
                
                // Wait before next poll
                await new Promise(resolve => setTimeout(resolve, pollInterval));
                
            } catch (error) {
                console.error(`Polling error for ${txHash}:`, error);
                
                // If it's the last attempt, report error
                if (attempt === maxAttempts - 1) {
                    callbacks.onError('Transaction monitoring failed. Please verify status on explorer.');
                    return;
                }
                
                // Otherwise, wait and retry
                await new Promise(resolve => setTimeout(resolve, pollInterval));
            }
        }
        
        // Timeout reached
        callbacks.onError('Transaction monitoring timed out. Please verify status on explorer.');
    }
    
    // ⚠️ H-2 FIX: Network Validation
    /**
     * Validate user is on correct network (Kasplex Testnet)
     * If not, prompt to switch networks
     * 
     * @throws {Error} If user cancels network switch
     */
    async validateNetwork() {
        // Check wallet type first - only validate network for MetaMask
        const wallet = this.walletManager.getConnectedWallet();
        if (!wallet) {
            throw new Error('Wallet not connected. Please connect your wallet first.');
        }
        
        const walletType = wallet.wallet_type;
        
        // Kastle and KasWare wallets: skip network validation (assume correct network)
        if (walletType === 'kastle' || walletType === 'kasware') {
            console.log(`[TransactionManager] Skipping network validation for ${walletType} wallet`);
            return;
        }
        
        // MetaMask: validate and switch network if needed
        if (walletType === 'metamask') {
            const provider = this.walletManager.getMetaMaskProvider();
            if (!provider) {
                throw new Error('MetaMask not found. Please install MetaMask to continue.');
            }
            
            const chainId = await provider.request({method: 'eth_chainId'});
            
            const KASPLEX_TESTNET_CHAIN_ID = '0x28C64'; // 167012 in hex
            
            if (chainId !== KASPLEX_TESTNET_CHAIN_ID) {
                // Use native confirm for simplicity (async/await compatible)
                const switchRequested = confirm(
                    'Wrong Network\n\n' +
                    'Please switch to Kasplex Testnet (Chain ID: 167012).\n\n' +
                    'Click OK to switch networks, or Cancel to abort.'
                );
                
                if (!switchRequested) {
                    throw new Error('User cancelled network switch');
                }
                
                try {
                    await provider.request({
                        method: 'wallet_switchEthereumChain',
                        params: [{chainId: KASPLEX_TESTNET_CHAIN_ID}]
                    });
                } catch (switchError) {
                    // Chain not added to wallet yet
                    if (switchError.code === 4902) {
                        await provider.request({
                            method: 'wallet_addEthereumChain',
                            params: [{
                                chainId: KASPLEX_TESTNET_CHAIN_ID,
                                chainName: 'Kasplex zkEVM Testnet',
                                nativeCurrency: {
                                    name: 'KAS',
                                    symbol: 'KAS',
                                    decimals: 18
                                },
                                rpcUrls: ['https://rpc.kasplextest.xyz'],
                                blockExplorerUrls: ['https://explorer.testnet.kasplextest.xyz']
                            }]
                        });
                    } else {
                        throw switchError;
                    }
                }
            }
        }
    }
    
    // ===== COMPLETE FLOW (Wallet-aware execution) =====
    /**
     * Execute complete transaction flow with wallet-specific branching
     * 
     * @param {string} txType - 'create_token' | 'buy' | 'sell' | 'claim_fees'
     * @param {Object} params - Transaction-specific parameters
     * @param {Object} callbacks - {onUpdate, onConfirm, onError}
     * 
     * @example
     * await txManager.executeTransaction('buy', {
     *     token_address: '0x...',
     *     kas_amount: 10.5,
     *     min_tokens_out: 950000,  // Slippage protection
     *     deadline: Math.floor(Date.now()/1000) + 300  // 5 min
     * }, {
     *     onUpdate: (status) => showSpinner(status),
     *     onConfirm: (receipt) => showSuccess(receipt),
     *     onError: (error) => showError(error)
     * });
     */
    async executeTransaction(txType, params, callbacks) {
        try {
            // ⚠️ H-2 FIX: Validate network before transaction
            await this.validateNetwork();
            
            // Phase 2: Build unsigned tx
            callbacks.onUpdate({status: 'building', message: 'Preparing transaction...'});
            const buildResult = await this.buildTransaction(txType, params);
            
            if (!buildResult.success) {
                throw new Error(buildResult.error);
            }
            
            // Phase 3: Sign & Submit (wallet-specific)
            callbacks.onUpdate({status: 'signing', message: 'Please sign in your wallet...'});
            const signResult = await this.signAndSubmitTransaction(buildResult.tx_data);
            
            let txHash;
            
            // Phase 4: Relay (only if wallet needs it)
            if (signResult.needs_relay) {
                callbacks.onUpdate({status: 'relaying', message: 'Submitting to blockchain...'});
                const relayResult = await this.relayTransaction(signResult.signed_tx);
                
                if (!relayResult.success) {
                    throw new Error(relayResult.error);
                }
                txHash = relayResult.tx_hash;
            } else {
                // MetaMask already submitted - register it for monitoring
                txHash = signResult.tx_hash;
                
                // Register MetaMask transaction in database for monitoring
                try {
                    await fetch('/api/tx/register', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            tx_hash: txHash,
                            tx_type: txType,
                            user_address: params.user_address || this.walletManager.getConnectedAddress(),
                            token_id: params.token_id
                        })
                    });
                } catch (error) {
                    console.warn('Failed to register transaction:', error);
                    // Don't fail the transaction if registration fails
                }
            }
            
            // Phase 5: Monitor confirmation
            callbacks.onUpdate({status: 'pending', message: 'Waiting for confirmation...'});
            await this.monitorTransaction(txHash, callbacks);
            
        } catch (error) {
            callbacks.onError(error.message);
        }
    }
    
    // ⚠️ H-2 FIX: Cleanup on page unload
    /**
     * Close all active SSE connections to prevent memory leaks
     * Called automatically on beforeunload, pagehide, and popstate events
     */
    closeAllConnections() {
        this.activeTransactions.forEach(eventSource => eventSource.close());
        this.activeTransactions.clear();
    }
    
    // ===== AUTO-SLIPPAGE: Progressive Retry System =====
    
    /**
     * Check if error is slippage-related
     * @private
     * @param {Error} error - Error from transaction or quote
     * @returns {boolean} True if slippage-related error
     */
    _isSlippageError(error) {
        if (!error) return false;
        
        // Safely convert error to string message
        let errorMsg = '';
        if (typeof error === 'string') {
            errorMsg = error;
        } else if (error.message && typeof error.message === 'string') {
            errorMsg = error.message;
        } else if (typeof error.toString === 'function') {
            errorMsg = error.toString();
        } else if (typeof error === 'object') {
            errorMsg = JSON.stringify(error);
        }
        errorMsg = errorMsg.toLowerCase();
        
        const errorData = error.data?.message?.toLowerCase() || '';
        
        // Known slippage error patterns
        const slippagePatterns = [
            'slippage too high',
            'insufficient_output_amount',
            'insufficient output amount',
            'price impact too high',
            'max_slippage',
            'exceeds maximum slippage',
            'slippage tolerance exceeded',
            'price movement',
            'execution reverted',  // Generic revert that might be slippage
            'transaction would fail'  // Gas estimation failure often means slippage
        ];
        
        return slippagePatterns.some(pattern => 
            errorMsg.includes(pattern) || errorData.includes(pattern)
        );
    }
    
    /**
     * Execute buy/sell trade with automatic progressive slippage retry
     * Starts with tight slippage and increases until transaction succeeds
     * 
     * @param {string} tradeType - 'buy' | 'sell'
     * @param {Object} params - Base parameters (token_address, kas_amount/token_amount)
     * @param {Object} callbacks - {onRetry, onStatusUpdate} for UI updates
     * @param {AbortSignal} signal - Optional abort signal for cancellation
     * @returns {Promise<Object>} {success, tx_hash, slippage_used}
     */
    async executeTradeWithAutoSlippage(tradeType, params, callbacks = {}, signal = null) {
        const isGraduated = params.is_graduated || false;
        const {onRetry, onStatusUpdate} = callbacks;
        
        let slippageLadder;
        
        if (isGraduated) {
            // DEX: Calculate optimal slippage based on price impact
            if (onStatusUpdate) {
                onStatusUpdate('Calculating optimal slippage...');
            }
            
            const initialQuoteParams = {...params, slippage_bps: 0};
            const initialQuote = await this.getQuote(tradeType, initialQuoteParams, signal);
            
            if (!initialQuote.success) {
                throw new Error(initialQuote.error || 'Failed to get initial quote');
            }
            
            // Extract price impact from DEX quote
            const priceImpactPct = initialQuote.price_impact_pct || 0;
            const priceImpactBps = Math.round(priceImpactPct * 100);
            
            // Calculate: price_impact + 0.5% buffer, minimum 0.5%, max 3%
            const safetyBufferBps = 50;
            const minimumSlippageBps = 50;
            const maxSlippageBps = 300;
            const calculatedSlippageBps = Math.max(priceImpactBps + safetyBufferBps, minimumSlippageBps);
            const optimalSlippageBps = Math.min(calculatedSlippageBps, maxSlippageBps);
            
            console.log(`🎯 DEX Slippage: Price impact ${priceImpactPct.toFixed(2)}% → Using ${(optimalSlippageBps / 100).toFixed(2)}% slippage`);
            
            // DEX ladder: optimal → 1% → 2% → 3%
            slippageLadder = [optimalSlippageBps, 100, 200, 300];
        } else {
            // Bonding Curve: Use static ladder (UNCHANGED)
            slippageLadder = [50, 100, 200, 500, 750, 1000];
        }
        
        const maxAttempts = slippageLadder.length;
        
        // ✅ FIX: Track if wallet popup was shown to prevent double-popup retries
        let walletPopupShown = false;
        
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const slippage_bps = slippageLadder[attempt];
            const slippage_percent = (slippage_bps / 100).toFixed(2);
            
            try {
                // Notify UI of retry attempt
                if (onRetry && attempt > 0) {
                    onRetry({
                        attempt: attempt + 1,
                        maxAttempts,
                        slippage_bps,
                        slippage_percent
                    });
                }
                
                if (onStatusUpdate) {
                    const statusMsg = attempt === 0 
                        ? `Getting quote with ${slippage_percent}% slippage...`
                        : `Retrying with ${slippage_percent}% slippage (attempt ${attempt + 1}/${maxAttempts})...`;
                    onStatusUpdate(statusMsg);
                }
                
                // PHASE 1: Get quote with current slippage
                const quoteParams = {
                    ...params,
                    slippage_bps
                };
                
                const quote = await this.getQuote(tradeType, quoteParams, signal);
                
                if (!quote.success) {
                    // If quote fails with slippage error and we have retries left, continue
                    if (this._isSlippageError(new Error(quote.error)) && attempt < maxAttempts - 1) {
                        console.log(`[AutoSlippage] Quote failed with slippage error, retrying...`);
                        continue;
                    }
                    throw new Error(quote.error || 'Quote failed');
                }
                
                if (onStatusUpdate) {
                    onStatusUpdate('Building transaction...');
                }
                
                // PHASE 2: Build transaction with min values from quote
                const buildParams = {
                    ...params
                };
                
                // Calculate slippage-adjusted minimums
                // For DEX quotes: need to calculate from amount_out + slippage_bps
                // For bonding curve: use provided min_tokens_out_wei / min_kas_out_wei
                if (tradeType === 'buy') {
                    if (quote.min_tokens_out_wei) {
                        // Bonding curve format
                        buildParams.min_tokens_out = quote.min_tokens_out_wei;
                    } else if (quote.amount_out) {
                        // DEX format - calculate min from amount_out and slippage
                        const amountOutWei = window.ethers.utils.parseEther(quote.amount_out.toString());
                        const minTokensOut = amountOutWei.mul(10000 - slippage_bps).div(10000);
                        buildParams.min_tokens_out = minTokensOut.toString();
                    }
                } else {
                    if (quote.min_kas_out_wei) {
                        // Bonding curve format
                        buildParams.min_kas_out = quote.min_kas_out_wei;
                    } else if (quote.amount_out) {
                        // DEX format - calculate min from amount_out and slippage
                        const amountOutWei = window.ethers.utils.parseEther(quote.amount_out.toString());
                        const minKasOut = amountOutWei.mul(10000 - slippage_bps).div(10000);
                        buildParams.min_kas_out = minKasOut.toString();
                    }
                }
                
                const buildResult = await this.buildTransaction(tradeType, buildParams);
                
                if (!buildResult.success) {
                    if (this._isSlippageError(new Error(buildResult.error)) && attempt < maxAttempts - 1) {
                        console.log(`[AutoSlippage] Build failed with slippage error, retrying...`);
                        continue;
                    }
                    throw new Error(buildResult.error || 'Failed to build transaction');
                }
                
                if (onStatusUpdate) {
                    onStatusUpdate('Please sign the transaction in your wallet...');
                }
                
                // ✅ FIX: Mark that we're about to show wallet popup
                walletPopupShown = true;
                
                // PHASE 3: Sign and submit
                const signResult = await this.signAndSubmitTransaction(buildResult.tx_data);
                
                // Success! Return result with slippage used
                return {
                    success: true,
                    tx_hash: signResult.tx_hash,
                    signed_tx: signResult.signed_tx,
                    needs_relay: signResult.needs_relay,
                    slippage_used: slippage_bps,
                    slippage_percent,
                    attempts: attempt + 1
                };
                
            } catch (error) {
                // Safely extract error message
                let errorMessage = 'Unknown error';
                if (typeof error === 'string') {
                    errorMessage = error;
                } else if (error.message && typeof error.message === 'string') {
                    errorMessage = error.message;
                } else if (typeof error.toString === 'function') {
                    try {
                        errorMessage = error.toString();
                    } catch (e) {
                        errorMessage = JSON.stringify(error);
                    }
                } else if (typeof error === 'object') {
                    errorMessage = JSON.stringify(error);
                }
                
                console.error(`[AutoSlippage] Attempt ${attempt + 1} failed:`, errorMessage);
                console.error('Full error:', error.stack || error);
                
                // ✅ FIX: NEVER retry after wallet popup was shown to prevent double transactions
                if (walletPopupShown) {
                    console.warn('[AutoSlippage] Wallet popup was shown - cannot retry to avoid double transaction');
                    throw new Error(`Transaction failed: ${errorMessage}`);
                }
                
                // Check if this is a slippage error and we have retries left
                if (this._isSlippageError(error) && attempt < maxAttempts - 1) {
                    console.log(`[AutoSlippage] Slippage error detected, will retry with ${(slippageLadder[attempt + 1] / 100).toFixed(2)}%`);
                    // Continue to next retry
                    continue;
                }
                
                // Non-slippage error or max retries reached - fail immediately
                throw new Error(
                    attempt === maxAttempts - 1 
                        ? `Transaction failed after ${maxAttempts} attempts. Last error: ${errorMessage}`
                        : errorMessage
                );
            }
        }
        
        // Should never reach here
        throw new Error('Auto-slippage retry loop completed without result');
    }
}

// Initialize globally for use across the application
window.TransactionManager = TransactionManager;
