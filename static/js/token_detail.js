// Token Detail Page JavaScript Module
// Using IIFE (Immediately Invoked Function Expression) to avoid global scope pollution
(function(window, document) {
    'use strict';

    // Module-scoped variables - avoid global pollution
    const TokenDetail = {
        // CSRF Token Helper
        getCsrfToken: function() {
            const meta = document.querySelector('meta[name="csrf-token"]');
            return meta ? meta.getAttribute('content') : '';
        },
        
        // Trading state
        currentTradeMode: 'buy',
        tokenPrice: null,
        marketCap: null,
        kasToUsd: 0.15, // Will be updated from oracle
        tokenSymbol: null,
        tokenName: null,
        isProToken: false,
        
        // Chart state
        currentChartType: 'marketcap',
        currentInterval: '1h',  // Default to 1H candles like trading platforms
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
        
        // Quote management - M-2 FIX: AbortController for request cancellation
        quoteTimeout: null,
        quoteAbortController: null,
        
        // Graduation polling interval
        graduationPollingInterval: null,
        
        // Initialize the module with data from server
        init: function(config) {
            this.tokenPrice = config.tokenPrice;
            this.marketCap = config.marketCap;
            this.tokenSymbol = config.tokenSymbol;
            this.tokenName = config.tokenName;
            this.isProToken = config.isProToken || false;
            this.kasToUsd = config.kasPrice || 0.15; // Use server-provided KAS price (cached for 5 min)
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
            
            // Initialize graduation status polling
            this.fetchGraduationStatus();
            
            // Clear existing interval if any
            if (this.graduationPollingInterval) {
                clearInterval(this.graduationPollingInterval);
            }
            
            // Poll graduation status every 30 seconds
            this.graduationPollingInterval = setInterval(() => {
                this.fetchGraduationStatus();
            }, 30000);
            
            // Cleanup on page unload
            window.addEventListener('beforeunload', () => {
                if (this.graduationPollingInterval) {
                    clearInterval(this.graduationPollingInterval);
                }
            });
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
                    
                    const spotlightContainer = document.getElementById('spotlightMessages');
                    const listContainer = document.getElementById('spotlightMessagesList');
                    
                    // Clear existing spotlight messages
                    if (listContainer) {
                        listContainer.innerHTML = '';
                    }
                    
                    // Process and display spotlight messages
                    if (data.spotlights && data.spotlights.length > 0 && spotlightContainer && listContainer) {
                        // Add each spotlight message
                        data.spotlights.forEach(spotlight => {
                            // Use the expires_at_ms directly from backend (already in milliseconds)
                            const expiresAt = spotlight.expires_at_ms || 
                                new Date(spotlight.created_at).getTime() + (60 * 60 * 1000);
                            
                            const spotlightEntry = {
                                id: spotlight.id,
                                user: spotlight.user,
                                message: spotlight.message,
                                expiresAt: expiresAt
                            };
                            // Add the message content only (don't control visibility here)
                            this.addSpotlightMessage(spotlightEntry);
                            console.log('✨ Added spotlight to display:', spotlightEntry);
                        });
                        
                        // Show the container after adding all messages
                        spotlightContainer.style.display = 'block';
                        console.log('✨ Spotlight container shown with messages');
                    } else if (spotlightContainer) {
                        // Hide container if no spotlights
                        spotlightContainer.style.display = 'none';
                        console.log('✨ No spotlight messages - container hidden');
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
        
        // Fetch real chart data from blockchain trade history with candlestick support
        fetchChartData: async function(type, interval = '1h') {
            try {
                // Calculate appropriate timeframe based on interval (like real trading platforms)
                const timeframeMap = {
                    '5m': '6h',    // 5min candles: show last 6 hours
                    '15m': '24h',  // 15min candles: show last 24 hours
                    '1h': '7d',    // 1hour candles: show last 7 days
                    '4h': '30d',   // 4hour candles: show last 30 days
                    '1d': '90d'    // 1day candles: show last 90 days
                };
                const timeframe = timeframeMap[interval] || '7d';
                
                let url = `/api/token/${window.tokenContractAddress}/chart-data?timeframe=${timeframe}&interval=${interval}`;
                
                const response = await fetch(url);
                const result = await response.json();
                
                if (!result.success || !result.data || result.data.length === 0) {
                    // No trade data available, return error
                    return { error: 'No data available', format: 'area' };
                }
                
                return {
                    data: result.data,
                    format: result.format,
                    interval: result.interval,
                    timeframe: result.timeframe
                };
                
            } catch (error) {
                console.error('Error fetching chart data:', error);
                return { error: error.message, format: 'area' };
            }
        },
        
        // Initialize TradingView Lightweight Charts with candlestick support
        initChart: async function() {
            const container = document.getElementById('tradingview_chart');
            if (!container) return;
            
            // Remove existing chart if it exists
            if (this.myChart) {
                this.myChart.remove();
                this.myChart = null;
            }
            
            // Clear container
            container.innerHTML = '';
            
            const chartResult = await this.fetchChartData(this.currentChartType, this.currentInterval);
            const self = this;
            
            // Create chart with teal theme
            this.myChart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    textColor: '#888',
                },
                grid: {
                    vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                    horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {
                        color: 'rgba(32, 178, 170, 0.5)',
                        width: 1,
                        style: LightweightCharts.LineStyle.Dashed,
                    },
                    horzLine: {
                        color: 'rgba(32, 178, 170, 0.5)',
                        width: 1,
                        style: LightweightCharts.LineStyle.Dashed,
                    },
                },
                rightPriceScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                },
                timeScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });
            
            // Handle error case
            if (chartResult.error) {
                console.log('No chart data available:', chartResult.error);
                const fallbackValue = this.currentChartType === 'marketcap' ? this.marketCap : this.tokenPrice;
                const areaSeries = this.myChart.addAreaSeries({
                    lineColor: '#20B2AA',
                    topColor: 'rgba(32, 178, 170, 0.4)',
                    bottomColor: 'rgba(32, 178, 170, 0.0)',
                    lineWidth: 2,
                });
                areaSeries.setData([{
                    time: Math.floor(Date.now() / 1000),
                    value: fallbackValue || 0
                }]);
                this.myChart.timeScale().fitContent();
                return;
            }
            
            // Choose series type based on format
            let series;
            if (chartResult.format === 'candlestick') {
                // Candlestick chart with teal colors
                series = this.myChart.addCandlestickSeries({
                    upColor: '#20B2AA',
                    downColor: '#FF6B6B',
                    borderVisible: false,
                    wickUpColor: '#20B2AA',
                    wickDownColor: '#FF6B6B',
                    priceFormat: {
                        type: 'custom',
                        formatter: (price) => {
                            if (self.currentChartType === 'marketcap') {
                                return '$' + self.formatNumber(price, true);
                            } else {
                                return price.toFixed(6) + ' KAS';
                            }
                        },
                    },
                });
                
                // Convert OHLC data to TradingView format
                const tvData = chartResult.data.map(candle => ({
                    time: candle.time,
                    open: candle.open,
                    high: candle.high,
                    low: candle.low,
                    close: candle.close
                }));
                
                series.setData(tvData);
                
            } else {
                // Area chart (fallback for low trade count)
                series = this.myChart.addAreaSeries({
                    lineColor: '#20B2AA',
                    topColor: 'rgba(32, 178, 170, 0.4)',
                    bottomColor: 'rgba(32, 178, 170, 0.0)',
                    lineWidth: 2,
                    priceFormat: {
                        type: 'custom',
                        formatter: (price) => {
                            if (self.currentChartType === 'marketcap') {
                                return '$' + self.formatNumber(price, true);
                            } else {
                                return price.toFixed(6) + ' KAS';
                            }
                        },
                    },
                });
                
                // Convert area data to TradingView format
                const tvData = chartResult.data.map(point => ({
                    time: point.time,
                    value: point.value
                }));
                
                series.setData(tvData);
            }
            
            // Fit content to view
            this.myChart.timeScale().fitContent();
            
            // Handle window resize
            const resizeObserver = new ResizeObserver(entries => {
                if (this.myChart && entries.length > 0) {
                    const { width, height } = entries[0].contentRect;
                    this.myChart.applyOptions({ width, height });
                }
            });
            resizeObserver.observe(container);
        },
        
        // Trading functions
        setTradeMode: function(mode) {
            this.currentTradeMode = mode;
            
            // Update tab styling
            document.querySelectorAll('.trade-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelector(`.trade-tab.${mode}`).classList.add('active');
            
            // ⚠️ M-10 FIX: Update field readonly states
            const kasAmountInput = document.getElementById('kasAmount');
            const tokenAmountInput = document.getElementById('tokenAmount');
            
            if (mode === 'buy') {
                // BUY mode: User edits KAS, tokens are output
                if (kasAmountInput) kasAmountInput.readOnly = false;
                if (tokenAmountInput) tokenAmountInput.readOnly = true;
            } else { // sell
                // SELL mode: User edits tokens, KAS is output
                if (kasAmountInput) kasAmountInput.readOnly = true;
                if (tokenAmountInput) tokenAmountInput.readOnly = false;
            }
            
            // Update trade button text with icon and symbol
            const tradeButton = document.getElementById('tradeButton');
            if (tradeButton) {
                const icon = mode === 'buy' ? 
                    '<i class="fas fa-rocket"></i>' : 
                    '<i class="fas fa-money-bill-wave"></i>';
                const symbol = this.tokenSymbol || 'TOKEN';
                tradeButton.innerHTML = `${icon} ${mode === 'buy' ? 'Buy' : 'Sell'} $${symbol}`;
                tradeButton.className = `trade-button ${mode}`;
            }
            
            // Clear inputs when switching modes
            if (kasAmountInput) kasAmountInput.value = '';
            if (tokenAmountInput) tokenAmountInput.value = '';
            this.clearFeeBreakdown();
        },
        
        switchTradeMode: function() {
            const newMode = this.currentTradeMode === 'buy' ? 'sell' : 'buy';
            this.setTradeMode(newMode);
        },
        
        setQuickAmount: function(amount) {
            document.getElementById('kasAmount').value = amount;
            this.updateTokenAmount();
        },
        
        // Helper functions for quote UI - Phase 3.6 Enhanced
        showQuoteLoading: function() {
            const tokenAmountInput = document.getElementById('tokenAmount');
            const kasAmountInput = document.getElementById('kasAmount');
            
            // ⚠️ FIX: Apply loading to INPUT field (what user is editing)
            if (this.currentTradeMode === 'buy') {
                // BUY mode: User edits KAS (input), tokens are output
                if (kasAmountInput) {
                    kasAmountInput.classList.add('loading');
                    kasAmountInput.disabled = true;
                }
                // Dim the output field
                if (tokenAmountInput) {
                    tokenAmountInput.style.opacity = '0.5';
                }
            } else { // sell
                // SELL mode: User edits tokens (input), KAS is output  
                if (tokenAmountInput) {
                    tokenAmountInput.classList.add('loading');
                    tokenAmountInput.disabled = true;
                }
                // Dim the output field
                if (kasAmountInput) {
                    kasAmountInput.style.opacity = '0.5';
                }
            }
            
            // Fade fee breakdown while loading
            const feeBreakdown = document.getElementById('feeBreakdown');
            if (feeBreakdown) {
                feeBreakdown.style.opacity = '0.5';
            }
        },
        
        hideQuoteLoading: function() {
            const tokenAmountInput = document.getElementById('tokenAmount');
            const kasAmountInput = document.getElementById('kasAmount');
            
            // Remove loading class from both fields
            if (tokenAmountInput) {
                tokenAmountInput.classList.remove('loading');
                tokenAmountInput.disabled = false;
                tokenAmountInput.style.opacity = '1';
            }
            if (kasAmountInput) {
                kasAmountInput.classList.remove('loading');
                kasAmountInput.disabled = false;
                kasAmountInput.style.opacity = '1';
            }
            
            // Restore fee breakdown opacity
            const feeBreakdown = document.getElementById('feeBreakdown');
            if (feeBreakdown) {
                feeBreakdown.style.opacity = '1';
            }
        },
        
        displayFeeBreakdown: function(fees) {
            // Phase 3.3 Step 2: Spec-compliant fee breakdown display
            const feeBreakdown = document.getElementById('feeBreakdown');
            if (!feeBreakdown) return;
            
            // Update Anti-Bot Fee
            const antiBotFee = fees.antiBotFee || fees.anti_bot || 0;
            const antiBotFeeDisplay = document.getElementById('antiBotFeeDisplay');
            if (antiBotFeeDisplay) {
                antiBotFeeDisplay.textContent = `${antiBotFee.toFixed(4)} KAS`;
            }
            
            // Update Platform Fee (0.9%)
            const platformFee = fees.platformFee || fees.platform || 0;
            const platformFeeDisplay = document.getElementById('platformFeeDisplay');
            if (platformFeeDisplay) {
                platformFeeDisplay.textContent = `${platformFee.toFixed(4)} KAS`;
            }
            
            // Update Creator Fee (0.1%)
            const creatorFee = fees.creatorFee || fees.creator || 0;
            const creatorFeeDisplay = document.getElementById('creatorFeeDisplay');
            if (creatorFeeDisplay) {
                creatorFeeDisplay.textContent = `${creatorFee.toFixed(4)} KAS`;
            }
            
            // Calculate and update Total Platform Fee
            const totalPlatformFee = platformFee + creatorFee + antiBotFee;
            const totalPlatformFeeDisplay = document.getElementById('totalPlatformFee');
            if (totalPlatformFeeDisplay) {
                totalPlatformFeeDisplay.textContent = `${totalPlatformFee.toFixed(4)} KAS`;
            }
            
            // Update Price Impact with color coding
            const priceImpact = fees.priceImpact || fees.price_impact_percent || 0;
            const impactColor = priceImpact > 5 ? '#FF5252' : 
                               priceImpact > 2 ? '#FFA500' : '#4CAF50';
            const priceImpactDisplay = document.getElementById('priceImpactDisplay');
            if (priceImpactDisplay) {
                priceImpactDisplay.innerHTML = `<span style="color: ${impactColor}">${priceImpact.toFixed(2)}%</span>`;
            }
            
            // Update Auto Slippage
            const slippageBps = fees.auto_slippage_bps || 50;
            const autoSlippageDisplay = document.getElementById('autoSlippageDisplay');
            if (autoSlippageDisplay) {
                autoSlippageDisplay.textContent = `${(slippageBps / 100).toFixed(2)}%`;
            }
            
            // Show breakdown
            feeBreakdown.style.display = 'block';
        },
        
        clearFeeBreakdown: function() {
            const feeBreakdown = document.getElementById('feeBreakdown');
            if (!feeBreakdown) return;
            
            // Hide breakdown
            feeBreakdown.style.display = 'none';
        },
        
        showQuoteError: function(message) {
            console.error('Quote error:', message);
            
            // Show error in fee breakdown area
            const feeBreakdown = document.getElementById('feeBreakdown');
            if (feeBreakdown) {
                feeBreakdown.innerHTML = `
                    <div class="quote-error">
                        <i class="fas fa-exclamation-triangle"></i>
                        ${message || 'Quote unavailable'}
                    </div>
                `;
                feeBreakdown.style.display = 'block';
            }
        },
        
        // PHASE 3 AUDITED IMPLEMENTATION - All 5 audit fixes applied
        updateTokenAmount: function() {
            const action = this.currentTradeMode; // 'buy' or 'sell'
            
            // ⚠️ CRITICAL FIX: Cancel previous work FIRST, before any early returns
            // This ensures stale quotes don't update UI when user clears input
            if (this.quoteAbortController) {
                this.quoteAbortController.abort();
                this.quoteAbortController = null;  // ✅ FIX 1: Reset to null after abort
            }
            clearTimeout(this.quoteTimeout);
            
            // M-9 FIX: Get appropriate input based on mode
            let params = {
                token_address: window.tokenContractAddress
            };
            
            if (action === 'buy') {
                // BUY: User enters KAS, gets token amount
                const kasAmount = parseFloat(document.getElementById('kasAmount').value) || 0;
                
                if (kasAmount <= 0) {
                    document.getElementById('tokenAmount').value = 0;
                    this.clearFeeBreakdown();
                    return;  // ✅ Now safe to return - already cancelled pending work
                }
                
                params.kas_amount = kasAmount;  // ✅ Buy needs kas_amount
                
            } else { // sell
                // SELL: User enters tokens, gets KAS amount
                const tokenAmount = parseFloat(document.getElementById('tokenAmount').value) || 0;
                
                if (tokenAmount <= 0) {
                    document.getElementById('kasAmount').value = 0;
                    this.clearFeeBreakdown();
                    return;  // ✅ Now safe to return - already cancelled pending work
                }
                
                params.token_amount = tokenAmount;  // ✅ Sell needs token_amount
            }
            
            // Create NEW AbortController for this request
            this.quoteAbortController = new AbortController();
            
            // Debounce API calls (300ms)
            this.quoteTimeout = setTimeout(async () => {
                try {
                    // ✅ FIX 2: Re-validate inputs before fetching quote (prevent stale updates)
                    const currentKasAmount = parseFloat(document.getElementById('kasAmount').value) || 0;
                    const currentTokenAmount = parseFloat(document.getElementById('tokenAmount').value) || 0;
                    
                    if (action === 'buy' && currentKasAmount <= 0) {
                        return;  // Input was cleared, don't fetch quote
                    }
                    if (action === 'sell' && currentTokenAmount <= 0) {
                        return;  // Input was cleared, don't fetch quote
                    }
                    
                    this.showQuoteLoading();
                    
                    const quote = await window.txManager.getQuote(
                        action,
                        params,  // ✅ Now has correct parameter for each mode
                        this.quoteAbortController?.signal  // H-5 FIX: Pass abort signal with optional chaining
                    );
                    
                    if (quote.success) {
                        // M-9 FIX: Update the OUTPUT field based on mode
                        if (action === 'buy') {
                            // Show tokens user will receive
                            document.getElementById('tokenAmount').value = 
                                Math.floor(quote.tokens_out);
                        } else { // sell
                            // Show KAS user will receive
                            document.getElementById('kasAmount').value = 
                                quote.kas_out.toFixed(6);
                        }
                        
                        // Display fee breakdown
                        this.displayFeeBreakdown({
                            antiBotFee: quote.fees?.anti_bot || 0,
                            platformFee: quote.fees?.platform || 0,
                            creatorFee: quote.fees?.creator || 0,
                            priceImpact: quote.price_impact_percent || 0
                        });
                        
                        // CD-1 + M-8 FIX: Store quote with flat structure INSIDE function
                        window.lastQuote = {
                            ...quote,              // Spread all quote properties (M-8 fix)
                            timestamp: Date.now(),
                            mode: action           // 'buy' or 'sell'
                        };
                        
                        // M-9 FIX: Update USD value (works for both modes)
                        const kasValue = action === 'buy' 
                            ? params.kas_amount 
                            : quote.kas_out;
                        const usdAmount = kasValue * this.kasToUsd;
                        const inputAddon = document.querySelector('.input-addon');
                        if (inputAddon) {
                            inputAddon.textContent = `$${usdAmount.toFixed(2)} USD`;
                        }
                    }
                    
                } catch (error) {
                    // M-2 FIX: Ignore aborted requests
                    if (error.name === 'AbortError') {
                        return; // Request cancelled, ignore
                    }
                    console.error('Quote failed:', error);
                    this.showQuoteError(error.message || 'Quote request failed');
                } finally {
                    this.hideQuoteLoading();
                }
            }, 300);
        },
        
        // NC-3 FIX: Quote freshness validation
        isQuoteFresh: function(maxAgeSeconds = 30) {
            if (!window.lastQuote) return false;
            
            const age = (Date.now() - window.lastQuote.timestamp) / 1000;
            const correctMode = window.lastQuote.mode === this.currentTradeMode;
            
            return age < maxAgeSeconds && correctMode;
        },
        
        // H-4 FIX: Gas estimation with error handling
        estimateTradeGas: async function(action, params) {
            try {
                const response = await fetch(`/api/trade/${action}/estimate-gas`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(params)
                });
                
                if (!response.ok) {
                    throw new Error(`Gas estimation failed: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (!data.gas_estimate) {
                    throw new Error('Invalid gas estimate response');
                }
                
                return data.gas_estimate;
            } catch (error) {
                console.error('Gas estimation error:', error);
                ModalManager.alert(
                    'Gas Estimation Failed',
                    'Unable to estimate gas cost. Please try again.',
                    'error'
                );
                throw error;  // Re-throw to stop trade flow
            }
        },
        
        // Trade status display helper - Phase 3.6 Enhanced
        showTradeStatus: function(message) {
            console.log('🔄 Trade Status:', message);
            
            const statusEl = document.getElementById('tradeStatus');
            if (statusEl) {
                statusEl.textContent = message;
                statusEl.style.display = 'block';
                statusEl.classList.add('status-fade-in');
            }
        },
        
        hideTradeStatus: function() {
            const statusEl = document.getElementById('tradeStatus');
            if (statusEl) {
                statusEl.style.display = 'none';
                statusEl.textContent = '';
            }
        },
        
        // Phase 3.5: executeTrade() with all audit fixes
        executeTrade: async function() {
            // Check wallet connection
            if (!window.walletManager.isConnected()) {
                ModalManager.alert('Wallet Required', 'Please connect your wallet to trade.', 'error');
                window.walletManager.openWalletModal();
                return;
            }
            
            // ⚠️ FIX #1: NETWORK VALIDATION
            const provider = window.walletManager.getMetaMaskProvider();
            const chainId = await provider.request({ method: 'eth_chainId' });
            const chainIdDecimal = parseInt(chainId, 16);
            
            if (chainIdDecimal !== 167012) {
                ModalManager.alert(
                    'Wrong Network',
                    `Please switch to Kasplex Testnet (Chain ID: 167012). Currently on: ${chainIdDecimal}`,
                    'error'
                );
                return;
            }
            
            // NC-3 FIX: Validate quote freshness with auto-refresh
            if (!this.isQuoteFresh()) {
                this.showTradeStatus('Refreshing quote...');
                await this.updateTokenAmount();  // Refresh quote
                
                // Wait for quote to complete (with timeout)
                let attempts = 0;
                while (!this.isQuoteFresh() && attempts < 10) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    attempts++;
                }
                
                this.hideTradeStatus();
                
                if (!this.isQuoteFresh()) {
                    ModalManager.alert('Quote Unavailable', 'Unable to get current price. Please try again.', 'error');
                    return;
                }
            }
            
            const action = this.currentTradeMode; // 'buy' or 'sell'
            
            // Build parameters based on trade type
            let params;
            if (action === 'buy') {
                // BUY FLOW
                const kasAmount = parseFloat(document.getElementById('kasAmount').value) || 0;
                const expectedTokens = parseFloat(document.getElementById('tokenAmount').value) || 0;
                
                if (kasAmount <= 0) {
                    ModalManager.alert('Invalid Amount', 'Please enter a valid KAS amount.', 'error');
                    return;
                }
                
                // H-3 FIX: Check KAS balance before buy
                const wallet = window.walletManager.getConnectedWallet();
                const provider = window.walletManager.getMetaMaskProvider();
                
                const balance = await provider.request({
                    method: 'eth_getBalance',
                    params: [wallet.address, 'latest']
                });
                
                const balanceKAS = parseFloat(ethers.utils.formatEther(balance));
                const requiredKAS = kasAmount * 1.01; // Add 1% for gas
                
                if (balanceKAS < requiredKAS) {
                    ModalManager.alert(
                        'Insufficient Balance',
                        `You need ${requiredKAS.toFixed(4)} KAS (including gas) but only have ${balanceKAS.toFixed(4)} KAS`,
                        'error'
                    );
                    return;
                }
                
                // Calculate slippage protection
                const slippageBps = window.lastQuote?.auto_slippage_bps || 50;
                const minTokensOut = Math.floor(expectedTokens * (10000 - slippageBps) / 10000);
                
                params = {
                    token_address: window.tokenContractAddress,
                    user_address: wallet.address,  // REQUIRED FOR METAMASK
                    kas_amount: kasAmount,
                    min_tokens_out: minTokensOut,
                    deadline: Math.floor(Date.now() / 1000) + 300 // 5 minutes
                };
                
                // H-4 FIX: Get gas estimate for display
                const gasEstimate = await this.estimateTradeGas(action, params);
                const gasCostKAS = ethers.utils.formatEther(gasEstimate.toString());
                const gasCostUSD = (parseFloat(gasCostKAS) * this.kasToUsd).toFixed(2);
                
                // Show gas estimate in status
                this.showTradeStatus(`Estimated gas: ~${parseFloat(gasCostKAS).toFixed(4)} KAS ($${gasCostUSD})`);
                
            } else { // sell
                // SELL FLOW
                const tokenAmount = parseFloat(document.getElementById('tokenAmount').value) || 0;
                const expectedKas = parseFloat(document.getElementById('kasAmount').value) || 0;
                
                if (tokenAmount <= 0) {
                    ModalManager.alert('Invalid Amount', 'Please enter a valid token amount.', 'error');
                    return;
                }
                
                // CB-1 FIX: CHECK ERC20 APPROVAL
                const wallet = window.walletManager.getConnectedWallet();
                const provider = window.walletManager.getMetaMaskProvider();
                
                // ⚠️ FIX #2: Token and Pool are SEPARATE contracts
                // Token is at window.tokenContractAddress
                // Pool needs approval to spend user's tokens
                const tokenContract = new ethers.Contract(
                    window.tokenContractAddress,  // This IS the token
                    [
                        'function allowance(address,address) view returns (uint256)',
                        'function approve(address,uint256) returns (bool)',
                        'function balanceOf(address) view returns (uint256)'
                    ],
                    provider.getSigner()
                );
                
                // Check if pool has allowance to spend user's tokens
                const currentAllowance = await tokenContract.allowance(
                    wallet.address,
                    window.poolContractAddress  // ⚠️ CRITICAL: Approve POOL, not token itself
                );
                
                const tokenAmountWei = ethers.utils.parseEther(tokenAmount.toString());
                
                // If insufficient allowance, request approval
                if (currentAllowance.lt(tokenAmountWei)) {
                    this.showTradeStatus(`Requesting approval to spend ${this.tokenSymbol} tokens...`);
                    
                    // ⚠️ FIX #2: Approve POOL to spend tokens from token contract
                    const approveTx = await tokenContract.approve(
                        window.poolContractAddress,  // Pool address (NOT token address)
                        ethers.constants.MaxUint256
                    );
                    
                    this.showTradeStatus('Waiting for approval confirmation...');
                    await approveTx.wait();
                    this.showTradeStatus('Approval confirmed! Proceeding with sell...');
                }
                
                // Calculate slippage protection
                const slippageBps = window.lastQuote?.auto_slippage_bps || 50;
                const minKasOut = expectedKas * (10000 - slippageBps) / 10000;
                
                params = {
                    token_address: window.tokenContractAddress,
                    user_address: wallet.address,  // REQUIRED FOR METAMASK
                    token_amount: tokenAmount,
                    min_kas_out: minKasOut,
                    deadline: Math.floor(Date.now() / 1000) + 300
                };
                
                // H-4 FIX: Get gas estimate for display
                const gasEstimate = await this.estimateTradeGas(action, params);
                const gasCostKAS = ethers.utils.formatEther(gasEstimate.toString());
                const gasCostUSD = (parseFloat(gasCostKAS) * this.kasToUsd).toFixed(2);
                
                // Show gas estimate in status
                this.showTradeStatus(`Estimated gas: ~${parseFloat(gasCostKAS).toFixed(4)} KAS ($${gasCostUSD})`);
            }
            
            // Execute via TransactionManager with manual flow
            try {
                // Phase 1: Build unsigned transaction
                this.showTradeStatus('Preparing transaction...');
                
                const buildEndpoint = action === 'buy' ? '/api/trade/buy' : '/api/trade/sell';
                const buildResponse = await fetch(buildEndpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(params)
                });
                
                const buildData = await buildResponse.json();
                if (!buildData.success) {
                    throw new Error(buildData.error || 'Failed to build transaction');
                }
                
                const txData = buildData.tx_data;
                
                // Phase 2: Sign and submit with wallet
                this.showTradeStatus('Please sign the transaction in your wallet...');
                const signResult = await window.txManager.signAndSubmitTransaction(txData);
                
                let txHash;
                
                // Phase 3: Relay if needed (for Kaspa wallets)
                if (signResult.needs_relay) {
                    this.showTradeStatus('Submitting to blockchain...');
                    const relayResponse = await fetch('/api/relay/transaction', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            signed_tx: signResult.signed_tx
                        })
                    });
                    
                    const relayData = await relayResponse.json();
                    if (!relayData.success) {
                        throw new Error(relayData.error || 'Failed to relay transaction');
                    }
                    txHash = relayData.tx_hash;
                } else {
                    // MetaMask already submitted
                    txHash = signResult.tx_hash;
                }
                
                // Phase 4: Monitor transaction via SSE
                this.showTradeStatus('Waiting for confirmation...');
                this.monitorTransaction(txHash);
                
            } catch (error) {
                console.error('Trade execution error:', error);
                this.hideTradeStatus();
                ModalManager.alert('Trade Failed', error.message || 'Transaction failed', 'error');
            }
        },
        
        // SSE Transaction Monitoring
        monitorTransaction: function(txHash) {
            const eventSource = new EventSource(`/api/tx/${txHash}/stream`);
            
            eventSource.addEventListener('status', (e) => {
                const data = JSON.parse(e.data);
                this.showTradeStatus(data.message);
                
                if (data.status === 'confirmed' || data.status === 'success') {
                    eventSource.close();
                    this.hideTradeStatus();
                    
                    // Use txHash from closure (no receipt variable)
                    ModalManager.alert(
                        'Trade Successful! ✅',
                        `Transaction: ${txHash}`,
                        'success'
                    );
                    
                    // Refresh wallet balance
                    if (window.WalletManager && window.WalletManager.updateWalletBalance) {
                        window.WalletManager.updateWalletBalance();
                    }
                    
                    // Reload page to update charts and balances
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                    
                } else if (data.status === 'failed' || data.status === 'error') {
                    eventSource.close();
                    this.hideTradeStatus();
                    ModalManager.alert('Transaction Failed', data.message || 'Transaction failed', 'error');
                }
            });
            
            eventSource.onerror = async () => {
                eventSource.close();
                
                // Check transaction status one final time before showing error
                try {
                    const response = await fetch(`/api/tx/${txHash}/status`);
                    const status = await response.json();
                    
                    this.hideTradeStatus();
                    
                    if (status.status === 'confirmed' || status.status === 'success') {
                        // Transaction succeeded! Show success even though monitoring failed
                        ModalManager.alert(
                            'Trade Successful! ✅',
                            `Transaction: ${txHash}`,
                            'success'
                        );
                        
                        // Refresh wallet balance
                        if (window.WalletManager && window.WalletManager.updateWalletBalance) {
                            window.WalletManager.updateWalletBalance();
                        }
                        
                        // Reload page to update charts and balances
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                        
                    } else if (status.status === 'failed' || status.status === 'error') {
                        ModalManager.alert('Transaction Failed', status.message || 'Transaction failed', 'error');
                    } else {
                        // Still pending or unknown
                        ModalManager.alert(
                            'Monitoring Error',
                            'Transaction monitoring failed. Please check the blockchain explorer to verify status.',
                            'warning'
                        );
                    }
                } catch (err) {
                    this.hideTradeStatus();
                    console.error('Error checking final transaction status:', err);
                    ModalManager.alert(
                        'Monitoring Error',
                        'Transaction monitoring failed. Please check the blockchain explorer to verify status.',
                        'warning'
                    );
                }
            };
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
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCsrfToken()
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
                        <span>Replying to <strong>@${this.escapeHtml(replyTo.user)}</strong>: ${this.escapeHtml(replyTo.text)}</span>
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
                    <button class="message-action delete-btn" onclick="TokenDetail.showDeleteConfirm(${messageId})" title="Delete this message">
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
                    <span class="chat-user ${userClass} ${isSpotlight ? 'spotlight-user' : ''}">${this.escapeHtml(displayName)}:</span>
                    <span class="chat-text">${this.escapeHtml(message)} ${isSpotlight ? '✨' : ''}</span>
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
                        'X-Wallet-Address': localStorage.getItem('connectedWallet'),
                        'X-CSRFToken': this.getCsrfToken()
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
                    <span>Replying to <strong>${this.escapeHtml(username)}</strong>: ${this.escapeHtml(messageText)}${messageText.length >= 50 ? '...' : ''}</span>
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
        
        showDeleteConfirm: function(messageId) {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (!messageEl) return;
            
            const deleteBtn = messageEl.querySelector('.delete-btn');
            if (!deleteBtn) return;
            
            // Store original HTML
            const originalHTML = deleteBtn.innerHTML;
            
            // Transform trash into confirm/cancel buttons
            deleteBtn.innerHTML = `
                <i class="fas fa-check" style="color: #4CAF50; cursor: pointer;" onclick="event.stopPropagation(); TokenDetail.confirmDelete(${messageId})" title="Confirm delete"></i>
                <i class="fas fa-times" style="color: #FF5252; cursor: pointer; margin-left: 0.35rem;" onclick="event.stopPropagation(); TokenDetail.cancelDelete(${messageId})" title="Cancel"></i>
            `;
            deleteBtn.style.pointerEvents = 'auto';
            deleteBtn.onclick = null;
            
            // Store original HTML for cancel
            deleteBtn.dataset.originalHTML = originalHTML;
        },
        
        confirmDelete: function(messageId) {
            this.deleteMessage(messageId);
        },
        
        cancelDelete: function(messageId) {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (!messageEl) return;
            
            const deleteBtn = messageEl.querySelector('.delete-btn');
            if (deleteBtn && deleteBtn.dataset.originalHTML) {
                deleteBtn.innerHTML = deleteBtn.dataset.originalHTML;
                deleteBtn.onclick = () => this.showDeleteConfirm(messageId);
                delete deleteBtn.dataset.originalHTML;
            }
        },
        
        deleteMessage: async function(messageId) {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (!messageEl) return;
            
            // User confirmed deletion - proceed
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/message/${messageId}`, {
                    method: 'DELETE',
                    headers: {
                        'X-Wallet-Address': localStorage.getItem('connectedWallet'),
                        'X-CSRFToken': this.getCsrfToken()
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
                    
                    console.log(`🗑️ Deleted message ${messageId}`);
                } else {
                    const error = await response.json();
                    this.showNotification('❌ Delete Failed', error.error || 'Failed to delete message', 'error');
                }
            } catch (error) {
                console.error('Error deleting message:', error);
                this.showNotification('❌ Error', 'Failed to delete message. Please try again.', 'error');
            }
        },
        
        toggleTokenGate: async function() {
            console.log('🔒 Toggle token gate');
            
            if (!window.tokenContractAddress) {
                this.showNotification('❌ Error', 'Unable to update settings. Token address not found.', 'error');
                return;
            }
            
            const toggleCheckbox = document.getElementById('tokenGateToggle');
            if (!toggleCheckbox) return;
            
            const newState = toggleCheckbox.checked;
            
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/settings/update`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Wallet-Address': localStorage.getItem('connectedWallet'),
                        'X-CSRFToken': this.getCsrfToken()
                    },
                    body: JSON.stringify({
                        holders_only_chat: newState,
                        min_tokens_to_chat: this.tokenSettings.minTokensToChat,
                        min_tokens_for_spotlight: this.tokenSettings.minTokensForSpotlight,
                        min_tokens_to_create_poll: this.tokenSettings.minTokensToCreatePoll
                    })
                });
                
                if (response.ok) {
                    this.tokenSettings.holdersOnlyChat = newState;
                    
                    const settingsModal = document.getElementById('chatSettingsModal');
                    if (settingsModal && settingsModal.style.display === 'flex') {
                        const modalCheckbox = document.getElementById('holdersOnlyChat');
                        if (modalCheckbox) {
                            modalCheckbox.checked = newState;
                        }
                    }
                    
                    this.showNotification(
                        '✅ Settings Updated',
                        `Holders-only chat is now ${newState ? 'enabled' : 'disabled'}.`,
                        'success'
                    );
                } else {
                    const error = await response.json();
                    toggleCheckbox.checked = !newState;
                    this.showNotification('❌ Error', error.error || 'Failed to update settings', 'error');
                }
            } catch (error) {
                console.error('Failed to update token gate:', error);
                toggleCheckbox.checked = !newState;
                this.showNotification('❌ Error', 'Failed to update token gate settings', 'error');
            }
        },
        
        openChatSettings: function() {
            console.log('🔧 Opening chat settings...');
            console.log('🔧 Token type:', TokenDetail.isProToken ? 'pro' : 'basic', 'Is Pro:', TokenDetail.isProToken);
            
            // Different settings for pro vs basic tokens
            if (TokenDetail.isProToken) {
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
                                    <div class="section-header" onclick="toggleTreasuryManagement()" style="cursor: pointer; display: flex; align-items: center; justify-content: space-between;">
                                        <h4 style="margin: 0;"><i class="fas fa-coins"></i> Treasury Management</h4>
                                        <i class="fas fa-chevron-down treasury-toggle" style="transition: transform 0.3s; transform: rotate(180deg);"></i>
                                    </div>
                                    <div id="treasuryManagementContent">
                                        <p>Configure treasury distribution settings for your community.</p>
                                        
                                        <div class="form-group">
                                            <label>Airdrop Threshold</label>
                                            <input type="number" class="form-control" value="100000" placeholder="Market cap for airdrops">
                                            <small class="setting-hint">Market cap milestone for community airdrops</small>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="settings-section">
                                    <h4><i class="fas fa-shield-alt"></i> Chat Access Control</h4>
                                    
                                    <div class="form-check" style="margin-bottom: 1.5rem;">
                                        <input type="checkbox" id="holdersOnlyChat" ${TokenDetail.tokenSettings.holdersOnlyChat ? 'checked' : ''}>
                                        <label for="holdersOnlyChat">Holders-only chat</label>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens to chat</label>
                                        <input type="number" class="form-control" id="minTokensToChat" value="${TokenDetail.tokenSettings.minTokensToChat || 0}">
                                        <small class="setting-hint">Minimum balance required to chat</small>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens for spotlight</label>
                                        <input type="number" class="form-control" id="minTokensForSpotlight" value="${TokenDetail.tokenSettings.minTokensForSpotlight || 500}">
                                        <small class="setting-hint">Tokens required to create spotlight messages</small>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens to create poll</label>
                                        <input type="number" class="form-control" id="minTokensToCreatePoll" value="${TokenDetail.tokenSettings.minTokensToCreatePoll || 1000}">
                                        <small class="setting-hint">Tokens required to create polls</small>
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
                                        <input type="checkbox" id="holdersOnlyChat" ${TokenDetail.tokenSettings.holdersOnlyChat ? 'checked' : ''}>
                                        <label for="holdersOnlyChat">Holders-only chat</label>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens to chat</label>
                                        <input type="number" class="form-control" id="minTokensToChat" value="${TokenDetail.tokenSettings.minTokensToChat || 0}">
                                        <small class="setting-hint">Minimum balance required to chat</small>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens for spotlight</label>
                                        <input type="number" class="form-control" id="minTokensForSpotlight" value="${TokenDetail.tokenSettings.minTokensForSpotlight || 500}">
                                        <small class="setting-hint">Tokens required to create spotlight messages</small>
                                    </div>
                                    
                                    <div class="form-group">
                                        <label>Minimum tokens to create poll</label>
                                        <input type="number" class="form-control" id="minTokensToCreatePoll" value="${TokenDetail.tokenSettings.minTokensToCreatePoll || 1000}">
                                        <small class="setting-hint">Tokens required to create polls</small>
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
        
        saveChatSettings: async function() {
            // Save settings logic
            const holdersOnly = document.getElementById('holdersOnlyChat').checked;
            const minTokens = document.getElementById('minTokensToChat').value;
            const spotlightThreshold = document.getElementById('minTokensForSpotlight').value;
            const pollThreshold = document.getElementById('minTokensToCreatePoll').value;
            
            if (!window.tokenContractAddress) {
                this.showNotification('❌ Error', 'Unable to save settings. Token address not found.', 'error');
                return;
            }
            
            const settings = {
                holdersOnlyChat: holdersOnly,
                minTokensToChat: parseInt(minTokens) || 0,
                minTokensForSpotlight: parseInt(spotlightThreshold) || 500,
                minTokensToCreatePoll: parseInt(pollThreshold) || 1000
            };
            
            console.log('💾 Saving chat settings:', settings);
            
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/settings/update`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Wallet-Address': localStorage.getItem('connectedWallet'),
                        'X-CSRFToken': this.getCsrfToken()
                    },
                    body: JSON.stringify({
                        holders_only_chat: settings.holdersOnlyChat,
                        min_tokens_to_chat: settings.minTokensToChat,
                        min_tokens_for_spotlight: settings.minTokensForSpotlight,
                        min_tokens_to_create_poll: settings.minTokensToCreatePoll
                    })
                });
                
                if (response.ok) {
                    this.tokenSettings.holdersOnlyChat = settings.holdersOnlyChat;
                    this.tokenSettings.minTokensToChat = settings.minTokensToChat;
                    this.tokenSettings.minTokensForSpotlight = settings.minTokensForSpotlight;
                    this.tokenSettings.minTokensToCreatePoll = settings.minTokensToCreatePoll;
                    
                    this.closeChatSettings();
                    this.checkTokenOwnership();
                    this.showNotification('Settings Saved', 'Chat settings have been updated successfully.', 'success');
                } else {
                    const error = await response.json();
                    this.showNotification('❌ Error', error.error || 'Failed to save settings', 'error');
                }
            } catch (error) {
                console.error('Failed to save chat settings:', error);
                this.showNotification('❌ Error', 'Failed to save settings. Please try again.', 'error');
            }
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
        
        // HTML escape utility to prevent XSS
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        // Poll and spotlight functions
        addPollToChat: function(poll) {
            console.log('📊 Adding poll to chat:', poll);
            
            const chatContainer = document.getElementById('chatMessages');
            if (!chatContainer) return;
            
            // Calculate total votes
            const totalVotes = poll.total_votes || 0;
            
            // Calculate time remaining
            const now = new Date();
            const endsAt = new Date(poll.ends_at);
            const timeRemainingMs = Math.max(0, endsAt - now);
            const hoursRemaining = Math.floor(timeRemainingMs / (1000 * 60 * 60));
            const minutesRemaining = Math.floor((timeRemainingMs % (1000 * 60 * 60)) / (1000 * 60));
            
            let timeDisplay = '';
            if (timeRemainingMs <= 0) {
                timeDisplay = 'Ended';
            } else if (hoursRemaining > 0) {
                timeDisplay = `${hoursRemaining}h ${minutesRemaining}m left`;
            } else {
                timeDisplay = `${minutesRemaining}m left`;
            }
            
            // Check if poll has ended
            const hasEnded = timeRemainingMs <= 0;
            
            // Check if user already voted
            const userHasVoted = poll.user_has_voted || false;
            
            // Create poll container
            const pollDiv = document.createElement('div');
            pollDiv.className = 'chat-poll';
            pollDiv.setAttribute('data-poll-id', poll.id);
            pollDiv.style.cssText = `
                background: linear-gradient(135deg, rgba(32, 178, 170, 0.15) 0%, rgba(0, 206, 209, 0.1) 100%);
                border: 1px solid rgba(32, 178, 170, 0.3);
                border-radius: 12px;
                padding: 1rem;
                margin: 1rem 0;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            `;
            
            // Build options HTML
            let optionsHTML = '';
            poll.options.forEach(option => {
                const percentage = totalVotes > 0 ? Math.round((option.vote_count / totalVotes) * 100) : 0;
                const isDisabled = userHasVoted || hasEnded;
                const voteWidth = `${percentage}%`;
                
                optionsHTML += `
                    <div class="poll-option ${isDisabled ? 'disabled' : ''}" 
                         onclick="${isDisabled ? '' : `TokenDetail.votePoll(${poll.id}, ${option.id})`}"
                         style="
                            position: relative;
                            background: rgba(255, 255, 255, 0.05);
                            border: 1px solid rgba(32, 178, 170, 0.2);
                            border-radius: 8px;
                            padding: 0.75rem;
                            margin: 0.5rem 0;
                            cursor: ${isDisabled ? 'not-allowed' : 'pointer'};
                            transition: all 0.3s ease;
                            overflow: hidden;
                            ${isDisabled ? 'opacity: 0.7;' : ''}
                         "
                         ${isDisabled ? '' : 'onmouseenter="this.style.borderColor=\'#20B2AA\'; this.style.background=\'rgba(32, 178, 170, 0.1)\';"'}
                         ${isDisabled ? '' : 'onmouseleave="this.style.borderColor=\'rgba(32, 178, 170, 0.2)\'; this.style.background=\'rgba(255, 255, 255, 0.05)\';"'}
                    >
                        <div style="
                            position: absolute;
                            top: 0;
                            left: 0;
                            height: 100%;
                            width: ${voteWidth};
                            background: linear-gradient(90deg, rgba(32, 178, 170, 0.2) 0%, rgba(0, 206, 209, 0.1) 100%);
                            transition: width 0.5s ease;
                            border-radius: 8px 0 0 8px;
                        "></div>
                        <div style="position: relative; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #E0E0E0; font-weight: 500;">${this.escapeHtml(option.text)}</span>
                            <div style="display: flex; align-items: center; gap: 0.75rem;">
                                <span style="color: #20B2AA; font-weight: 600; font-size: 0.9rem;">${percentage}%</span>
                                <span style="color: #888; font-size: 0.85rem;">${option.vote_count} vote${option.vote_count !== 1 ? 's' : ''}</span>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            // Build the complete poll HTML
            pollDiv.innerHTML = `
                <div style="display: flex; align-items: start; gap: 0.75rem; margin-bottom: 1rem;">
                    <div style="font-size: 1.2rem; color: #20B2AA; margin-top: 0.25rem;">
                        <i class="fas fa-poll"></i>
                    </div>
                    <div style="flex: 1;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                            <div>
                                <div style="color: #20B2AA; font-weight: 600; margin-bottom: 0.25rem;">
                                    ${this.escapeHtml(poll.creator)}
                                </div>
                                <div style="color: #E0E0E0; font-size: 1.1rem; font-weight: 500; margin-bottom: 0.75rem;">
                                    ${this.escapeHtml(poll.question)}
                                </div>
                            </div>
                        </div>
                        
                        ${optionsHTML}
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid rgba(32, 178, 170, 0.2);">
                            <div style="display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap;">
                                <div style="display: flex; align-items: center; gap: 0.5rem; color: #00CED1; font-size: 0.85rem;">
                                    <i class="fas fa-users"></i>
                                    <span>${totalVotes} vote${totalVotes !== 1 ? 's' : ''}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.5rem; color: #00CED1; font-size: 0.85rem;">
                                    <i class="fas fa-fire"></i>
                                    <span>${poll.vote_cost} ${this.tokenSymbol} per vote</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.5rem; color: ${hasEnded ? '#FF5252' : '#00CED1'}; font-size: 0.85rem;">
                                    <i class="fas fa-clock"></i>
                                    <span>${timeDisplay}</span>
                                </div>
                            </div>
                            ${userHasVoted ? `
                                <div style="color: #4CAF50; font-size: 0.85rem; display: flex; align-items: center; gap: 0.5rem;">
                                    <i class="fas fa-check-circle"></i>
                                    <span>You voted</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
            
            // Add to chat
            chatContainer.appendChild(pollDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        },
        
        // Vote on a poll
        votePoll: async function(pollId, optionId) {
            const userWallet = localStorage.getItem('connectedWallet');
            if (!userWallet) {
                ModalManager.alert('❌ Error', 'Please connect your wallet to vote on polls.', 'error');
                return;
            }
            
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/polls/${pollId}/vote`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Wallet-Address': userWallet,
                        'X-CSRFToken': this.getCsrfToken()
                    },
                    body: JSON.stringify({
                        option_id: optionId
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    // Show success message
                    ModalManager.alert('✅ Vote Recorded', 'Your vote has been successfully recorded!', 'success');
                    
                    // Reload polls to update the display
                    await this.reloadPolls();
                } else {
                    // Show error message
                    ModalManager.alert('❌ Error', data.error || 'Failed to vote on poll. Please try again.', 'error');
                }
            } catch (error) {
                console.error('Failed to vote on poll:', error);
                ModalManager.alert('❌ Error', 'Failed to vote on poll. Please try again.', 'error');
            }
        },
        
        // Reload polls from server
        reloadPolls: async function() {
            try {
                const userWallet = localStorage.getItem('connectedWallet');
                const response = await fetch(`/api/token/${window.tokenContractAddress}/polls`, {
                    headers: {
                        'X-Wallet-Address': userWallet
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    // Remove existing polls from chat
                    const chatContainer = document.getElementById('chatMessages');
                    const existingPolls = chatContainer.querySelectorAll('.chat-poll');
                    existingPolls.forEach(poll => poll.remove());
                    
                    // Re-add updated polls
                    data.polls.forEach(poll => {
                        this.addPollToChat(poll);
                    });
                }
            } catch (error) {
                console.error('Failed to reload polls:', error);
            }
        },
        
        // Add spotlight message WITHOUT controlling container visibility
        addSpotlightMessage: function(spotlight) {
            const listContainer = document.getElementById('spotlightMessagesList');
            if (!listContainer) return;
            
            // Calculate time remaining
            const timeRemaining = Math.max(0, Math.floor((spotlight.expiresAt - Date.now()) / 1000 / 60));
            
            // Skip expired messages (don't display them at all)
            if (timeRemaining <= 0) {
                console.log('⏰ Skipping expired spotlight message:', spotlight.id);
                return;
            }
            
            // Create spotlight message element with teal/blue theme
            const spotlightDiv = document.createElement('div');
            spotlightDiv.className = 'spotlight-message';
            spotlightDiv.setAttribute('data-spotlight-id', spotlight.id);
            spotlightDiv.style.cssText = `
                background: rgba(32, 178, 170, 0.1);
                border: 1px solid #20B2AA;
                border-radius: 8px;
                padding: 0.75rem;
                margin-bottom: 0.5rem;
                position: relative;
            `;
            
            spotlightDiv.innerHTML = `
                <div style="display: flex; align-items: start; gap: 0.75rem;">
                    <div class="spotlight-icon" style="font-size: 0.9rem; color: #20B2AA; margin-top: 0.2rem;">
                        <i class="fas fa-thumbtack"></i>
                    </div>
                    <div class="spotlight-content" style="flex: 1; min-width: 0; padding-right: 4.5rem;">
                        <div class="spotlight-user" style="
                            font-weight: 600;
                            color: #20B2AA;
                            margin-bottom: 0.25rem;
                        ">${this.escapeHtml(spotlight.user)}</div>
                        <div class="spotlight-text" style="
                            color: #E0E0E0;
                            font-size: 1rem;
                            line-height: 1.4;
                        ">${this.escapeHtml(spotlight.message)}</div>
                    </div>
                </div>
                <div class="spotlight-time" style="
                    display: flex;
                    align-items: center;
                    gap: 0.25rem;
                    color: #00CED1;
                    font-size: 0.85rem;
                    position: absolute;
                    top: 0.75rem;
                    right: 0.75rem;
                ">
                    <i class="fas fa-clock" style="color: #00CED1; font-size: 0.8rem;"></i>
                    <span id="spotlight-timer-${spotlight.id}">${timeRemaining}m</span>
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
                        timerElement.textContent = `${remaining}m`;
                    } else {
                        timerElement.innerHTML = '<span style="color: #dc3545;">0m</span>';
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
                    setTimeout(() => {
                        element.remove();
                        // Hide container if no spotlights remain
                        const listContainer = document.getElementById('spotlightMessagesList');
                        const spotlightContainer = document.getElementById('spotlightMessages');
                        if (listContainer && spotlightContainer && listContainer.children.length === 0) {
                            spotlightContainer.style.display = 'none';
                        }
                    }, 500);
                }
            }, timeRemaining * 60 * 1000);
        },
        
        // Update spotlight display for newly created spotlights
        updateSpotlightDisplay: function(spotlight) {
            console.log('✨ Updating spotlight display:', spotlight);
            
            // Show the container when adding a new spotlight
            const spotlightContainer = document.getElementById('spotlightMessages');
            if (spotlightContainer) {
                spotlightContainer.style.display = 'block';
            }
            
            // Add the message
            this.addSpotlightMessage(spotlight);
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
                            <button class="modal-close" onclick="ModalManager.closeModal('spotlightModal')">&times;</button>
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
                            <button type="button" class="btn btn-secondary" onclick="ModalManager.closeModal('spotlightModal')">
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
                    ModalManager.alert(
                        'Empty Message',
                        'Please enter a message to spotlight.',
                        'error'
                    );
                    return;
                }
                
                ModalManager.closeModal('spotlightModal');
                
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
                    
                    // Success notification removed per user request
                } else {
                    const error = await response.json();
                    this.showNotification('❌ Error', error.error || 'Failed to create spotlight', 'error');
                }
            } catch (error) {
                console.error('Failed to create spotlight:', error);
                this.showNotification('❌ Error', 'Failed to create spotlight message', 'error');
            }
        },
        
        fetchGraduationStatus: async function() {
            try {
                const response = await fetch(`/api/token/${window.tokenContractAddress}/graduation-status`);
                const data = await response.json();
                
                if (data.success) {
                    if (data.is_graduated) {
                        this.updateGraduationProgress({
                            marketCap: 70000,
                            graduationThreshold: 70000,
                            isGraduated: true,
                            dexPoolAddress: data.dex_pool?.pool_address
                        });
                    } else {
                        this.updateGraduationProgress({
                            marketCap: data.current_market_cap,
                            graduationThreshold: data.graduation_threshold || 70000,
                            isGraduated: false,
                            progressPercent: data.progress_percent
                        });
                    }
                }
            } catch (error) {
                console.error('Failed to fetch graduation status:', error);
            }
        },
        
        updateGraduationProgress: function(data) {
            const progressPercent = data.progressPercent || (data.marketCap / data.graduationThreshold) * 100;
            const progressBar = document.querySelector('.progress-fill');
            
            if (progressBar) {
                progressBar.style.width = `${Math.min(progressPercent, 100)}%`;
            }
            
            const marketCapElement = document.getElementById('marketCapValue');
            if (marketCapElement) {
                marketCapElement.textContent = 
                    `$${data.marketCap.toLocaleString('en-US', {maximumFractionDigits: 0})}`;
            }
            
            if (data.isGraduated) {
                this.showGraduatedStatus(data.dexPoolAddress);
            } else if (progressPercent >= 100) {
                this.showGraduatingStatus();
            }
        },
        
        showGraduatedStatus: function(poolAddress) {
            const container = document.getElementById('graduationStatus');
            if (!container) return;
            
            container.innerHTML = `
                <div style="background: linear-gradient(135deg, #4CAF50, #45a049); 
                            padding: 1rem; border-radius: 10px; text-align: center;">
                    <h3 style="margin: 0 0 0.5rem 0; color: #fff;">🎓 Graduated to Kaspa Finance DEX</h3>
                    <a href="https://kaspa.finance/pool/${poolAddress}" 
                       target="_blank" 
                       class="btn btn-primary" 
                       style="margin-top: 0.5rem; display: inline-block; padding: 0.5rem 1rem; background: #fff; color: #4CAF50; text-decoration: none; border-radius: 5px; font-weight: 600;">
                        Trade on DEX →
                    </a>
                </div>
            `;
        },
        
        showGraduatingStatus: function() {
            const container = document.getElementById('graduationStatus');
            if (!container) return;
            
            container.innerHTML = `
                <div style="background: linear-gradient(135deg, #FFA500, #FF8C00); 
                            padding: 1rem; border-radius: 10px; text-align: center;">
                    <h3 style="margin: 0 0 0.5rem 0; color: #fff;">🚀 Graduating to DEX...</h3>
                    <p style="margin: 0; color: #fff; font-size: 0.9rem;">Market cap reached $70,000! Liquidity pool deploying...</p>
                </div>
            `;
        },
        
        // Vesting modal and data fetching
        loadVestingData: async function() {
            if (!this.isProToken || !window.tokenId || !window.tokenContractAddress) {
                return;
            }

            try {
                const response = await fetch(`/api/token/${window.tokenId}/vesting/status`);
                if (!response.ok) {
                    console.warn('No vesting data available');
                    return;
                }

                const data = await response.json();
                if (data.success && data.vesting) {
                    this.updateVestingModal(data.vesting);
                }
            } catch (error) {
                console.error('Error loading vesting data:', error);
            }
        },

        updateVestingModal: function(data) {
            if (!window.VestingUtils) {
                console.warn('Vesting utilities not loaded');
                return;
            }

            // Check if there's any vesting data at all
            const hasAnyData = data && (data.marketing || data.team || data.airdrop);
            if (!hasAnyData) {
                // Show message in all sections that vesting contracts are being deployed
                const noDataMessage = `
                    <div style="text-align: center; padding: 1rem; color: #FFD700;">
                        <i class="fas fa-clock" style="font-size: 1.5rem; margin-bottom: 0.5rem;"></i>
                        <p style="margin: 0; font-size: 0.9rem;">Vesting contracts deploying...</p>
                        <p style="margin: 0.5rem 0 0 0; font-size: 0.8rem; opacity: 0.8;">Refresh page in a few moments</p>
                    </div>
                `;
                ['marketing-progress-info', 'team-progress-info', 'airdrop-progress-info'].forEach(id => {
                    const div = document.getElementById(id);
                    if (div) div.innerHTML = noDataMessage;
                });
                return;
            }

            // Update marketing vesting  
            if (data.marketing) {
                const { total_amount, unlocked_amount, contract_address } = data.marketing;
                const progress = window.VestingUtils.calculateProgress(unlocked_amount, total_amount);
                const unlockedFormatted = window.VestingUtils.formatTokenAmount(unlocked_amount);
                const totalFormatted = window.VestingUtils.formatTokenAmount(total_amount);
                
                const infoDiv = document.getElementById('marketing-progress-info');
                if (infoDiv) {
                    infoDiv.innerHTML = `
                        <div style="font-size: 0.9rem;">
                            <div style="margin-bottom: 0.5rem;">
                                <strong style="color: #20B2AA;">Contract:</strong><br>
                                <code style="font-size: 0.85rem; color: #fff;">${contract_address}</code>
                            </div>
                            <div style="background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 5px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                    <span>Unlocked:</span>
                                    <strong>${unlockedFormatted}</strong>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                    <span>Total:</span>
                                    <strong>${totalFormatted}</strong>
                                </div>
                                <div style="height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; margin-top: 0.5rem;">
                                    <div style="height: 100%; background: #20B2AA; width: ${progress}%;"></div>
                                </div>
                                <div style="text-align: center; margin-top: 0.3rem; color: #20B2AA; font-size: 0.85rem;">
                                    ${progress.toFixed(1)}% unlocked
                                </div>
                            </div>
                        </div>
                    `;
                }
            }

            // Update team vesting
            if (data.team) {
                const { total_amount, unlocked_amount, contract_address } = data.team;
                const progress = window.VestingUtils.calculateProgress(unlocked_amount, total_amount);
                const unlockedFormatted = window.VestingUtils.formatTokenAmount(unlocked_amount);
                const totalFormatted = window.VestingUtils.formatTokenAmount(total_amount);
                
                const infoDiv = document.getElementById('team-progress-info');
                if (infoDiv) {
                    infoDiv.innerHTML = `
                        <div style="font-size: 0.9rem;">
                            <div style="margin-bottom: 0.5rem;">
                                <strong style="color: #B19CD9;">Contract:</strong><br>
                                <code style="font-size: 0.85rem; color: #fff;">${contract_address}</code>
                            </div>
                            <div style="background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 5px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                    <span>Unlocked:</span>
                                    <strong>${unlockedFormatted}</strong>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                    <span>Total:</span>
                                    <strong>${totalFormatted}</strong>
                                </div>
                                <div style="height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; margin-top: 0.5rem;">
                                    <div style="height: 100%; background: #B19CD9; width: ${progress}%;"></div>
                                </div>
                                <div style="text-align: center; margin-top: 0.3rem; color: #B19CD9; font-size: 0.85rem;">
                                    ${progress.toFixed(1)}% unlocked
                                </div>
                            </div>
                        </div>
                    `;
                }
            }

            // Update airdrop vesting
            if (data.airdrop) {
                const { total_amount, unlocked_amount, contract_address } = data.airdrop;
                const progress = window.VestingUtils.calculateProgress(unlocked_amount, total_amount);
                const unlockedFormatted = window.VestingUtils.formatTokenAmount(unlocked_amount);
                const totalFormatted = window.VestingUtils.formatTokenAmount(total_amount);
                
                const infoDiv = document.getElementById('airdrop-progress-info');
                if (infoDiv) {
                    infoDiv.innerHTML = `
                        <div style="font-size: 0.9rem;">
                            <div style="margin-bottom: 0.5rem;">
                                <strong style="color: #00D9FF;">Contract:</strong><br>
                                <code style="font-size: 0.85rem; color: #fff;">${contract_address}</code>
                            </div>
                            <div style="background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 5px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                    <span>Unlocked:</span>
                                    <strong>${unlockedFormatted}</strong>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                    <span>Total:</span>
                                    <strong>${totalFormatted}</strong>
                                </div>
                                <div style="height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; margin-top: 0.5rem;">
                                    <div style="height: 100%; background: #00D9FF; width: ${progress}%;"></div>
                                </div>
                                <div style="text-align: center; margin-top: 0.3rem; color: #00D9FF; font-size: 0.85rem;">
                                    ${progress.toFixed(1)}% unlocked
                                </div>
                            </div>
                        </div>
                    `;
                }
            }
        }
    };
    
    // Expose the module to global scope for HTML event handlers
    window.TokenDetail = TokenDetail;
    
    // Initialize function - runs on turbo:load and DOMContentLoaded
    function initializeTokenPage() {
        // TradingView chart initialization
        if (window.LightweightCharts && document.getElementById('tradingview_chart')) {
            setTimeout(() => TokenDetail.initChart(), 100);
        }
        
        // Chart type toggle buttons - only add if not already added
        document.querySelectorAll('.chart-type-btn').forEach(btn => {
            if (!btn.dataset.listenerAdded) {
                btn.dataset.listenerAdded = 'true';
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.chart-type-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    
                    TokenDetail.currentChartType = this.getAttribute('data-type');
                    TokenDetail.initChart();
                });
            }
        });
        
        // Interval selector buttons (like real trading platforms)
        document.querySelectorAll('.interval-btn').forEach(btn => {
            if (!btn.dataset.listenerAdded) {
                btn.dataset.listenerAdded = 'true';
                btn.addEventListener('click', function() {
                    // Update active state
                    document.querySelectorAll('.interval-btn').forEach(b => {
                        b.classList.remove('active');
                        b.style.background = 'transparent';
                        b.style.borderColor = '#555';
                        b.style.color = '#888';
                    });
                    this.classList.add('active');
                    this.style.background = 'rgba(32, 178, 170, 0.2)';
                    this.style.borderColor = '#20B2AA';
                    this.style.color = '#20B2AA';
                    
                    // Reload chart with new interval
                    TokenDetail.currentInterval = this.getAttribute('data-interval');
                    TokenDetail.initChart();
                });
            }
        });
        
        // ⚠️ M-10 FIX: Mode-aware input listeners
        const kasAmountInput = document.getElementById('kasAmount');
        const tokenAmountInput = document.getElementById('tokenAmount');

        if (kasAmountInput && !kasAmountInput.dataset.listenerAdded) {
            kasAmountInput.dataset.listenerAdded = 'true';
            kasAmountInput.addEventListener('input', () => {
                // Only trigger in BUY mode (kasAmount is input in buy mode)
                if (TokenDetail.currentTradeMode === 'buy') {
                    TokenDetail.updateTokenAmount();
                }
            });
        }

        if (tokenAmountInput && !tokenAmountInput.dataset.listenerAdded) {
            tokenAmountInput.dataset.listenerAdded = 'true';
            tokenAmountInput.addEventListener('input', () => {
                // Only trigger in SELL mode (tokenAmount is input in sell mode)
                if (TokenDetail.currentTradeMode === 'sell') {
                    TokenDetail.updateTokenAmount();
                }
            });
        }
        
        // Chat enter key - only add if not already added
        const chatInput = document.getElementById('chatInput');
        if (chatInput && !chatInput.dataset.listenerAdded) {
            chatInput.dataset.listenerAdded = 'true';
            chatInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    // Use the same global function as the send button to ensure consistency
                    window.sendMessage();
                }
            });
        }
    }
    
    // Initialize on turbo:load (fires on both initial load AND Turbo navigation)
    document.addEventListener('turbo:load', initializeTokenPage);
    
    // Fallback for non-Turbo scenarios
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTokenPage);
    } else {
        // DOM already loaded, initialize immediately
        initializeTokenPage();
    }
    
    // Additional global functions for HTML event handlers
    window.setTradeMode = function(mode) { TokenDetail.setTradeMode(mode); };
    window.switchTradeMode = function() { TokenDetail.switchTradeMode(); };
    window.setQuickAmount = function(amount) { TokenDetail.setQuickAmount(amount); };
    window.executeTrade = function() { TokenDetail.executeTrade(); };
    window.togglePlatformFees = function() {
        const details = document.getElementById('platformFeeDetails');
        const toggle = document.querySelector('.platform-fee-toggle');
        const chevron = document.getElementById('platformFeeChevron');
        
        if (details.style.display === 'none') {
            details.style.display = 'block';
            toggle.classList.add('expanded');
            chevron.classList.remove('fa-chevron-right');
            chevron.classList.add('fa-chevron-down');
        } else {
            details.style.display = 'none';
            toggle.classList.remove('expanded');
            chevron.classList.remove('fa-chevron-down');
            chevron.classList.add('fa-chevron-right');
        }
    };
    window.sendMessage = function() { TokenDetail.sendMessage(); };
    window.openChatSettings = function() { TokenDetail.openChatSettings(); };
    window.copyContractAddress = function(address) {
        navigator.clipboard.writeText(address).then(() => {
            ModalManager.alert(
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
    
    window.toggleTreasuryManagement = function() {
        const content = document.getElementById('treasuryManagementContent');
        const toggle = document.querySelector('.treasury-toggle');
        if (content && toggle) {
            if (content.classList.contains('collapsed')) {
                // Expand: remove collapsed class, set maxHeight, rotate chevron up
                content.classList.remove('collapsed');
                content.style.maxHeight = content.scrollHeight + 'px';
                toggle.style.transform = 'rotate(180deg)';
            } else {
                // Collapse: add collapsed class, set maxHeight to 0, rotate chevron down
                content.classList.add('collapsed');
                content.style.maxHeight = '0';
                toggle.style.transform = 'rotate(0deg)';
            }
        }
    };
    
})(window, document);

// Toggle vesting info modal
function toggleVestingModal() {
    let modal = document.getElementById('vestingModal');
    
    // If modal exists, just toggle it
    if (modal) {
        const isVisible = modal.style.display === 'flex';
        if (isVisible) {
            modal.style.display = 'none';
        } else {
            modal.style.display = 'flex';
            // Load vesting data when opening
            if (window.TokenDetail && window.tokenId) {
                window.TokenDetail.loadVestingData();
            }
        }
        return;
    }
    
    // Create modal first time only
    if (!window.vestingData) return;
    
    const vd = window.vestingData;
    const airdropsTotal = (vd.airdropsAllocation * vd.reservedPercentage / 100).toFixed(2);
    const marketingTotal = (vd.marketingAllocation * vd.reservedPercentage / 100).toFixed(2);
    const teamTotal = (vd.teamAllocation * vd.reservedPercentage / 100).toFixed(2);
    
    const modalHTML = `
        <div id="vestingModal" class="modal" style="display: flex;">
            <div class="modal-content vesting-modal-content">
                <div class="modal-header">
                    <h3><i class="fas fa-lock"></i> Reserve Allocation & Vesting</h3>
                    <button class="modal-close" onclick="toggleVestingModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div style="text-align: center; margin-bottom: 1rem;">
                        <div style="font-size: 1.1rem; font-weight: 600; color: #20B2AA;">
                            ${vd.reservedPercentage}% Total Allocation
                        </div>
                    </div>
                    <div class="vesting-bar">
                        <div class="vesting-segment airdrops" style="width: ${vd.airdropsAllocation}%;">
                            <span class="vesting-label">${vd.airdropsAllocation}%</span>
                        </div>
                        <div class="vesting-segment marketing" style="width: ${vd.marketingAllocation}%;">
                            <span class="vesting-label">${vd.marketingAllocation}%</span>
                        </div>
                        <div class="vesting-segment team" style="width: ${vd.teamAllocation}%;">
                            <span class="vesting-label">${vd.teamAllocation}%</span>
                        </div>
                    </div>
                    <div class="vesting-details">
                        <div class="vesting-item-wrapper">
                            <div class="vesting-item" onclick="toggleVestingProgress(this)" style="cursor: pointer;">
                                <i class="fas fa-gift" style="color:#00D9FF;"></i>
                                <span class="vesting-category">Airdrops & Rewards</span>
                                <span class="vesting-percent">${airdropsTotal}% of total</span>
                                <small>5% daily unlock</small>
                            </div>
                            <div class="vesting-progress-container" style="display: none; padding: 1rem; background: rgba(0,0,0,0.2); border-radius: 0 0 8px 8px; margin-top: -0.5rem;">
                                <div id="airdrop-progress-info"></div>
                            </div>
                        </div>
                        <div class="vesting-item-wrapper">
                            <div class="vesting-item" onclick="toggleVestingProgress(this)" style="cursor: pointer;">
                                <i class="fas fa-bullhorn" style="color:#20B2AA;"></i>
                                <span class="vesting-category">Marketing</span>
                                <span class="vesting-percent">${marketingTotal}% of total</span>
                                <small>12-month linear</small>
                            </div>
                            <div class="vesting-progress-container" style="display: none; padding: 1rem; background: rgba(0,0,0,0.2); border-radius: 0 0 8px 8px; margin-top: -0.5rem;">
                                <div id="marketing-progress-info"></div>
                            </div>
                        </div>
                        <div class="vesting-item-wrapper">
                            <div class="vesting-item" onclick="toggleVestingProgress(this)" style="cursor: pointer;">
                                <i class="fas fa-users" style="color:#B19CD9;"></i>
                                <span class="vesting-category">Team</span>
                                <span class="vesting-percent">${teamTotal}% of total</span>
                                <small>6mo cliff + 18mo vest</small>
                            </div>
                            <div class="vesting-progress-container" style="display: none; padding: 1rem; background: rgba(0,0,0,0.2); border-radius: 0 0 8px 8px; margin-top: -0.5rem;">
                                <div id="team-progress-info"></div>
                            </div>
                        </div>
                        <div class="vesting-item">
                            <i class="fas fa-swimming-pool" style="color:#FFD700;"></i>
                            <span class="vesting-category">Liquidity Pool</span>
                            <span class="vesting-percent">25% of total</span>
                            <small>Reserved for DEX graduation</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Close on background click
    modal = document.getElementById('vestingModal');
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            toggleVestingModal();
        }
    });
    
    // Load vesting data
    if (window.TokenDetail && window.tokenId) {
        window.TokenDetail.loadVestingData();
    }
}

// Toggle vesting progress display
function toggleVestingProgress(element) {
    const wrapper = element.closest('.vesting-item-wrapper');
    if (!wrapper) return;
    
    const progressContainer = wrapper.querySelector('.vesting-progress-container');
    if (!progressContainer) return;
    
    const isHidden = progressContainer.style.display === 'none';
    
    if (isHidden) {
        // Expand
        progressContainer.style.display = 'block';
        
        // Load data immediately if not loaded
        const infoDiv = progressContainer.querySelector('div[id$="-progress-info"]');
        if (infoDiv && infoDiv.innerHTML === '') {
            // Trigger data load if TokenDetail is available
            if (window.TokenDetail && window.tokenId) {
                window.TokenDetail.loadVestingData();
            }
        }
    } else {
        // Collapse
        progressContainer.style.display = 'none';
    }
}
