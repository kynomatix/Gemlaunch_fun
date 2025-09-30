// Token Detail Page JavaScript Module
// Using IIFE (Immediately Invoked Function Expression) to avoid global scope pollution
(function(window, document) {
    'use strict';

    // Module-scoped variables - avoid global pollution
    const TokenDetail = {
        // Modal System
        modals: {
            // Show a custom alert modal
            alert: function(title, message, type = 'info', callback) {
                const iconClass = type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle';
                const iconColor = type === 'success' ? '#4CAF50' : type === 'error' ? '#FF5252' : '#20B2AA';
                
                const modalHTML = `
                    <div id="customAlertModal" class="modal" style="display: flex;">
                        <div class="modal-content" style="max-width: 400px;">
                            <div class="modal-header">
                                <h3><i class="fas ${iconClass}" style="color: ${iconColor};"></i> ${title}</h3>
                                <button class="modal-close" onclick="TokenDetail.modals.closeModal('customAlertModal')">&times;</button>
                            </div>
                            <div class="modal-body">
                                <p style="color: #CCC; margin: 0; line-height: 1.5;">${message}</p>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-primary" onclick="TokenDetail.modals.closeModal('customAlertModal')">
                                    <i class="fas fa-check"></i> OK
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                const existingModal = document.getElementById('customAlertModal');
                if (existingModal) existingModal.remove();
                
                document.body.insertAdjacentHTML('beforeend', modalHTML);
                
                if (callback) {
                    const modal = document.getElementById('customAlertModal');
                    const okBtn = modal.querySelector('.btn-primary');
                    okBtn.onclick = function() {
                        TokenDetail.modals.closeModal('customAlertModal');
                        callback();
                    };
                }
            },
            
            // Show a confirm modal
            confirm: function(title, message, onConfirm, onCancel) {
                const modalHTML = `
                    <div id="customConfirmModal" class="modal" style="display: flex;">
                        <div class="modal-content" style="max-width: 450px;">
                            <div class="modal-header">
                                <h3>${title}</h3>
                                <button class="modal-close" onclick="TokenDetail.modals.closeModal('customConfirmModal')">&times;</button>
                            </div>
                            <div class="modal-body">
                                <div style="color: #CCC; line-height: 1.5;">${message}</div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" id="confirmCancelBtn">
                                    <i class="fas fa-times"></i> Cancel
                                </button>
                                <button type="button" class="btn btn-primary" id="confirmOkBtn">
                                    <i class="fas fa-check"></i> Confirm
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                const existingModal = document.getElementById('customConfirmModal');
                if (existingModal) existingModal.remove();
                
                document.body.insertAdjacentHTML('beforeend', modalHTML);
                
                document.getElementById('confirmOkBtn').onclick = function() {
                    TokenDetail.modals.closeModal('customConfirmModal');
                    if (onConfirm) onConfirm();
                };
                
                document.getElementById('confirmCancelBtn').onclick = function() {
                    TokenDetail.modals.closeModal('customConfirmModal');
                    if (onCancel) onCancel();
                };
            },
            
            // Show a prompt modal
            prompt: function(title, message, defaultValue, onSubmit, onCancel, placeholder = 'Enter your input here...') {
                const modalHTML = `
                    <div id="customPromptModal" class="modal" style="display: flex;">
                        <div class="modal-content" style="max-width: 500px;">
                            <div class="modal-header">
                                <h3>${title}</h3>
                                <button class="modal-close" onclick="TokenDetail.modals.closeModal('customPromptModal')">&times;</button>
                            </div>
                            <div class="modal-body">
                                <p style="color: #CCC; margin-bottom: 1rem; line-height: 1.5;">${message}</p>
                                <input type="text" id="promptInput" class="form-control" 
                                       value="${defaultValue || ''}" 
                                       placeholder="${placeholder}"
                                       style="width: 100%;">
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" id="promptCancelBtn">
                                    <i class="fas fa-times"></i> Cancel
                                </button>
                                <button type="button" class="btn btn-primary" id="promptSubmitBtn">
                                    <i class="fas fa-check"></i> Submit
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                const existingModal = document.getElementById('customPromptModal');
                if (existingModal) existingModal.remove();
                
                document.body.insertAdjacentHTML('beforeend', modalHTML);
                
                const input = document.getElementById('promptInput');
                setTimeout(() => {
                    input.focus();
                    input.select();
                }, 100);
                
                const submitHandler = function() {
                    const value = document.getElementById('promptInput').value;
                    TokenDetail.modals.closeModal('customPromptModal');
                    if (onSubmit) onSubmit(value);
                };
                
                document.getElementById('promptSubmitBtn').onclick = submitHandler;
                
                input.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        submitHandler();
                    }
                });
                
                document.getElementById('promptCancelBtn').onclick = function() {
                    TokenDetail.modals.closeModal('customPromptModal');
                    if (onCancel) onCancel();
                };
            },
            
            // Close modal
            closeModal: function(modalId) {
                const modal = document.getElementById(modalId);
                if (modal) {
                    modal.style.display = 'none';
                    setTimeout(() => modal.remove(), 300);
                }
            },
            
            // Show notification (uses existing notification system)
            showNotification: function(title, message, type = 'info') {
                TokenDetail.showNotification(title, message, type);
            }
        },
        
        // Trading state
        currentTradeMode: 'buy',
        tokenPrice: null,
        marketCap: null,
        kasToUsd: 0.125,
        tokenSymbol: null,
        tokenName: null,
        isProToken: false,
        
        // Chart state
        currentChartType: 'marketcap',
        myChart: null,
        
        // Token settings from backend
        tokenSettings: {
            holdersOnlyChat: false,
            minTokensToChat: 0,
            minTokensForSpotlight: 500,
            minTokensToCreatePoll: 1000
        },
        
        // Chat state management
        chatState: {
            userTokenBalance: 0,
            messageLoves: {},
            userLoves: [],
            isTokenHolder: true,
            userScore: 0,
            spotlightMessages: [],
            activePolls: [],
            airdropHistory: [],
            replyingTo: null,  // Track which message is being replied to
            messagesData: {}  // Store message data for reply lookups
        },
        
        // Initialize the module with data from server
        init: function(config) {
            this.tokenPrice = config.tokenPrice;
            this.marketCap = config.marketCap;
            this.tokenSymbol = config.tokenSymbol;
            this.tokenName = config.tokenName;
            this.isProToken = config.isProToken || false;
            this.tokenSettings = config.tokenSettings || this.tokenSettings;
            
            // Initialize chat state (NO FAKE BALANCE!)
            // Real token balance will be fetched from server when needed
            this.chatState.userTokenBalance = 0; // Will be updated from actual holdings
            this.chatState.messageLoves = JSON.parse(localStorage.getItem(`loves_${this.tokenSymbol}`) || '{}');
            this.chatState.userLoves = JSON.parse(localStorage.getItem(`userLoves_${this.tokenSymbol}`) || '[]');
            this.chatState.userScore = parseInt(localStorage.getItem(`userScore_${this.tokenSymbol}`)) || 0;
            
            // Auto-collapse sidebar and initialize
            const sidebar = document.getElementById('sidebar');
            const mainContent = document.getElementById('mainContent');
            
            if (sidebar && !sidebar.classList.contains('collapsed')) {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('sidebar-collapsed');
                localStorage.setItem('sidebarCollapsed', 'true');
            }
            
            // Initialize chat with delay
            setTimeout(() => {
                this.initializeChatState();
            }, 100);
        },
        
        // Number formatting function
        formatNumber: function(num, includeDecimals = false) {
            if (num === null || num === undefined) return '0';
            
            const absNum = Math.abs(parseFloat(num));
            
            if (absNum >= 1e12) {
                return (num / 1e12).toFixed(includeDecimals ? 2 : 1).replace(/\.0+$/, '') + 'T';
            } else if (absNum >= 1e9) {
                return (num / 1e9).toFixed(includeDecimals ? 2 : 1).replace(/\.0+$/, '') + 'B';
            } else if (absNum >= 1e6) {
                return (num / 1e6).toFixed(includeDecimals ? 2 : 1).replace(/\.0+$/, '') + 'M';
            } else if (absNum >= 1e3) {
                return (num / 1e3).toFixed(includeDecimals ? 2 : 1).replace(/\.0+$/, '') + 'K';
            }
            
            return parseFloat(num).toLocaleString();
        },
        
        // Save chat state periodically
        saveChatState: function() {
            localStorage.setItem(`loves_${this.tokenSymbol}`, JSON.stringify(this.chatState.messageLoves));
            localStorage.setItem(`userLoves_${this.tokenSymbol}`, JSON.stringify(this.chatState.userLoves));
            localStorage.setItem(`tokenBalance_${this.tokenSymbol}`, this.chatState.userTokenBalance);
            localStorage.setItem(`userScore_${this.tokenSymbol}`, this.chatState.userScore);
            console.log(`💾 Chat state saved for ${this.tokenSymbol}`);
        },
        
        // Initialize chat state
        initializeChatState: async function() {
            console.log('💎 Initializing chat state...');
            
            // Check ownership and set up interface
            this.checkTokenOwnership();
            
            // Load messages from database
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/messages`);
                if (response.ok) {
                    const data = await response.json();
                    const chatContainer = document.getElementById('chatMessages');
                    
                    chatContainer.innerHTML = '';
                    
                    // Clear existing state to avoid duplicates
                    this.chatState.messageLoves = {};
                    this.chatState.userLoves = [];
                    
                    // First pass: store all message data and load reactions from database
                    data.messages.forEach(msg => {
                        this.chatState.messagesData[msg.id] = {
                            user: msg.user,
                            username: msg.user,
                            text: msg.message,
                            wallet: msg.wallet
                        };
                        
                        // Store love count and user's reaction from database
                        this.chatState.messageLoves[msg.id] = msg.love_count || 0;
                        if (msg.is_loved_by_user) {
                            this.chatState.userLoves.push(msg.id);
                        }
                    });
                    
                    // Second pass: display messages with reply information
                    data.messages.forEach(msg => {
                        this.addMessageToChat(
                            msg.user, 
                            msg.message, 
                            false, 
                            msg.id, 
                            msg.wallet,
                            msg.reply_to || null
                        );
                    });
                    
                    console.log(`📥 Loaded ${data.messages.length} messages from database`);
                }
            } catch (error) {
                console.error('Failed to load messages:', error);
            }
            
            // Load active polls from database
            try {
                const userWallet = localStorage.getItem('connectedWallet');
                const response = await fetch(`/api/token/${window.tokenContractAddress}/polls`, {
                    headers: {
                        'X-Wallet-Address': userWallet
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    this.chatState.activePolls = data.polls || [];
                    
                    data.polls.forEach(poll => {
                        this.addPollToChat(poll);
                    });
                    
                    console.log(`📊 Loaded ${data.polls.length} active polls from database`);
                }
            } catch (error) {
                console.error('Failed to load polls:', error);
            }
            
            // Load spotlight messages from database
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/spotlight`);
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.spotlights && data.spotlights.length > 0) {
                        const spotlightContainer = document.getElementById('spotlightMessages');
                        const listContainer = document.getElementById('spotlightMessagesList');
                        
                        spotlightContainer.style.display = 'block';
                        listContainer.innerHTML = '';
                        
                        data.spotlights.forEach(spotlight => {
                            const spotlightEntry = {
                                id: spotlight.id,
                                user: spotlight.user,
                                message: spotlight.message,
                                expiresAt: new Date(spotlight.created_at).getTime() + (60 * 60 * 1000)
                            };
                            this.updateSpotlightDisplay(spotlightEntry);
                        });
                    }
                    
                    console.log(`✨ Loaded ${data.spotlights.length} spotlight messages from database`);
                }
            } catch (error) {
                console.error('Failed to load spotlight messages:', error);
            }
            
            const savedUsername = localStorage.getItem('username');
            console.log(`💎 Chat initialized | Balance: ${this.chatState.userTokenBalance.toLocaleString()} $${this.tokenSymbol} | Username: ${savedUsername || 'Not set'}`);
        },
        
        // Check token ownership
        checkTokenOwnership: function() {
            const userWallet = localStorage.getItem('connectedWallet');
            const tokenCreatorAddress = window.tokenCreatorAddress;
            const isTokenOwner = userWallet && userWallet.toLowerCase() === tokenCreatorAddress.toLowerCase();
            const isProToken = this.isProToken;
            
            console.log(`🔐 Ownership check - User: ${userWallet}, Creator: ${tokenCreatorAddress}, Is Owner: ${isTokenOwner}, Is Pro: ${isProToken}`);
            
            // Set up Holders Only toggle/badge
            const tokenGateContainer = document.getElementById('tokenGateContainer');
            if (tokenGateContainer) {
                if (isTokenOwner) {
                    const isHoldersOnly = this.tokenSettings.holdersOnlyChat;
                    const minTokens = this.tokenSettings.minTokensToChat;
                    
                    if (isProToken) {
                        tokenGateContainer.innerHTML = `
                            <div class="token-gate-toggle pro-token" title="Pro Token: Toggle holders-only mode">
                                <input type="checkbox" id="tokenGateToggle" class="toggle-switch" ${isHoldersOnly ? 'checked' : ''} onchange="TokenDetail.toggleTokenGate()">
                                <label for="tokenGateToggle" class="toggle-label">
                                    <i class="fas fa-crown"></i>
                                    <span class="toggle-text">Holders Only${minTokens > 0 ? ' (' + minTokens.toLocaleString() + ' min)' : ''}</span>
                                </label>
                            </div>
                        `;
                    } else {
                        tokenGateContainer.innerHTML = `
                            <div class="token-gate-toggle" title="Toggle holders-only mode">
                                <input type="checkbox" id="tokenGateToggle" class="toggle-switch" ${isHoldersOnly ? 'checked' : ''} onchange="TokenDetail.toggleTokenGate()">
                                <label for="tokenGateToggle" class="toggle-label">
                                    <i class="fas fa-lock"></i>
                                    <span class="toggle-text">Holders Only${minTokens > 0 ? ' (' + minTokens.toLocaleString() + ' min)' : ''}</span>
                                </label>
                            </div>
                        `;
                    }
                    
                    if (isHoldersOnly) {
                        setTimeout(() => this.toggleTokenGate(), 100);
                    }
                } else {
                    const isHoldersOnly = this.tokenSettings.holdersOnlyChat;
                    const minTokens = this.tokenSettings.minTokensToChat;
                    if (isHoldersOnly) {
                        const icon = this.isProToken ? 'fa-crown' : 'fa-shield-alt';
                        tokenGateContainer.innerHTML = `
                            <div class="token-gate-badge ${this.isProToken ? 'pro-token' : ''}" title="Holders-only chat active">
                                <i class="fas ${icon}"></i>
                                <span>Holders Only${minTokens > 0 ? ' (' + minTokens.toLocaleString() + ' tokens)' : ''}</span>
                            </div>
                        `;
                    } else {
                        tokenGateContainer.innerHTML = '';
                    }
                }
            }
        },
        
        // Generate realistic chart data
        generateChartData: function(type) {
            const now = new Date();
            const data = [];
            const labels = [];
            
            for (let i = 24; i >= 0; i--) {
                const time = new Date(now - i * 60 * 60 * 1000);
                labels.push(time);
                
                let value;
                if (type === 'marketcap') {
                    const baseValue = this.marketCap * 0.7;
                    const trendFactor = (24 - i) / 24;
                    const volatility = (Math.sin(i * 0.5) * 0.1 + Math.random() * 0.1);
                    value = baseValue * (1 + trendFactor * 0.5 + volatility);
                } else {
                    const volatility = Math.sin(i * 0.3) * 0.15 + Math.random() * 0.1 - 0.05;
                    value = this.tokenPrice * (1 + volatility);
                }
                data.push(value);
            }
            return { labels, data };
        },
        
        // Initialize Chart.js chart
        initChart: function() {
            const ctx = document.getElementById('tokenChart').getContext('2d');
            const chartData = this.generateChartData(this.currentChartType);
            
            if (this.myChart) {
                this.myChart.destroy();
            }
            
            this.myChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: this.currentChartType === 'marketcap' ? 'Market Cap' : 'Price',
                        data: chartData.data,
                        borderColor: 'rgba(32, 178, 170, 1)',
                        backgroundColor: 'rgba(32, 178, 170, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        pointHoverBackgroundColor: '#20B2AA',
                        pointHoverBorderColor: '#fff',
                        pointHoverBorderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.9)',
                            titleColor: '#20B2AA',
                            bodyColor: '#fff',
                            borderColor: 'rgba(32, 178, 170, 0.5)',
                            borderWidth: 1,
                            cornerRadius: 5,
                            displayColors: false,
                            callbacks: {
                                label: (context) => {
                                    const value = context.parsed.y;
                                    if (this.currentChartType === 'marketcap') {
                                        return 'Market Cap: $' + (value * 0.125 / 1000).toFixed(2) + 'K';
                                    } else {
                                        return 'Price: ' + value.toFixed(6) + ' KAS ($' + (value * 0.125).toFixed(4) + ')';
                                    }
                                }
                            }
                        },
                        zoom: {
                            zoom: {
                                wheel: {
                                    enabled: true,
                                },
                                pinch: {
                                    enabled: true
                                },
                                mode: 'x',
                            },
                            pan: {
                                enabled: true,
                                mode: 'x',
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'hour',
                                displayFormats: {
                                    hour: 'HH:mm'
                                }
                            },
                            grid: {
                                color: 'rgba(255, 255, 255, 0.05)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#888',
                                font: {
                                    size: 11
                                }
                            }
                        },
                        y: {
                            grid: {
                                color: 'rgba(255, 255, 255, 0.05)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#888',
                                font: {
                                    size: 11
                                },
                                callback: (value) => {
                                    if (this.currentChartType === 'marketcap') {
                                        return '$' + this.formatNumber(value * 0.125, true);
                                    } else {
                                        return value.toFixed(6) + ' KAS';
                                    }
                                }
                            }
                        }
                    }
                }
            });
        },
        
        // Trading functions
        setTradeMode: function(mode) {
            this.currentTradeMode = mode;
            
            document.querySelectorAll('.trade-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelector(`.trade-tab.${mode}`).classList.add('active');
            
            const button = document.getElementById('tradeButton');
            button.className = `trade-button ${mode}`;
            button.innerHTML = mode === 'buy' 
                ? `<i class="fas fa-rocket"></i> Buy $${this.tokenSymbol}`
                : `<i class="fas fa-money-bill"></i> Sell $${this.tokenSymbol}`;
        },
        
        setQuickAmount: function(amount) {
            document.getElementById('kasAmount').value = amount;
            this.updateTokenAmount();
        },
        
        updateTokenAmount: function() {
            const kasAmount = parseFloat(document.getElementById('kasAmount').value) || 0;
            const tokenAmount = kasAmount / this.tokenPrice;
            document.getElementById('tokenAmount').value = Math.floor(tokenAmount);
            
            const usdAmount = kasAmount * this.kasToUsd;
            const inputAddon = document.querySelector('.input-addon');
            if (inputAddon) {
                inputAddon.textContent = `$${usdAmount.toFixed(2)} USD`;
            }
        },
        
        executeTrade: function() {
            const kasAmount = parseFloat(document.getElementById('kasAmount').value) || 0;
            if (kasAmount <= 0) {
                this.modals.alert(
                    'Invalid Amount',
                    'Please enter a valid amount to trade.',
                    'error'
                );
                return;
            }
            
            const action = this.currentTradeMode === 'buy' ? 'Buy' : 'Sell';
            const actionColor = this.currentTradeMode === 'buy' ? '#4CAF50' : '#FF5252';
            const tokenAmount = document.getElementById('tokenAmount').value;
            
            this.modals.confirm(
                `<i class="fas fa-exchange-alt"></i> Confirm ${action} Order`,
                `<div style="text-align: center; padding: 1rem;">
                    <div style="font-size: 1.2rem; margin-bottom: 1rem;">
                        <strong style="color: ${actionColor}">${action}</strong>
                        <span style="color: #20B2AA; font-weight: bold;">${this.formatNumber(tokenAmount)} $${this.tokenSymbol}</span>
                    </div>
                    <div style="font-size: 1rem; color: #AAA;">
                        for <span style="color: #FFD700; font-weight: bold;">${this.formatNumber(kasAmount)} KAS</span>
                    </div>
                    <div style="margin-top: 1rem; padding: 0.75rem; background: rgba(32, 178, 170, 0.1);
                                border: 1px solid rgba(32, 178, 170, 0.3); border-radius: 8px;">
                        <small style="color: #999;">Rate: 1 KAS = ${(tokenAmount/kasAmount).toFixed(4)} $${this.tokenSymbol}</small>
                    </div>
                </div>`,
                function() {
                    console.log(`Executing ${action} order:`, {tokens: tokenAmount, kas: kasAmount});
                    TokenDetail.modals.alert(
                        'Trade Submitted',
                        `Your ${action.toLowerCase()} order has been submitted successfully!`,
                        'success'
                    );
                },
                function() {
                    console.log('Trade cancelled');
                }
            );
        },
        
        // Chat functions
        sendMessage: async function() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Prepare request body
            const requestBody = {
                message: message,
                message_type: 'regular'
            };
            
            // Include reply_to_id if replying
            if (this.chatState.replyingTo) {
                requestBody.reply_to_id = this.chatState.replyingTo.id;
            }
            
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/messages`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    // Pass reply information if available
                    this.addMessageToChat(
                        data.message.user, 
                        data.message.message, 
                        false, 
                        data.message.id,
                        data.message.wallet,
                        data.message.reply_to || null
                    );
                    input.value = '';
                    
                    // Clear reply state after sending
                    if (this.chatState.replyingTo) {
                        this.clearReply();
                    }
                    
                    console.log(`💬 Message saved to database: "${message}"`);
                } else {
                    const error = await response.json();
                    this.showNotification('❌ Error', error.error || 'Failed to send message', 'error');
                }
            } catch (error) {
                console.error('Failed to send message:', error);
                this.showNotification('❌ Error', 'Failed to send message. Please try again.', 'error');
            }
        },
        
        addMessageToChat: function(user, message, isSpotlight = false, msgId = null, wallet = null, replyTo = null) {
            const messagesContainer = document.getElementById('chatMessages');
            const messageId = msgId || Date.now();
            
            const displayName = this.getUserDisplayName(user);
            const userClass = this.getUsernameClass(wallet || user);
            
            // Store message data for future reply references
            this.chatState.messagesData[messageId] = {
                user: user,
                username: displayName,
                text: message,
                wallet: wallet
            };
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${isSpotlight ? 'spotlight-in-chat' : ''}`;
            messageDiv.setAttribute('data-message-id', messageId);
            
            // Build reply reference if this message is a reply
            let replyReferenceHTML = '';
            if (replyTo) {
                replyReferenceHTML = `
                    <div class="reply-reference">
                        <i class="fas fa-reply"></i>
                        <span>Replying to <strong>@${replyTo.user}</strong>: ${replyTo.text}</span>
                    </div>
                `;
            }
            
            // Check if current user is token owner
            const userWallet = localStorage.getItem('connectedWallet');
            const isTokenOwner = userWallet && window.tokenCreatorAddress && 
                userWallet.toLowerCase() === window.tokenCreatorAddress.toLowerCase();
            
            // Add delete button for token owners
            let deleteButtonHTML = '';
            if (isTokenOwner) {
                deleteButtonHTML = `
                    <button class="message-action delete-btn" onclick="TokenDetail.deleteMessage(${messageId})" title="Delete this message">
                        <i class="fas fa-trash"></i>
                    </button>
                `;
            }
            
            // Get love count from state (loaded from database) or default to 0
            const loveCount = this.chatState.messageLoves[messageId] || 0;
            const isLoved = this.chatState.userLoves.includes(messageId);
            
            messageDiv.innerHTML = `
                ${replyReferenceHTML}
                <div class="message-content">
                    <span class="chat-user ${userClass} ${isSpotlight ? 'spotlight-user' : ''}">${displayName}:</span>
                    <span class="chat-text">${message} ${isSpotlight ? '✨' : ''}</span>
                </div>
                <div class="message-actions">
                    <button class="message-action love-btn ${isLoved ? 'active' : ''}" onclick="TokenDetail.toggleLove(${messageId})" title="Love this message">
                        <i class="fas fa-heart"></i>
                        <span class="love-count">${loveCount}</span>
                    </button>
                    <button class="message-action reply-btn" onclick="TokenDetail.replyToMessage(${messageId})" title="Reply to this message">
                        <i class="fas fa-reply"></i>
                    </button>
                    ${deleteButtonHTML}
                </div>
            `;
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            
            // Only set love count if not already set (for new messages)
            if (this.chatState.messageLoves[messageId] === undefined) {
                this.chatState.messageLoves[messageId] = 0;
            }
        },
        
        getUserDisplayName: function(user) {
            if (user === 'You') {
                const savedUsername = localStorage.getItem('username');
                if (savedUsername) {
                    return savedUsername;
                } else {
                    return '...' + Math.random().toString(36).substr(-6).toUpperCase();
                }
            }
            return user;
        },
        
        getUsernameClass: function(walletOrUser) {
            if (walletOrUser === 'You') {
                const savedUsername = localStorage.getItem('username');
                return savedUsername ? 'verified-user' : 'wallet-user';
            }
            
            if (walletOrUser && walletOrUser.startsWith('0x')) {
                return 'verified-user';
            }
            
            if (walletOrUser && (walletOrUser.startsWith('...') || /^[a-f0-9]{6}$/i.test(walletOrUser))) {
                return 'wallet-user';
            }
            
            return 'verified-user';
        },
        
        // Additional chat functions to be exposed globally
        toggleLove: async function(messageId) {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (!messageEl) return;
            
            const loveBtn = messageEl.querySelector('.love-btn');
            const heartIcon = loveBtn.querySelector('i');
            const loveCountEl = loveBtn.querySelector('.love-count');
            
            // Check if already loved by this user
            const isLoved = this.chatState.userLoves.includes(messageId);
            
            try {
                const apiUrl = `/api/token/${window.tokenContractAddress}/message/${messageId}/react`;
                console.log('Calling love API:', apiUrl);
                
                // Make API call
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Wallet-Address': localStorage.getItem('connectedWallet')
                    },
                    body: JSON.stringify({
                        reaction_type: 'love'
                    })
                });
                
                if (response.ok) {
                    // Toggle love state
                    if (isLoved) {
                        // Remove from loved messages
                        this.chatState.userLoves = this.chatState.userLoves.filter(id => id !== messageId);
                        heartIcon.classList.remove('fas');
                        heartIcon.classList.add('far');
                        loveBtn.classList.remove('loved');
                        this.chatState.messageLoves[messageId] = Math.max(0, (this.chatState.messageLoves[messageId] || 1) - 1);
                    } else {
                        // Add to loved messages
                        this.chatState.userLoves.push(messageId);
                        heartIcon.classList.remove('far');
                        heartIcon.classList.add('fas');
                        loveBtn.classList.add('loved', 'heartPulse');
                        this.chatState.messageLoves[messageId] = (this.chatState.messageLoves[messageId] || 0) + 1;
                        
                        // Remove animation after it completes
                        setTimeout(() => {
                            loveBtn.classList.remove('heartPulse');
                        }, 600);
                    }
                    
                    // Update love count display
                    loveCountEl.textContent = this.chatState.messageLoves[messageId] || 0;
                    
                    // Save state
                    this.saveChatState();
                    
                    console.log(`❤️ ${isLoved ? 'Unloved' : 'Loved'} message ${messageId}`);
                } else {
                    console.error('Failed to toggle love:', await response.text());
                    this.showNotification('❌ Error', 'Failed to react to message', 'error');
                }
            } catch (error) {
                console.error('Error toggling love:', error);
                this.showNotification('❌ Error', 'Failed to react to message', 'error');
            }
        },
        
        replyToMessage: function(messageId) {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (!messageEl) return;
            
            // Get message details
            const userEl = messageEl.querySelector('.chat-user');
            const textEl = messageEl.querySelector('.chat-text');
            const username = userEl ? userEl.textContent.replace(':', '') : 'Unknown';
            const messageText = textEl ? textEl.textContent.substring(0, 50) : '';
            
            // Clear any existing reply indicator
            this.clearReply();
            
            // Store reply state with full message text for sending to backend
            const fullText = textEl ? textEl.textContent.replace('✨', '').trim() : '';
            this.chatState.replyingTo = {
                id: messageId,
                username: username,
                text: fullText.substring(0, 100) + (fullText.length > 100 ? '...' : '')
            };
            
            // Add visual indicator to the message being replied to
            messageEl.classList.add('reply-target');
            
            // Create reply indicator above chat input
            const chatInputContainer = document.querySelector('.chat-input-container');
            const replyIndicator = document.createElement('div');
            replyIndicator.className = 'reply-indicator';
            replyIndicator.id = 'replyIndicator';
            replyIndicator.innerHTML = `
                <div class="reply-info">
                    <i class="fas fa-reply"></i>
                    <span>Replying to <strong>${username}</strong>: ${messageText}${messageText.length >= 50 ? '...' : ''}</span>
                </div>
                <button class="cancel-reply" onclick="TokenDetail.clearReply()">
                    <i class="fas fa-times"></i>
                </button>
            `;
            
            chatInputContainer.parentNode.insertBefore(replyIndicator, chatInputContainer);
            
            // Focus the input
            document.getElementById('chatInput').focus();
            
            console.log(`↩️ Replying to message ${messageId} from ${username}`);
        },
        
        clearReply: function() {
            // Remove reply indicator
            const replyIndicator = document.getElementById('replyIndicator');
            if (replyIndicator) {
                replyIndicator.remove();
            }
            
            // Remove visual indicator from message
            const replyTarget = document.querySelector('.reply-target');
            if (replyTarget) {
                replyTarget.classList.remove('reply-target');
            }
            
            // Clear reply state
            this.chatState.replyingTo = null;
        },
        
        deleteMessage: async function(messageId) {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (!messageEl) return;
            
            // Get message details for confirmation
            const textEl = messageEl.querySelector('.chat-text');
            const messageText = textEl ? textEl.textContent.substring(0, 50) : '';
            
            // Show confirmation modal
            this.modals.confirm(
                '<i class="fas fa-exclamation-triangle" style="color: #FF5252;"></i> Delete Message',
                `<div style="padding: 0.5rem;">
                    <p style="color: #CCC; margin-bottom: 1rem;">Are you sure you want to delete this message?</p>
                    <div style="background: rgba(255, 82, 82, 0.1); border: 1px solid rgba(255, 82, 82, 0.3); 
                                border-radius: 8px; padding: 0.75rem; margin-bottom: 1rem;">
                        <p style="color: #AAA; margin: 0; font-style: italic;">"${messageText}${messageText.length >= 50 ? '...' : ''}"</p>
                    </div>
                    <p style="color: #999; font-size: 0.9rem; margin: 0;">
                        <i class="fas fa-info-circle"></i> This action cannot be undone.
                    </p>
                </div>`,
                async () => {
                    // User confirmed deletion
                    try {
                        const response = await fetch(`/api/token/${window.tokenContractAddress}/message/${messageId}`, {
                            method: 'DELETE',
                            headers: {
                                'X-Wallet-Address': localStorage.getItem('connectedWallet')
                            }
                        });
                        
                        if (response.ok) {
                            // Remove message from UI with animation
                            messageEl.style.transition = 'all 0.3s ease';
                            messageEl.style.opacity = '0';
                            messageEl.style.transform = 'translateX(-20px)';
                            
                            setTimeout(() => {
                                messageEl.remove();
                            }, 300);
                            
                            // Remove from chat state
                            delete this.chatState.messagesData[messageId];
                            delete this.chatState.messageLoves[messageId];
                            this.chatState.userLoves = this.chatState.userLoves.filter(id => id !== messageId);
                            
                            this.modals.showNotification('Message Deleted', 'The message has been removed successfully.', 'success');
                            console.log(`🗑️ Deleted message ${messageId}`);
                        } else {
                            const error = await response.json();
                            this.modals.showNotification('Delete Failed', error.error || 'Failed to delete message', 'error');
                        }
                    } catch (error) {
                        console.error('Error deleting message:', error);
                        this.modals.showNotification('Error', 'Failed to delete message. Please try again.', 'error');
                    }
                },
                () => {
                    // User cancelled deletion
                    console.log('Message deletion cancelled');
                }
            );
        },
        
        toggleTokenGate: function() {
            console.log('🔒 Toggle token gate');
            // Implementation here
        },
        
        openChatSettings: function() {
            console.log('🔧 Opening chat settings...');
            console.log('🔧 Token type:', this.isProToken ? 'pro' : 'basic', 'Is Pro:', this.isProToken);
            
            // Different settings for pro vs basic tokens
            if (this.isProToken) {
                // Pro Token Settings Modal - includes treasury management
                const modalHtml = `
                    <div id="chatSettingsModal" class="modal" style="display: flex;">
                        <div class="modal-content chat-settings-modal">
                            <div class="modal-header">
                                <h3><i class="fas fa-crown"></i> Pro Token Settings</h3>
                                <button class="modal-close" onclick="TokenDetail.closeChatSettings()">&times;</button>
                            </div>
                            <div class="modal-body">
                                <div class="settings-section">
                                    <h4><i class="fas fa-coins"></i> Treasury Management</h4>
                                    <p>Configure how treasury funds are distributed to active community members.</p>
                                    
                                    <div class="form-group">
                                        <label>Daily Reward Pool</label>
                                        <input type="number" class="form-control" value="1000" placeholder="Tokens per day">
                                        <small class="setting-hint">Tokens distributed daily from treasury</small>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Airdrop Threshold</label>
                                        <input type="number" class="form-control" value="100000" placeholder="Market cap for airdrops">
                                        <small class="setting-hint">Market cap milestone for community airdrops</small>
                                    </div>
                                </div>
                                
                                <div class="settings-section">
                                    <h4><i class="fas fa-shield-alt"></i> Chat Access Control</h4>
                                    
                                    <div class="form-check" style="margin-bottom: 1.5rem;">
                                        <input type="checkbox" id="holdersOnlyChat" ${this.tokenSettings.holdersOnlyChat ? 'checked' : ''}>
                                        <label for="holdersOnlyChat">Holders-only chat</label>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens to chat</label>
                                        <input type="number" class="form-control" id="minTokensToChat" value="${this.tokenSettings.minTokensToChat || 0}">
                                        <small class="setting-hint">Minimum balance required to chat</small>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Spotlight threshold</label>
                                        <input type="number" class="form-control" id="minTokensForSpotlight" value="${this.tokenSettings.minTokensForSpotlight || 500}">
                                        <small class="setting-hint">Tokens needed for spotlight messages</small>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" onclick="TokenDetail.closeChatSettings()">Cancel</button>
                                <button type="button" class="btn btn-primary" onclick="TokenDetail.saveChatSettings()">Save Settings</button>
                            </div>
                        </div>
                    </div>
                `;
                
                // Add modal to page if not already present
                if (!document.getElementById('chatSettingsModal')) {
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                }
                
                document.getElementById('chatSettingsModal').style.display = 'flex';
            } else {
                // Basic Token Settings - simple chat controls only
                const modalHtml = `
                    <div id="chatSettingsModal" class="modal" style="display: flex;">
                        <div class="modal-content chat-settings-modal">
                            <div class="modal-header">
                                <h3><i class="fas fa-cog"></i> Chat Settings</h3>
                                <button class="modal-close" onclick="TokenDetail.closeChatSettings()">&times;</button>
                            </div>
                            <div class="modal-body">
                                <div class="settings-section">
                                    <h4><i class="fas fa-shield-alt"></i> Chat Access Control</h4>
                                    
                                    <div class="form-check" style="margin-bottom: 1.5rem;">
                                        <input type="checkbox" id="holdersOnlyChat" ${this.tokenSettings.holdersOnlyChat ? 'checked' : ''}>
                                        <label for="holdersOnlyChat">Holders-only chat</label>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens to chat</label>
                                        <input type="number" class="form-control" id="minTokensToChat" value="${this.tokenSettings.minTokensToChat || 0}">
                                        <small class="setting-hint">Minimum balance required to chat</small>
                                    </div>
                                </div>
                                
                                <div class="basic-token-note">
                                    <i class="fas fa-info-circle"></i>
                                    <p>Basic tokens have limited features. Create a Pro token with treasury allocation to unlock rewards, airdrops, and advanced community management.</p>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" onclick="TokenDetail.closeChatSettings()">Cancel</button>
                                <button type="button" class="btn btn-primary" onclick="TokenDetail.saveChatSettings()">Save Settings</button>
                            </div>
                        </div>
                    </div>
                `;
                
                // Add modal to page if not already present  
                if (!document.getElementById('chatSettingsModal')) {
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                }
                
                document.getElementById('chatSettingsModal').style.display = 'flex';
            }
            
            console.log('🔧 Chat settings modal opened successfully');
        },
        
        closeChatSettings: function() {
            const modal = document.getElementById('chatSettingsModal');
            if (modal) {
                modal.style.display = 'none';
            }
            console.log('🔧 Settings modal closed');
        },
        
        saveChatSettings: function() {
            // Save settings logic
            const holdersOnly = document.getElementById('holdersOnlyChat').checked;
            const minTokens = document.getElementById('minTokensToChat').value;
            
            this.tokenSettings.holdersOnlyChat = holdersOnly;
            this.tokenSettings.minTokensToChat = parseInt(minTokens) || 0;
            
            if (this.isProToken) {
                // Save additional pro token settings
                const spotlightThreshold = document.getElementById('minTokensForSpotlight').value;
                this.tokenSettings.minTokensForSpotlight = parseInt(spotlightThreshold) || 500;
            }
            
            console.log('💾 Saving chat settings:', this.tokenSettings);
            
            // TODO: Send settings to server via API
            
            this.closeChatSettings();
            this.showNotification('Settings Saved', 'Chat settings have been updated successfully.', 'success');
        },
        
        showNotification: function(title, message, type = 'info') {
            const modal = document.getElementById('notificationModal');
            const modalTitle = document.getElementById('notificationTitle');
            const modalMessage = document.getElementById('notificationMessage');
            const modalContent = modal.querySelector('.modal-content');
            
            modalTitle.textContent = title;
            modalMessage.textContent = message;
            
            modalContent.className = `modal-content notification-modal ${type}`;
            
            modal.style.display = 'flex';
        },
        
        // Poll and spotlight functions
        addPollToChat: function(poll) {
            console.log('📊 Adding poll to chat:', poll);
            // Implementation here
        },
        
        updateSpotlightDisplay: function(spotlight) {
            console.log('✨ Updating spotlight display:', spotlight);
            
            // Use existing spotlight container from template (no need to create dynamically)
            const spotlightContainer = document.getElementById('spotlightMessages');
            const listContainer = document.getElementById('spotlightMessagesList');
            if (!listContainer || !spotlightContainer) return;
            
            // Show the spotlight container when adding messages
            spotlightContainer.style.display = 'block';
            
            // Create spotlight message element with yellow theme and countdown
            const spotlightDiv = document.createElement('div');
            spotlightDiv.className = 'spotlight-message-item';
            spotlightDiv.setAttribute('data-spotlight-id', spotlight.id);
            spotlightDiv.style.cssText = `
                background: rgba(255, 255, 255, 0.8);
                border: 1px solid #FFC107;
                border-radius: 8px;
                padding: 0.75rem;
                margin-bottom: 0.5rem;
                position: relative;
                animation: pulseGlow 2s ease-in-out infinite;
            `;
            
            const timeRemaining = Math.max(0, Math.floor((spotlight.expiresAt - Date.now()) / 1000 / 60));
            
            spotlightDiv.innerHTML = `
                <div style="display: flex; align-items: start; gap: 0.75rem;">
                    <div class="spotlight-icon" style="font-size: 1.5rem;">✨</div>
                    <div class="spotlight-content" style="flex: 1;">
                        <div class="spotlight-user" style="
                            font-weight: 600;
                            color: #856404;
                            margin-bottom: 0.25rem;
                        ">${spotlight.user}</div>
                        <div class="spotlight-text" style="
                            color: #333;
                            font-size: 1rem;
                            line-height: 1.4;
                        ">${spotlight.message}</div>
                        <div class="spotlight-time" style="
                            display: flex;
                            align-items: center;
                            gap: 0.5rem;
                            margin-top: 0.5rem;
                            color: #856404;
                            font-size: 0.85rem;
                        ">
                            <i class="fas fa-clock" style="color: #FFC107;"></i>
                            <span id="spotlight-timer-${spotlight.id}">${timeRemaining} minutes remaining</span>
                        </div>
                    </div>
                </div>
            `;
            
            // Add to the list
            listContainer.appendChild(spotlightDiv);
            
            // Update timer every minute
            const timerId = setInterval(() => {
                const remaining = Math.max(0, Math.floor((spotlight.expiresAt - Date.now()) / 1000 / 60));
                const timerElement = document.getElementById(`spotlight-timer-${spotlight.id}`);
                if (timerElement) {
                    if (remaining > 0) {
                        timerElement.textContent = `${remaining} minutes remaining`;
                    } else {
                        timerElement.innerHTML = '<span style="color: #dc3545;">Expiring...</span>';
                        clearInterval(timerId);
                    }
                }
            }, 60000); // Update every minute
            
            // Spotlight messages stay ONLY in the spotlight panel, not in regular chat
            
            // Remove after expiration
            setTimeout(() => {
                const element = document.querySelector(`[data-spotlight-id="${spotlight.id}"]`);
                if (element) {
                    element.style.animation = 'fadeOut 0.5s ease';
                    setTimeout(() => element.remove(), 500);
                }
            }, timeRemaining * 60 * 1000);
        },
        
        // Create spotlight message
        createSpotlight: async function() {
            const requiredTokens = this.tokenSettings.minTokensForSpotlight || 500;
            const userWallet = localStorage.getItem('connectedWallet');
            
            if (!userWallet) {
                this.showNotification('🔗 Wallet Required', 'Please connect your wallet to create spotlight messages', 'error');
                return;
            }
            
            // Check ACTUAL token holdings from server (NOT localStorage fake balance)
            try {
                const holdingsResponse = await fetch(`/api/token/${window.tokenContractAddress}/holdings`, {
                    headers: {
                        'X-Wallet-Address': userWallet
                    }
                });
                
                if (!holdingsResponse.ok) {
                    throw new Error('Failed to check token holdings');
                }
                
                const holdingsData = await holdingsResponse.json();
                const actualBalance = holdingsData.balance || 0;
                
                // TOKEN GATE CHECK - User must HOLD tokens, not spend them!
                if (actualBalance < requiredTokens) {
                    this.showNotification('🔐 Token Gate', `You need to HOLD at least ${requiredTokens.toLocaleString()} $${this.tokenSymbol} tokens to create spotlight messages (You hold: ${actualBalance.toLocaleString()})`, 'error');
                    return;
                }
            } catch (error) {
                console.error('Failed to verify token holdings:', error);
                this.showNotification('❌ Error', 'Failed to verify token holdings', 'error');
                return;
            }
            
            // Show spotlight message input modal
            const modalHTML = `
                <div id="spotlightModal" class="modal" style="display: flex;">
                    <div class="modal-content" style="max-width: 550px;">
                        <div class="modal-header">
                            <h3><i class="fas fa-star" style="color: #FFD700;"></i> Create Spotlight Message</h3>
                            <button class="modal-close" onclick="TokenDetail.modals.closeModal('spotlightModal')">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div style="padding: 1rem; background: linear-gradient(135deg, rgba(255, 215, 0, 0.1), rgba(255, 215, 0, 0.05));
                                        border: 1px solid rgba(255, 215, 0, 0.3); border-radius: 8px; margin-bottom: 1rem;">
                                <div style="display: flex; align-items: center; gap: 0.5rem; color: #FFD700; font-weight: 600; margin-bottom: 0.5rem;">
                                    <i class="fas fa-shield-alt"></i>
                                    <span>Token Gate Active</span>
                                </div>
                                <div style="color: #AAA; font-size: 0.9rem;">
                                    Required: Hold <strong style="color: #20B2AA;">${requiredTokens} $${this.tokenSymbol}</strong> tokens
                                </div>
                                <div style="color: #999; font-size: 0.85rem; margin-top: 0.5rem;">
                                    Your message will be pinned for 1 hour
                                </div>
                            </div>
                            
                            <label style="color: #20B2AA; font-weight: 600; display: block; margin-bottom: 0.5rem;">
                                Your Spotlight Message
                            </label>
                            <textarea id="spotlightMessageInput" 
                                      placeholder="Enter your message to be spotlighted..."
                                      maxlength="280"
                                      style="width: 100%; min-height: 100px; padding: 0.75rem;
                                             background: linear-gradient(135deg, rgba(0, 0, 0, 0.4), rgba(20, 20, 30, 0.3));
                                             border: 1px solid rgba(32, 178, 170, 0.3); border-radius: 10px;
                                             color: #FFF; resize: vertical; font-family: inherit;"></textarea>
                            <div style="text-align: right; margin-top: 0.5rem;">
                                <small style="color: #999;">
                                    <span id="spotlightCharCount">0</span>/280 characters
                                </small>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="TokenDetail.modals.closeModal('spotlightModal')">
                                <i class="fas fa-times"></i> Cancel
                            </button>
                            <button type="button" class="btn btn-primary" id="submitSpotlightBtn">
                                <i class="fas fa-star"></i> Create Spotlight
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            const existingModal = document.getElementById('spotlightModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            const textarea = document.getElementById('spotlightMessageInput');
            const charCount = document.getElementById('spotlightCharCount');
            textarea.addEventListener('input', function() {
                charCount.textContent = textarea.value.length;
            });
            
            const self = this;
            document.getElementById('submitSpotlightBtn').onclick = async function() {
                const message = document.getElementById('spotlightMessageInput').value;
                
                if (!message || message.trim() === '') {
                    self.modals.alert(
                        'Empty Message',
                        'Please enter a message to spotlight.',
                        'error'
                    );
                    return;
                }
                
                self.modals.closeModal('spotlightModal');
                
                // Continue with the spotlight creation
                await self.submitSpotlightMessage(message);
            };
            
            setTimeout(() => textarea.focus(), 100);
            return;
        },
        
        // Submit spotlight message (separated from modal)
        submitSpotlightMessage: async function(message) {
            const requiredTokens = this.tokenSettings.minTokensForSpotlight || 500;
            
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/spotlight`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Wallet-Address': localStorage.getItem('connectedWallet')
                    },
                    body: JSON.stringify({ message })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    // NO TOKEN DEDUCTION! This is TOKEN GATED, not a cost!
                    // Users must HOLD tokens, not spend them
                    
                    // Update display with yellow pinned message at top
                    this.updateSpotlightDisplay({
                        id: data.spotlight.id,
                        user: data.spotlight.user,
                        message: data.spotlight.message,
                        wallet: data.spotlight.wallet,
                        expiresAt: Date.now() + (60 * 60 * 1000) // 1 hour
                    });
                    
                    this.showNotification('✨ Spotlight Created!', `Your message is now pinned for 1 hour! (Token gated: ${requiredTokens.toLocaleString()} $${this.tokenSymbol} holding required)`, 'success');
                } else {
                    const error = await response.json();
                    this.showNotification('❌ Error', error.error || 'Failed to create spotlight', 'error');
                }
            } catch (error) {
                console.error('Failed to create spotlight:', error);
                this.showNotification('❌ Error', 'Failed to create spotlight message', 'error');
            }
        }
    };
    
    // Expose the module to global scope for HTML event handlers
    window.TokenDetail = TokenDetail;
    
    // Initialize event listeners when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        // Chart.js initialization
        if (window.Chart && document.getElementById('tokenChart')) {
            setTimeout(() => TokenDetail.initChart(), 100);
        }
        
        // Chart type toggle buttons
        document.querySelectorAll('.chart-type-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.chart-type-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                TokenDetail.currentChartType = this.getAttribute('data-type');
                TokenDetail.initChart();
            });
        });
        
        // Trading input listener
        const kasAmountInput = document.getElementById('kasAmount');
        if (kasAmountInput) {
            kasAmountInput.addEventListener('input', () => TokenDetail.updateTokenAmount());
        }
        
        // Chat enter key
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    TokenDetail.sendMessage();
                }
            });
        }
    });
    
    // Additional global functions for HTML event handlers
    window.setTradeMode = function(mode) { TokenDetail.setTradeMode(mode); };
    window.setQuickAmount = function(amount) { TokenDetail.setQuickAmount(amount); };
    window.executeTrade = function() { TokenDetail.executeTrade(); };
    window.sendMessage = function() { TokenDetail.sendMessage(); };
    window.openChatSettings = function() { TokenDetail.openChatSettings(); };
    window.copyContractAddress = function(address) {
        navigator.clipboard.writeText(address).then(() => {
            TokenDetail.modals.alert(
                'Copied!',
                'Contract address has been copied to clipboard.',
                'success'
            );
        });
    };
    window.zoomChart = function(direction) {
        // Implement zoom functionality
        console.log('Zoom chart:', direction);
    };
    window.resetChart = function() {
        TokenDetail.initChart();
    };
    window.createSpotlight = function() {
        TokenDetail.createSpotlight();
    };
    
    // Toggle functions for collapsible sections
    window.toggleLeaderboard = function() {
        const content = document.getElementById('leaderboardContent');
        const toggle = document.querySelector('.leaderboard-toggle i');
        if (content && toggle) {
            content.classList.toggle('collapsed');
            toggle.style.transform = content.classList.contains('collapsed') ? 'rotate(0deg)' : 'rotate(180deg)';
        }
    };
    
    window.toggleAchievements = function() {
        const content = document.getElementById('achievementContent');
        const toggle = document.querySelector('.achievement-toggle i');
        if (content && toggle) {
            content.classList.toggle('collapsed');
            toggle.style.transform = content.classList.contains('collapsed') ? 'rotate(0deg)' : 'rotate(180deg)';
        }
    };
    
})(window, document);