/**
 * Vesting Portal JavaScript Module
 * Manages the creator vesting portal functionality
 */

(function(window, document) {
    'use strict';

    // Module state
    const VestingPortal = {
        currentTokenId: null,
        currentTokenSymbol: null,
        pollInterval: null,
        transactionManager: null,
        walletManager: null,

        // Initialize the portal
        init: function() {
            console.log('🔐 Initializing Vesting Portal...');
            
            // Initialize wallet and transaction managers
            this.walletManager = window.WalletManager;
            this.transactionManager = new window.TransactionManager(this.walletManager);
            
            // Load user's PRO tokens
            this.loadUserTokens();
        },

        // Load user's PRO tokens with vesting
        loadUserTokens: async function() {
            try {
                const walletAddress = this.walletManager?.walletAddress;
                if (!walletAddress) {
                    this.showNoTokensMessage();
                    return;
                }

                const response = await fetch(`/api/user/tokens?wallet=${walletAddress}`);
                if (!response.ok) throw new Error('Failed to fetch tokens');

                const data = await response.json();
                
                // Filter for PRO tokens with vesting (reserved_percentage > 0)
                const proTokens = (data.tokens || []).filter(token => 
                    parseFloat(token.reserved_percentage || 0) > 0 &&
                    (token.marketing_vesting_address || token.team_vesting_address)
                );

                if (proTokens.length === 0) {
                    this.showNoTokensMessage();
                    return;
                }

                // Populate token selector
                this.populateTokenSelector(proTokens);
                
                // Auto-select first token
                if (proTokens.length > 0) {
                    document.getElementById('tokenSelect').value = proTokens[0].id;
                    this.loadVestingStatus();
                }
            } catch (error) {
                console.error('Error loading user tokens:', error);
                this.showNoTokensMessage();
            }
        },

        // Populate token selector dropdown
        populateTokenSelector: function(tokens) {
            const selector = document.getElementById('tokenSelect');
            selector.innerHTML = '<option value="">-- Select a token --</option>';
            
            tokens.forEach(token => {
                const option = document.createElement('option');
                option.value = token.id;
                option.textContent = `${token.name} (${token.symbol}) - ${token.reserved_percentage}% Reserved`;
                selector.appendChild(option);
            });
        },

        // Show no tokens message
        showNoTokensMessage: function() {
            document.getElementById('loadingState').style.display = 'none';
            document.getElementById('vestingContent').style.display = 'none';
            document.getElementById('noTokensMessage').style.display = 'block';
        },

        // Load vesting status for selected token
        loadVestingStatus: async function() {
            const tokenId = document.getElementById('tokenSelect').value;
            if (!tokenId) {
                document.getElementById('vestingContent').style.display = 'none';
                return;
            }

            this.currentTokenId = tokenId;
            
            // Show loading
            document.getElementById('loadingState').style.display = 'block';
            document.getElementById('vestingContent').style.display = 'none';
            document.getElementById('noTokensMessage').style.display = 'none';

            try {
                const response = await fetch(`/api/token/${tokenId}/vesting/status`);
                if (!response.ok) throw new Error('Failed to fetch vesting status');

                const data = await response.json();
                this.currentTokenSymbol = data.token_symbol;
                
                // Update UI with vesting data
                this.updateVestingUI(data);

                // Show vesting content
                document.getElementById('loadingState').style.display = 'none';
                document.getElementById('vestingContent').style.display = 'block';

                // Start polling for updates
                this.startPolling();
            } catch (error) {
                console.error('Error loading vesting status:', error);
                document.getElementById('loadingState').style.display = 'none';
                this.showToast('Error Loading Vesting', 'Failed to load vesting status. Please try again.', 'error');
            }
        },

        // Update UI with vesting data
        updateVestingUI: function(data) {
            // Update marketing section
            if (data.marketing) {
                this.updateVestingSection('marketing', data.marketing, data.token_symbol);
            } else {
                document.getElementById('marketingSection').style.display = 'none';
            }

            // Update team section
            if (data.team) {
                this.updateVestingSection('team', data.team, data.token_symbol);
            } else {
                document.getElementById('teamSection').style.display = 'none';
            }
        },

        // Update a specific vesting section
        updateVestingSection: function(type, vestingData, tokenSymbol) {
            const {
                total_allocated,
                total_unlocked,
                total_claimed,
                available_to_claim,
                start_time,
                cliff_duration,
                vesting_duration
            } = vestingData;

            // Format amounts using VestingUtils
            const totalFormatted = window.VestingUtils.formatTokenAmount(total_allocated);
            const unlockedFormatted = window.VestingUtils.formatTokenAmount(total_unlocked);
            const claimedFormatted = window.VestingUtils.formatTokenAmount(total_claimed);
            const availableFormatted = window.VestingUtils.formatTokenAmount(available_to_claim);

            // Update stat cards
            document.getElementById(`${type}-total`).textContent = totalFormatted;
            document.getElementById(`${type}-unlocked`).textContent = unlockedFormatted;
            document.getElementById(`${type}-claimed`).textContent = claimedFormatted;
            document.getElementById(`${type}-available`).textContent = availableFormatted;

            // Calculate and update progress
            const progress = window.VestingUtils.calculateProgress(total_unlocked, total_allocated);
            document.getElementById(`${type}-progress`).textContent = progress.toFixed(1) + '%';
            document.getElementById(`${type}-progress-bar`).style.width = progress + '%';

            // Update schedule text
            const scheduleText = window.VestingUtils.formatUnlockSchedule(type, start_time, vesting_duration);
            document.getElementById(`${type}-schedule`).textContent = scheduleText;

            // Update next unlock info
            const nextUnlock = window.VestingUtils.formatNextUnlock(type, start_time, total_claimed, total_allocated);
            document.getElementById(`${type}-next-unlock`).textContent = `Next unlock: ${nextUnlock}`;

            // Update withdraw section
            document.getElementById(`${type}-withdraw-amount`).textContent = `${availableFormatted} ${tokenSymbol}`;
            
            // Enable/disable withdraw button
            const withdrawBtn = document.getElementById(`withdraw${type.charAt(0).toUpperCase() + type.slice(1)}Btn`);
            const available = parseFloat(available_to_claim);
            withdrawBtn.disabled = available <= 0;
        },

        // Start polling for vesting status updates
        startPolling: function() {
            // Clear existing interval
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
            }

            // Poll every 30 seconds
            this.pollInterval = setInterval(() => {
                if (this.currentTokenId) {
                    this.loadVestingStatus();
                }
            }, 30000);
        },

        // Stop polling
        stopPolling: function() {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }
        },

        // Withdraw marketing tokens
        withdrawMarketing: async function() {
            await this.handleWithdrawal('marketing', 'withdraw-marketing');
        },

        // Withdraw team tokens
        withdrawTeam: async function() {
            await this.handleWithdrawal('team', 'withdraw-team');
        },

        // Toast notification system
        showToast: function(title, message, type = 'info') {
            // Create toast container if it doesn't exist
            let toastContainer = document.getElementById('toastContainer');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.id = 'toastContainer';
                toastContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 10000; display: flex; flex-direction: column; gap: 10px;';
                document.body.appendChild(toastContainer);
            }
            
            // Create toast element
            const toast = document.createElement('div');
            toast.style.cssText = `
                background: ${type === 'success' ? 'linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(22, 163, 74, 0.95))' : 
                             type === 'error' ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(220, 38, 38, 0.95))' : 
                             'linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(37, 99, 235, 0.95))'};
                color: white;
                padding: 16px 20px;
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                min-width: 300px;
                max-width: 400px;
                backdrop-filter: blur(10px);
                border: 1px solid ${type === 'success' ? 'rgba(34, 197, 94, 0.5)' : 
                                   type === 'error' ? 'rgba(239, 68, 68, 0.5)' : 
                                   'rgba(59, 130, 246, 0.5)'};
                transform: translateX(100%);
                transition: transform 0.3s ease-out;
                cursor: pointer;
            `;
            
            const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
            
            toast.innerHTML = `
                <div style="display: flex; align-items: start; gap: 12px;">
                    <div style="font-size: 20px;">${icon}</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 4px;">${this.escapeHtml(title)}</div>
                        <div style="font-size: 0.9rem; opacity: 0.95;">${this.escapeHtml(message)}</div>
                    </div>
                </div>
            `;
            
            // Click to dismiss
            toast.onclick = () => {
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            };
            
            toastContainer.appendChild(toast);
            
            // Slide in
            setTimeout(() => {
                toast.style.transform = 'translateX(0)';
            }, 10);
            
            // Auto dismiss after 5 seconds
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.style.transform = 'translateX(100%)';
                    setTimeout(() => toast.remove(), 300);
                }
            }, 5000);
        },

        // HTML escape utility to prevent XSS
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        // Handle withdrawal transaction
        handleWithdrawal: async function(type, endpoint) {
            const btn = document.getElementById(`withdraw${type.charAt(0).toUpperCase() + type.slice(1)}Btn`);
            
            try {
                // Check wallet connection
                if (!this.walletManager.isWalletConnected()) {
                    this.showToast('Wallet Required', 'Please connect your wallet first', 'info');
                    await this.walletManager.connectWallet();
                    return;
                }

                const wallet = this.walletManager.getConnectedWallet();
                if (!wallet) {
                    throw new Error('No wallet connected');
                }

                // Show loading state
                btn.classList.add('loading');
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

                // Build transaction by calling backend directly
                const buildEndpoint = `/api/token/${this.currentTokenId}/vesting/withdraw-${type}`;
                const buildResponse = await fetch(buildEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        creator_address: wallet.wallet_address
                    })
                });

                if (!buildResponse.ok) {
                    const errorData = await buildResponse.json();
                    throw new Error(errorData.error || 'Failed to build transaction');
                }

                const txData = await buildResponse.json();

                if (!txData.success) {
                    throw new Error(txData.error || 'Failed to build transaction');
                }

                // Sign and submit transaction
                const signResult = await this.transactionManager.signAndSubmitTransaction(
                    txData.tx_data,
                    `Withdraw ${type} vesting`
                );

                if (!signResult.success) {
                    throw new Error(signResult.error || 'Transaction failed');
                }

                // Show success message
                this.showToast(
                    'Claim Successful!',
                    `Successfully claimed ${type} vesting tokens. Transaction: ${signResult.txHash.slice(0, 10)}...`,
                    'success'
                );

                // Reload vesting status
                await this.loadVestingStatus();

            } catch (error) {
                console.error(`Error withdrawing ${type} tokens:`, error);
                
                // Display clean error message
                this.showToast(
                    'Claim Failed',
                    error.message || 'Unable to process claim. Please try again later.',
                    'error'
                );
            } finally {
                // Reset button state
                btn.classList.remove('loading');
                btn.innerHTML = '<i class="fas fa-wallet"></i> Withdraw';
                // Will be re-enabled/disabled by loadVestingStatus()
            }
        }
    };

    // Global functions for onclick handlers
    window.loadVestingStatus = function() {
        VestingPortal.loadVestingStatus();
    };

    window.withdrawMarketing = function() {
        VestingPortal.withdrawMarketing();
    };

    window.withdrawTeam = function() {
        VestingPortal.withdrawTeam();
    };

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        VestingPortal.init();
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        VestingPortal.stopPolling();
    });

    // Export module
    window.VestingPortal = VestingPortal;

})(window, document);
