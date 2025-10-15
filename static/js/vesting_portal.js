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
                alert('Failed to load vesting status. Please try again.');
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

        // Handle withdrawal transaction
        handleWithdrawal: async function(type, endpoint) {
            const btn = document.getElementById(`withdraw${type.charAt(0).toUpperCase() + type.slice(1)}Btn`);
            
            try {
                // Check wallet connection
                if (!this.walletManager.isWalletConnected()) {
                    alert('Please connect your wallet first');
                    await this.walletManager.connectWallet();
                    return;
                }

                // Show loading state
                btn.classList.add('loading');
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

                // Build transaction
                const txData = await this.transactionManager.buildTransaction('vesting_withdraw', {
                    token_id: this.currentTokenId,
                    vesting_type: type
                });

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
                alert(`Successfully withdrew ${type} tokens! Transaction: ${signResult.txHash}`);

                // Reload vesting status
                await this.loadVestingStatus();

            } catch (error) {
                console.error(`Error withdrawing ${type} tokens:`, error);
                alert(`Failed to withdraw ${type} tokens: ${error.message}`);
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
