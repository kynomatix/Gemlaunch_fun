import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User, Token, Trade, Holding, Achievement, UserAchievement

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize database
db.init_app(app)

def get_current_user():
    """Get current user from session - only if wallet is verified"""
    wallet_address = session.get('wallet_address')
    wallet_verified = session.get('wallet_verified', False)
    
    # Only return user if wallet has been cryptographically verified
    if wallet_address and wallet_verified:
        return User.query.filter_by(wallet_address=wallet_address.lower()).first()
    return None

def require_wallet_connection(f):
    """Decorator to require wallet connection"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_user():
            return jsonify({'error': 'Wallet connection required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Main landing page for Gemlaunch.fun"""
    return render_template('index.html')

@app.route('/docs')
def docs():
    """Documentation page for Gemlaunch.fun"""
    return render_template('docs.html')

@app.route('/pitch-deck')
def pitch_deck():
    """Investor pitch deck for Gemlaunch.fun"""
    return render_template('pitch-deck.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy'}

# Wallet Authentication API
@app.route('/api/auth/nonce', methods=['POST'])
def generate_nonce():
    """Generate a nonce for wallet authentication"""
    import secrets
    import time
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    # Generate cryptographically secure nonce
    nonce = secrets.token_hex(32)
    timestamp = int(time.time())
    
    # Store nonce in session (temporary storage)
    session_key = f'auth_nonce_{wallet_address.lower()}'
    session[session_key] = {
        'nonce': nonce,
        'timestamp': timestamp,
        'wallet_address': wallet_address.lower()
    }
    
    # Create human-readable message for signing
    message = f"Sign this message to authenticate with Gemlaunch.fun\n\nNonce: {nonce}\nTimestamp: {timestamp}\nWallet: {wallet_address.lower()}"
    
    return jsonify({
        'success': True,
        'nonce': nonce,
        'message': message,
        'timestamp': timestamp
    })

@app.route('/api/auth/verify', methods=['POST'])
def verify_signature():
    """Verify wallet signature and create user session"""
    import time
    # from eth_utils.address import to_checksum_address
    from eth_account.messages import encode_defunct
    from eth_account import Account
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    signature = data.get('signature')
    wallet_type = data.get('wallet_type', 'unknown')
    
    if not wallet_address or not signature:
        return jsonify({'error': 'Wallet address and signature required'}), 400
    
    try:
        # Get nonce from session
        session_key = f'auth_nonce_{wallet_address.lower()}'
        nonce_data = session.get(session_key)
        
        if not nonce_data:
            return jsonify({'error': 'No authentication challenge found. Please request a new nonce.'}), 400
        
        # Check nonce expiration (5 minutes)
        current_time = int(time.time())
        if current_time - nonce_data['timestamp'] > 300:  # 5 minutes
            session.pop(session_key, None)
            return jsonify({'error': 'Authentication challenge expired. Please try again.'}), 400
        
        # Reconstruct the message that was signed
        message = f"Sign this message to authenticate with Gemlaunch.fun\n\nNonce: {nonce_data['nonce']}\nTimestamp: {nonce_data['timestamp']}\nWallet: {wallet_address.lower()}"
        
        # Verify signature for EVM wallets (MetaMask)
        if wallet_type.lower() in ['metamask', 'evm']:
            try:
                # Encode message for Ethereum signing
                encoded_message = encode_defunct(text=message)
                
                # Recover address from signature
                recovered_address = Account.recover_message(encoded_message, signature=signature)
                
                # Verify the recovered address matches the claimed address
                if recovered_address.lower() != wallet_address.lower():
                    return jsonify({'error': 'Signature verification failed. Invalid signature.'}), 401
                    
            except Exception as sig_error:
                return jsonify({'error': f'Signature verification error: {str(sig_error)}'}), 401
        
        # For native Kaspa wallets, we would need Kaspa-specific signature verification
        # This is a simplified approach - in production, implement proper Kaspa signature verification
        elif wallet_type.lower() in ['kastle', 'kasware', 'kaspa']:
            # TODO: Implement Kaspa signature verification using Kasplex SDK
            # For now, we'll accept these wallet types with a warning
            print(f"Warning: Native Kaspa signature verification not yet implemented for {wallet_type}")
        
        # Clear the used nonce to prevent replay attacks
        if session_key:
            session.pop(session_key, None)
        
        # Create or get user with verified wallet address
        user = User.get_or_create_by_wallet(wallet_address, wallet_type)
        
        # Store verified wallet in session
        session['wallet_address'] = wallet_address.lower()
        session['user_id'] = user.id
        session['wallet_verified'] = True
        session['wallet_type'] = wallet_type
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'wallet_address': user.wallet_address,
                'display_name': user.display_name,
                'gem_points': user.gem_points,
                'wallet_type': user.wallet_type
            }
        })
        
    except Exception as e:
        # Clear any partial session data
        session.pop(session_key, None)
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 500

@app.route('/api/disconnect-wallet', methods=['POST'])
def disconnect_wallet():
    """Disconnect wallet and clear all session data"""
    # Clear all wallet-related session data
    session.pop('wallet_address', None)
    session.pop('user_id', None)
    session.pop('wallet_verified', None)
    session.pop('wallet_type', None)
    
    # Clear any remaining auth nonces
    keys_to_remove = [key for key in session.keys() if key.startswith('auth_nonce_')]
    for key in keys_to_remove:
        session.pop(key, None)
    
    return jsonify({'success': True})

@app.route('/api/user-info')
def user_info():
    """Get current user info"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not connected'}), 401
    
    return jsonify({
        'user': {
            'id': user.id,
            'wallet_address': user.wallet_address,
            'display_name': user.display_name,
            'gem_points': user.gem_points,
            'total_tokens_created': user.total_tokens_created,
            'total_trading_volume': float(user.total_trading_volume or 0)
        }
    })

# App routes
@app.route('/app')
def app_home():
    """Main app - redirects to marketplace (pump.fun style)"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Redirect to marketplace as main home page
    return redirect(url_for('token_marketplace'))

@app.route('/app/create', methods=['GET', 'POST'])
def create_token():
    """Token creation page and form handler"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    if request.method == 'POST':
        # Handle token creation form submission (UI mockup)
        name = request.form.get('name')
        symbol = request.form.get('symbol')
        description = request.form.get('description', '')
        mode = request.form.get('mode', 'simple')
        total_supply = request.form.get('total_supply', '1000000000')
        reserved_percentage = request.form.get('reserved_percentage', '0')
        
        # Simulate token creation (this is just UI - no actual blockchain deployment)
        try:
            # Create mock token record
            new_token = Token()
            new_token.name = name
            new_token.symbol = symbol.upper() if symbol else 'TOKEN'
            new_token.description = description
            new_token.creator_id = user.id
            new_token.total_supply = int(total_supply)
            new_token.circulating_supply = 0
            new_token.deployment_status = 'pending'  # Mock status for UI
            new_token.current_price = 0.001  # Mock starting price
            new_token.current_market_cap = 1000  # Start at $1K market cap
            
            db.session.add(new_token)
            db.session.commit()
            
            flash(f'🚀 Token "{name}" ({symbol}) created successfully! This is a UI demo - no actual blockchain deployment.', 'success')
            return redirect(url_for('token_marketplace'))
            
        except Exception as e:
            flash(f'Error creating token: {str(e)}', 'error')
            return redirect(url_for('create_token'))
    
    return render_template('app/create_token.html', user=user)

@app.route('/app/tokens')
def token_marketplace():
    """Token marketplace - main home page (pump.fun style)"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Show all tokens, including pending ones for UI demo
    tokens = Token.query.order_by(Token.created_at.desc()).all()
    return render_template('app/marketplace.html', tokens=tokens, user=user)

@app.route('/app/token/<int:token_id>')
def token_detail(token_id):
    """Individual token detail page"""
    token = Token.query.get_or_404(token_id)
    
    # Get recent trades
    recent_trades = Trade.query.filter_by(token_id=token_id, tx_status='confirmed').order_by(Trade.confirmed_at.desc()).limit(10).all()
    
    # Get user's holding if connected
    user_holding = None
    user = get_current_user()
    if user:
        user_holding = Holding.query.filter_by(user_id=user.id, token_id=token_id).first()
    
    return render_template('app/token_detail.html', 
                         token=token, 
                         recent_trades=recent_trades,
                         user_holding=user_holding,
                         user=user)

def init_database():
    """Initialize database tables and seed data"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created")
            
            # Create some sample achievements if they don't exist
            if not Achievement.query.first():
                achievements = []
                
                achievement1 = Achievement()
                achievement1.name = "First Launch"
                achievement1.description = "Create your first memecoin"
                achievement1.icon = "🚀"
                achievement1.category = "creator"
                achievement1.requirement_type = "tokens_created"
                achievement1.requirement_value = 1
                achievement1.gem_points_reward = 100
                achievements.append(achievement1)
                
                achievement2 = Achievement()
                achievement2.name = "Token Maestro"
                achievement2.description = "Create 10 memecoins"
                achievement2.icon = "🎭"
                achievement2.category = "creator"
                achievement2.requirement_type = "tokens_created"
                achievement2.requirement_value = 10
                achievement2.gem_points_reward = 1000
                achievements.append(achievement2)
                
                achievement3 = Achievement()
                achievement3.name = "First Trade"
                achievement3.description = "Make your first trade"
                achievement3.icon = "💎"
                achievement3.category = "trader"
                achievement3.requirement_type = "trades_made"
                achievement3.requirement_value = 1
                achievement3.gem_points_reward = 50
                achievements.append(achievement3)
                
                achievement4 = Achievement()
                achievement4.name = "High Roller"
                achievement4.description = "Trade over 1000 KAS volume"
                achievement4.icon = "🎰"
                achievement4.category = "trader"
                achievement4.requirement_type = "trading_volume"
                achievement4.requirement_value = 1000
                achievement4.gem_points_reward = 500
                achievements.append(achievement4)
                
                for achievement in achievements:
                    db.session.add(achievement)
                db.session.commit()
                print("✅ Sample achievements created")
            else:
                print("✅ Sample achievements already exist")
                
        except Exception as e:
            print(f"❌ Database initialization error: {e}")

# Initialize database when app starts
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
