class WalletManager {
    constructor() {
        this.connectedWallet = null;
        this.sessionCheckInterval = null;
        this.eventHandlers = {
            connect: [],
            disconnect: [],
            switch: [],
            error: []
        };
        
        this.KASPLEX_TESTNET = {
            chainId: '0x28C64',
            chainName: 'Kasplex Testnet',
            nativeCurrency: {
                name: 'Bridged KAS',
                symbol: 'KAS',
                decimals: 18
            },
            rpcUrls: ['https://rpc.kasplextest.xyz'],
            blockExplorerUrls: ['https://frontend.kasplextest.xyz']
        };
        
        this.init();
    }
    
    getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }
    
    init() {
        const savedWallet = this.getSavedWallet();
        if (savedWallet) {
            this.connectedWallet = savedWallet;
            this.startSessionPolling();
        }
        
        this.setupMetaMaskListeners();
    }
    
    setupMetaMaskListeners() {
        if (typeof window.ethereum !== 'undefined') {
            window.ethereum.on('accountsChanged', async (accounts) => {
                console.log('[WalletManager] MetaMask accountsChanged event:', accounts);
                console.log('[WalletManager] Current connected wallet:', this.connectedWallet);
                
                if (accounts.length === 0) {
                    console.log('[WalletManager] No accounts available - user disconnected from MetaMask');
                    if (this.connectedWallet) {
                        await this.disconnectWallet();
                    }
                } else if (this.connectedWallet && this.connectedWallet.wallet_type === 'metamask') {
                    const newAddress = accounts[0].toLowerCase();
                    const currentAddress = this.connectedWallet.address.toLowerCase();
                    
                    console.log('[WalletManager] Comparing addresses:', { current: currentAddress, new: newAddress });
                    
                    if (newAddress !== currentAddress) {
                        console.log('[WalletManager] Account changed detected - disconnecting old wallet');
                        await this.disconnectWallet();
                        
                        // Show user-friendly notification
                        const userChoice = confirm(
                            `Your MetaMask account has changed to ${newAddress.slice(0, 8)}...${newAddress.slice(-6)}.\n\n` +
                            'Would you like to connect with this new account now?'
                        );
                        
                        if (userChoice) {
                            console.log('[WalletManager] User chose to reconnect with new account');
                            try {
                                await this.connectWallet('metamask');
                                window.location.reload();
                            } catch (error) {
                                console.error('[WalletManager] Failed to reconnect:', error);
                                alert('Failed to connect with new account. Please try again manually.');
                            }
                        }
                    }
                }
            });
            
            window.ethereum.on('chainChanged', (chainId) => {
                console.log('[WalletManager] MetaMask chain changed:', chainId);
                window.location.reload();
            });
        }
    }
    
    detectWallet(walletType) {
        switch(walletType.toLowerCase()) {
            case 'kastle':
                return typeof window.kastle !== 'undefined' || typeof window.kasware !== 'undefined';
            case 'kasware':
                return typeof window.kasware !== 'undefined';
            case 'metamask':
                return typeof window.ethereum !== 'undefined';
            default:
                return false;
        }
    }
    
    async requestAccounts(walletType) {
        let accounts = null;
        
        switch(walletType.toLowerCase()) {
            case 'kastle':
                if (typeof window.kastle !== 'undefined') {
                    accounts = await window.kastle.request({
                        method: 'kas_requestAccounts'
                    });
                } else if (typeof window.kasware !== 'undefined') {
                    accounts = await window.kasware.requestAccounts();
                } else {
                    throw new Error('Kastle wallet not found. Please install Kastle wallet or Kasware.');
                }
                break;
                
            case 'kasware':
                if (typeof window.kasware !== 'undefined') {
                    accounts = await window.kasware.requestAccounts();
                } else {
                    throw new Error('KasWare wallet not found. Please install KasWare.');
                }
                break;
                
            case 'metamask':
                if (typeof window.ethereum !== 'undefined') {
                    // Get accounts - MetaMask will show account selector if not already connected
                    accounts = await window.ethereum.request({
                        method: 'eth_requestAccounts'
                    });
                } else {
                    throw new Error('MetaMask not found. Please install MetaMask.');
                }
                break;
                
            default:
                throw new Error(`Unsupported wallet type: ${walletType}`);
        }
        
        if (!accounts || accounts.length === 0) {
            throw new Error('No accounts found in wallet');
        }
        
        return accounts[0];
    }
    
    async requestNonce(walletAddress) {
        const response = await fetch('/api/auth/nonce', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                wallet_address: walletAddress
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to get authentication challenge');
        }
        
        return data.message;
    }
    
    async signMessage(message, walletAddress, walletType) {
        let signature;
        
        switch(walletType.toLowerCase()) {
            case 'kastle':
                if (typeof window.kastle !== 'undefined') {
                    signature = await window.kastle.request({
                        method: 'kas_signMessage',
                        params: {
                            message: message,
                            address: walletAddress
                        }
                    });
                } else if (typeof window.kasware !== 'undefined') {
                    signature = await window.kasware.signMessage(message, 'utf8');
                } else {
                    throw new Error('Kaspa wallet not available for signing');
                }
                break;
                
            case 'kasware':
                if (typeof window.kasware !== 'undefined') {
                    signature = await window.kasware.signMessage(message, 'utf8');
                } else {
                    throw new Error('KasWare wallet not available for signing');
                }
                break;
                
            case 'metamask':
                if (typeof window.ethereum !== 'undefined') {
                    signature = await window.ethereum.request({
                        method: 'personal_sign',
                        params: [message, walletAddress],
                    });
                } else {
                    throw new Error('MetaMask not available for signing');
                }
                break;
                
            default:
                throw new Error(`Unsupported wallet type: ${walletType}`);
        }
        
        if (!signature) {
            throw new Error('Signature request was cancelled or failed');
        }
        
        return signature;
    }
    
    async verifySignature(walletAddress, signature, walletType) {
        const response = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                wallet_address: walletAddress,
                signature: signature,
                wallet_type: walletType
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Signature verification failed');
        }
        
        return data;
    }
    
    async connectWallet(walletType) {
        try {
            console.log(`[WalletManager] Starting connection flow for ${walletType}`);
            this.updateUIState('connecting', walletType);
            
            if (!this.detectWallet(walletType)) {
                throw new Error(`${walletType} wallet not detected. Please install it first.`);
            }
            
            console.log(`[WalletManager] Requesting accounts from ${walletType}...`);
            const walletAddress = await this.requestAccounts(walletType);
            console.log(`[WalletManager] Got wallet address: ${walletAddress}`);
            
            if (walletType.toLowerCase() === 'metamask') {
                console.log('[WalletManager] Handling MetaMask network...');
                await this.handleMetaMaskNetwork();
            }
            
            console.log('[WalletManager] Requesting nonce from backend...');
            const nonce = await this.requestNonce(walletAddress);
            console.log('[WalletManager] Got nonce, requesting signature...');
            
            const signature = await this.signMessage(nonce, walletAddress, walletType);
            console.log('[WalletManager] Got signature, verifying...');
            
            const verifyResult = await this.verifySignature(walletAddress, signature, walletType);
            console.log('[WalletManager] Verification result:', verifyResult);
            
            const walletData = {
                address: walletAddress,
                wallet_type: walletType.toLowerCase()
            };
            
            this.connectedWallet = walletData;
            this.saveWallet(walletData);
            this.startSessionPolling();
            
            console.log('[WalletManager] Connection successful!', walletData);
            this.updateUIState('connected', walletType, walletData);
            this.trigger('connect', walletData);
            
            return walletData;
            
        } catch (error) {
            console.error('[WalletManager] Connection error:', error);
            this.updateUIState('error', walletType, null, error.message);
            this.trigger('error', { type: 'connect', error: error.message });
            throw error;
        }
    }
    
    async disconnectWallet() {
        try {
            console.log('[WalletManager] Starting disconnect...');
            
            const previousWallet = this.connectedWallet;
            
            // If MetaMask, revoke permissions to clear cached account (with timeout)
            if (previousWallet && previousWallet.wallet_type === 'metamask' && typeof window.ethereum !== 'undefined') {
                try {
                    console.log('[WalletManager] Revoking MetaMask permissions...');
                    
                    // Add 2-second timeout to prevent hanging
                    const revokePromise = window.ethereum.request({
                        method: 'wallet_revokePermissions',
                        params: [{ eth_accounts: {} }]
                    });
                    
                    const timeoutPromise = new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('Timeout')), 2000)
                    );
                    
                    await Promise.race([revokePromise, timeoutPromise]);
                    console.log('[WalletManager] MetaMask permissions revoked successfully');
                } catch (revokeError) {
                    // Permissions API might not be supported or timed out
                    console.warn('[WalletManager] Could not revoke MetaMask permissions:', revokeError.message);
                }
            }
            
            const response = await fetch('/api/disconnect-wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.connectedWallet = null;
                this.clearSavedWallet();
                this.stopSessionPolling();
                
                console.log('[WalletManager] Disconnect successful');
                this.updateUIState('disconnected');
                this.trigger('disconnect', previousWallet);
                
                return true;
            } else {
                throw new Error(data.error || 'Failed to disconnect wallet');
            }
            
        } catch (error) {
            console.error('[WalletManager] Disconnect error:', error);
            this.trigger('error', { type: 'disconnect', error: error.message });
            throw error;
        }
    }
    
    async switchWallet(newWalletType) {
        try {
            const previousWallet = this.connectedWallet;
            
            await this.disconnectWallet();
            
            const newWallet = await this.connectWallet(newWalletType);
            
            this.trigger('switch', { from: previousWallet, to: newWallet });
            
            return newWallet;
            
        } catch (error) {
            console.error('Switch wallet error:', error);
            this.trigger('error', { type: 'switch', error: error.message });
            throw error;
        }
    }
    
    async handleMetaMaskNetwork() {
        try {
            const chainId = await window.ethereum.request({ method: 'eth_chainId' });
            
            if (chainId.toLowerCase() !== this.KASPLEX_TESTNET.chainId.toLowerCase()) {
                const switchNetwork = confirm(
                    'Would you like to switch to Kasplex Network Testnet for the best experience? ' +
                    '(You can also continue with your current network)'
                );
                
                if (switchNetwork) {
                    try {
                        await this.addKasplexNetwork();
                        await window.ethereum.request({
                            method: 'wallet_switchEthereumChain',
                            params: [{ chainId: this.KASPLEX_TESTNET.chainId }],
                        });
                        console.log('Successfully switched to Kasplex network');
                    } catch (switchError) {
                        console.warn('Failed to switch to Kasplex network:', switchError);
                    }
                }
            }
        } catch (error) {
            console.warn('Network check failed:', error);
        }
    }
    
    async addKasplexNetwork() {
        try {
            await window.ethereum.request({
                method: 'wallet_addEthereumChain',
                params: [this.KASPLEX_TESTNET]
            });
            console.log('Kasplex network added successfully');
        } catch (error) {
            if (error.code === 4902) {
                console.log('Kasplex network already exists');
            } else {
                throw error;
            }
        }
    }
    
    async checkSession() {
        try {
            const response = await fetch('/api/auth/session', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                console.warn('[WalletManager] Session check failed with status:', response.status);
                return false;
            }
            
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.warn('[WalletManager] Session check returned non-JSON response, skipping check');
                return true;
            }
            
            const data = await response.json();
            
            if (!data.authenticated) {
                console.log('[WalletManager] Session expired, disconnecting wallet');
                this.connectedWallet = null;
                this.clearSavedWallet();
                this.stopSessionPolling();
                this.updateUIState('disconnected');
                this.trigger('disconnect', { reason: 'session_expired' });
            }
            
            return data.authenticated;
            
        } catch (error) {
            console.warn('[WalletManager] Session check error (non-critical):', error.message);
            return true;
        }
    }
    
    startSessionPolling(interval = 30000) {
        this.stopSessionPolling();
        
        this.sessionCheckInterval = setInterval(() => {
            this.checkSession();
        }, interval);
    }
    
    stopSessionPolling() {
        if (this.sessionCheckInterval) {
            clearInterval(this.sessionCheckInterval);
            this.sessionCheckInterval = null;
        }
    }
    
    saveWallet(walletData) {
        try {
            localStorage.setItem('connected_wallet', JSON.stringify(walletData));
        } catch (error) {
            console.error('Failed to save wallet to localStorage:', error);
        }
    }
    
    getSavedWallet() {
        try {
            const saved = localStorage.getItem('connected_wallet');
            return saved ? JSON.parse(saved) : null;
        } catch (error) {
            console.error('Failed to get saved wallet from localStorage:', error);
            return null;
        }
    }
    
    clearSavedWallet() {
        try {
            localStorage.removeItem('connected_wallet');
        } catch (error) {
            console.error('Failed to clear saved wallet from localStorage:', error);
        }
    }
    
    getConnectedWallet() {
        return this.connectedWallet;
    }
    
    isConnected() {
        return this.connectedWallet !== null;
    }
    
    openWalletModal() {
        const modal = document.getElementById('walletModal');
        if (modal) {
            modal.classList.add('active');
        }
    }
    
    closeWalletModal() {
        const modal = document.getElementById('walletModal');
        if (modal) {
            modal.classList.remove('active');
        }
    }
    
    updateUIState(state, walletType = null, walletData = null, errorMessage = null) {
        const stateEvent = new CustomEvent('walletStateChange', {
            detail: {
                state: state,
                walletType: walletType,
                walletData: walletData,
                errorMessage: errorMessage
            }
        });
        window.dispatchEvent(stateEvent);
        
        switch(state) {
            case 'connecting':
                this.updateConnectingUI(walletType);
                break;
            case 'connected':
                this.updateConnectedUI(walletData);
                break;
            case 'disconnected':
                this.updateDisconnectedUI();
                break;
            case 'error':
                this.updateErrorUI(errorMessage);
                break;
        }
    }
    
    updateConnectingUI(walletType) {
        const buttons = document.querySelectorAll('.wallet-button');
        buttons.forEach(btn => {
            btn.classList.add('connecting');
            btn.disabled = true;
        });
        
        const statusEl = document.getElementById('wallet-status');
        if (statusEl) {
            statusEl.textContent = `Connecting to ${walletType}...`;
            statusEl.className = 'wallet-status connecting';
        }
    }
    
    updateConnectedUI(walletData) {
        const buttons = document.querySelectorAll('.wallet-button');
        buttons.forEach(btn => {
            btn.classList.remove('connecting');
            btn.disabled = false;
        });
        
        this.closeWalletModal();
        
        const statusEl = document.getElementById('wallet-status');
        if (statusEl) {
            statusEl.textContent = `Connected: ${this.shortenAddress(walletData.address)}`;
            statusEl.className = 'wallet-status connected';
        }
        
        const connectBtn = document.getElementById('connect-wallet-btn');
        if (connectBtn) {
            connectBtn.textContent = this.shortenAddress(walletData.address);
            connectBtn.classList.add('connected');
        }
        
        const walletAddressEl = document.querySelector('.wallet-address');
        if (walletAddressEl) {
            walletAddressEl.textContent = this.shortenAddress(walletData.address);
        }
    }
    
    updateDisconnectedUI() {
        const statusEl = document.getElementById('wallet-status');
        if (statusEl) {
            statusEl.textContent = 'Not connected';
            statusEl.className = 'wallet-status disconnected';
        }
        
        const connectBtn = document.getElementById('connect-wallet-btn');
        if (connectBtn) {
            connectBtn.textContent = 'Connect Wallet';
            connectBtn.classList.remove('connected');
        }
        
        const walletAddressEl = document.querySelector('.wallet-address');
        if (walletAddressEl) {
            walletAddressEl.textContent = '';
        }
    }
    
    updateErrorUI(errorMessage) {
        const buttons = document.querySelectorAll('.wallet-button');
        buttons.forEach(btn => {
            btn.classList.remove('connecting');
            btn.disabled = false;
        });
        
        const errorEl = document.getElementById('error-message');
        const errorTextEl = document.getElementById('error-text');
        
        if (errorEl && errorTextEl) {
            errorTextEl.textContent = errorMessage;
            errorEl.style.display = 'block';
            
            setTimeout(() => {
                errorEl.style.display = 'none';
            }, 5000);
        }
    }
    
    shortenAddress(address) {
        if (!address) return '';
        if (address.length < 12) return address;
        return `${address.slice(0, 6)}...${address.slice(-4)}`;
    }
    
    on(event, handler) {
        if (this.eventHandlers[event]) {
            this.eventHandlers[event].push(handler);
        }
    }
    
    off(event, handler) {
        if (this.eventHandlers[event]) {
            const index = this.eventHandlers[event].indexOf(handler);
            if (index > -1) {
                this.eventHandlers[event].splice(index, 1);
            }
        }
    }
    
    trigger(event, data) {
        if (this.eventHandlers[event]) {
            this.eventHandlers[event].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in ${event} event handler:`, error);
                }
            });
        }
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = WalletManager;
}

if (typeof window !== 'undefined') {
    window.WalletManager = WalletManager;
}
