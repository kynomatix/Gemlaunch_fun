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
     * 
     * @param {string} quoteType - 'buy' | 'sell'
     * @param {Object} params - {token_address, kas_amount} for buy | {token_address, token_amount} for sell
     * @param {AbortSignal} signal - Optional AbortController signal for canceling requests
     * @returns {Promise<Object>} Quote data with tokens_out, fees, slippage, price_impact
     */
    async getQuote(quoteType, params, signal = null) {
        const endpoint = quoteType === 'buy' 
            ? '/api/trade/quote-buy' 
            : '/api/trade/quote-sell';
        
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
     * 
     * @param {string} txType - 'create_token' | 'buy' | 'sell' | 'claim_fees'
     * @param {Object} params - Transaction-specific parameters
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
        } else {
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
     * @private
     * @param {Object} txData - {to, value, data, gas}
     * @returns {Promise<Object>} {tx_hash, needs_relay: false}
     */
    async _signWithMetaMask(txData) {
        const provider = this.walletManager.getMetaMaskProvider();
        const accounts = await provider.request({method: 'eth_accounts'});
        
        const txParams = {
            from: accounts[0],
            to: txData.to,
            value: txData.value || '0x0',
            data: txData.data,
            gas: txData.gas
        };
        
        // eth_sendTransaction signs AND submits to blockchain
        const txHash = await provider.request({
            method: 'eth_sendTransaction',
            params: [txParams]
        });
        
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
     * Monitor transaction confirmation via Server-Sent Events
     * ⚠️ H-2 FIX: Properly cleanup SSE connections to prevent memory leaks
     * 
     * @param {string} txHash - Transaction hash to monitor
     * @param {Object} callbacks - {onUpdate, onConfirm, onError}
     */
    async monitorTransaction(txHash, callbacks) {
        const eventSource = new EventSource(`/api/tx/${txHash}/stream`);
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.status === 'confirmed') {
                callbacks.onConfirm(data);
                eventSource.close();
                this.activeTransactions.delete(txHash);
            } else if (data.status === 'failed') {
                callbacks.onError(data.error);
                eventSource.close();
                this.activeTransactions.delete(txHash);
            } else {
                callbacks.onUpdate(data);
            }
        };
        
        eventSource.onerror = () => {
            callbacks.onError('Connection lost');
            eventSource.close();
            this.activeTransactions.delete(txHash);
        };
        
        // ⚠️ H-2 FIX: Store for cleanup on page unload
        this.activeTransactions.set(txHash, eventSource);
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
                                blockExplorerUrls: ['http://explorer.testnet.kasplextest.xyz']
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
                // MetaMask already submitted - go straight to monitoring
                txHash = signResult.tx_hash;
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
        
        const errorMsg = (error.message || error.toString()).toLowerCase();
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
        // Progressive slippage ladder: 0.5% → 1% → 2% → 5% → 7.5% → 10%
        const slippageLadder = [50, 100, 200, 500, 750, 1000];
        const maxAttempts = slippageLadder.length;
        
        const {onRetry, onStatusUpdate} = callbacks;
        
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
                
                if (tradeType === 'buy') {
                    buildParams.min_tokens_out = quote.min_tokens_out_wei;
                } else {
                    // Send wei value to avoid float precision loss
                    buildParams.min_kas_out = quote.min_kas_out_wei;
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
                console.error(`[AutoSlippage] Attempt ${attempt + 1} failed:`, error.message || error.toString());
                console.error('Full error:', error.stack);
                
                // Check if this is a slippage error and we have retries left
                if (this._isSlippageError(error) && attempt < maxAttempts - 1) {
                    console.log(`[AutoSlippage] Slippage error detected, will retry with ${(slippageLadder[attempt + 1] / 100).toFixed(2)}%`);
                    // Continue to next retry
                    continue;
                }
                
                // Non-slippage error or max retries reached - fail immediately
                throw new Error(
                    attempt === maxAttempts - 1 
                        ? `Transaction failed after ${maxAttempts} attempts. Last error: ${error.message}`
                        : error.message
                );
            }
        }
        
        // Should never reach here
        throw new Error('Auto-slippage retry loop completed without result');
    }
}

// Initialize globally for use across the application
window.TransactionManager = TransactionManager;
