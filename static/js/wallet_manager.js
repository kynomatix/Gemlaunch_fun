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
    
    init() {
        const savedWallet = this.getSavedWallet();
        if (savedWallet) {
            this.connectedWallet = savedWallet;
            this.startSessionPolling();
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
            this.updateUIState('connecting', walletType);
            
            if (!this.detectWallet(walletType)) {
                throw new Error(`${walletType} wallet not detected. Please install it first.`);
            }
            
            const walletAddress = await this.requestAccounts(walletType);
            
            if (walletType.toLowerCase() === 'metamask') {
                await this.handleMetaMaskNetwork();
            }
            
            const nonce = await this.requestNonce(walletAddress);
            
            const signature = await this.signMessage(nonce, walletAddress, walletType);
            
            const verifyResult = await this.verifySignature(walletAddress, signature, walletType);
            
            const walletData = {
                address: walletAddress,
                wallet_type: walletType.toLowerCase()
            };
            
            this.connectedWallet = walletData;
            this.saveWallet(walletData);
            this.startSessionPolling();
            
            this.updateUIState('connected', walletType, walletData);
            this.trigger('connect', walletData);
            
            return walletData;
            
        } catch (error) {
            console.error('Wallet connection error:', error);
            this.updateUIState('error', walletType, null, error.message);
            this.trigger('error', { type: 'connect', error: error.message });
            throw error;
        }
    }
    
    async disconnectWallet() {
        try {
            const response = await fetch('/api/disconnect-wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                const previousWallet = this.connectedWallet;
                this.connectedWallet = null;
                this.clearSavedWallet();
                this.stopSessionPolling();
                
                this.updateUIState('disconnected');
                this.trigger('disconnect', previousWallet);
                
                return true;
            } else {
                throw new Error(data.error || 'Failed to disconnect wallet');
            }
            
        } catch (error) {
            console.error('Disconnect error:', error);
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
            
            const data = await response.json();
            
            if (!data.authenticated) {
                this.connectedWallet = null;
                this.clearSavedWallet();
                this.stopSessionPolling();
                this.updateUIState('disconnected');
                this.trigger('disconnect', { reason: 'session_expired' });
            }
            
            return data.authenticated;
            
        } catch (error) {
            console.error('Session check error:', error);
            return false;
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
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }
    
    closeWalletModal() {
        const modal = document.getElementById('walletModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
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
    window.walletManager = new WalletManager();
}
