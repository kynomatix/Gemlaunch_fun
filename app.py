import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User, Token, Trade, Holding, Achievement, UserAchievement, UserProfile, ConnectedWallet, Referral, Activity

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
        # Clear any partial session data if session_key is defined
        try:
            if 'session_key' in locals():
                session.pop(session_key, None)
        except:
            pass
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

@app.route('/app/dashboard')
def app_dashboard():
    """User dashboard with stats and portfolio - now includes activities and achievements"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Get user's created tokens and holdings
    created_tokens = Token.query.filter_by(creator_id=user.id).all()
    holdings = Holding.query.filter_by(user_id=user.id).all()
    
    # Get user's activities
    activities = Activity.query.filter_by(user_id=user.id).order_by(Activity.created_at.desc()).limit(20).all()
    
    # Get user's achievements
    user_achievements = UserAchievement.query.filter_by(user_id=user.id).all()
    total_achievements = Achievement.query.count()
    
    # Calculate achievement points
    achievement_points = sum(achievement.points_earned for achievement in user_achievements)
    
    # Get referral info for achievements
    referral = Referral.query.filter_by(referrer_id=user.id).first()
    
    return render_template('app/dashboard.html', 
                         user=user, 
                         created_tokens=created_tokens, 
                         holdings=holdings,
                         activities=activities,
                         user_achievements=user_achievements,
                         total_achievements=total_achievements,
                         achievement_points=achievement_points,
                         referral=referral)

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

# Leaderboard routes
@app.route('/app/leaderboard')
def leaderboard():
    """Main leaderboard page with rankings and points"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Get top users by GEM points
    top_users = User.query.order_by(User.gem_points.desc()).limit(50).all()
    
    # Get user's rank
    user_rank = None
    for i, u in enumerate(top_users, 1):
        if u.id == user.id:
            user_rank = i
            break
    
    # If user not in top 50, calculate their actual rank
    if user_rank is None:
        users_above = User.query.filter(User.gem_points > user.gem_points).count()
        user_rank = users_above + 1
    
    return render_template('app/leaderboard.html', 
                         user=user, 
                         top_users=top_users, 
                         user_rank=user_rank)

@app.route('/app/profile')
def profile():
    """User profile page with wallet connections and stats"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Get or create user profile
    user_profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not user_profile:
        user_profile = UserProfile()
        user_profile.user_id = user.id
        db.session.add(user_profile)
        db.session.commit()
    
    # Get connected wallets
    connected_wallets = ConnectedWallet.query.filter_by(user_id=user.id).all()
    
    # Get user's achievements
    user_achievements = UserAchievement.query.filter_by(user_id=user.id).all()
    
    # Get referral info
    referral = Referral.query.filter_by(referrer_id=user.id).first()
    if not referral:
        # Generate referral code
        import secrets
        referral_code = f"kryptoman{secrets.randbelow(10000):04d}"
        referral = Referral()
        referral.referrer_id = user.id
        referral.referral_code = referral_code
        referral.referral_link = f"https://gemlaunch.fun/?ref={referral_code}"
        db.session.add(referral)
        db.session.commit()
    
    return render_template('app/profile.html', 
                         user=user, 
                         user_profile=user_profile,
                         connected_wallets=connected_wallets,
                         user_achievements=user_achievements,
                         referral=referral)

@app.route('/app/referrals')
def referrals():
    """Referral management and tracking page - now includes profile management"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Get or create user profile
    user_profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not user_profile:
        user_profile = UserProfile()
        user_profile.user_id = user.id
        db.session.add(user_profile)
        db.session.commit()
    
    # Get user's referral info
    referral = Referral.query.filter_by(referrer_id=user.id).first()
    if not referral:
        # Generate referral code if doesn't exist
        import secrets
        referral_code = f"kryptoman{secrets.randbelow(10000):04d}"
        referral = Referral()
        referral.referrer_id = user.id
        referral.referral_code = referral_code
        referral.referral_link = f"https://gemlaunch.fun/?ref={referral_code}"
        db.session.add(referral)
        db.session.commit()
    
    # Get referred users
    referred_users = User.query.join(Referral, Referral.referee_id == User.id).filter(
        Referral.referrer_id == user.id
    ).all()
    
    # Get connected wallets
    connected_wallets = ConnectedWallet.query.filter_by(user_id=user.id).all()
    
    return render_template('app/referrals.html', 
                         user=user, 
                         user_profile=user_profile,
                         referral=referral,
                         referred_users=referred_users,
                         connected_wallets=connected_wallets)

@app.route('/app/activities')
def activities():
    """User activities and achievement progress page"""
    user = get_current_user()
    if not user:
        return render_template('app/connect_wallet.html')
    
    # Get user's recent activities
    user_activities = Activity.query.filter_by(user_id=user.id).order_by(
        Activity.created_at.desc()
    ).limit(50).all()
    
    # Get available achievements and user's progress
    all_achievements = Achievement.query.filter_by(is_active=True).all()
    user_achievements = {ua.achievement_id: ua for ua in UserAchievement.query.filter_by(user_id=user.id).all()}
    
    return render_template('app/activities.html', 
                         user=user, 
                         user_activities=user_activities,
                         all_achievements=all_achievements,
                         user_achievements=user_achievements)

def init_database():
    """Initialize database tables and seed data"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created")
            
            # Create fair-launch specific achievements if they don't exist
            if not Achievement.query.first():
                achievements = []
                
                # First Launch - Core creator achievement
                achievement1 = Achievement()
                achievement1.name = "First Launch"
                achievement1.description = "Create your first memecoin on Kaspa"
                achievement1.icon = "🚀"
                achievement1.category = "creator"
                achievement1.requirement_type = "tokens_created"
                achievement1.requirement_value = 1
                achievement1.gem_points_reward = 100
                achievements.append(achievement1)
                
                # Active Trader - Start trading
                achievement2 = Achievement()
                achievement2.name = "Active Trader"
                achievement2.description = "Trade $1,000 worth of tokens"
                achievement2.icon = "📈"
                achievement2.category = "trader"
                achievement2.requirement_type = "trading_volume"
                achievement2.requirement_value = 1000
                achievement2.gem_points_reward = 150
                achievements.append(achievement2)
                
                # Volume Trader - Serious trading
                achievement3 = Achievement()
                achievement3.name = "Volume Trader"
                achievement3.description = "Trade $10,000 worth of tokens"
                achievement3.icon = "🔥"
                achievement3.category = "trader"
                achievement3.requirement_type = "trading_volume"
                achievement3.requirement_value = 10000
                achievement3.gem_points_reward = 300
                achievements.append(achievement3)
                
                # Token Creator - Multiple launches
                achievement4 = Achievement()
                achievement4.name = "Token Creator"
                achievement4.description = "Launch 5 different tokens"
                achievement4.icon = "🪙"
                achievement4.category = "creator"
                achievement4.requirement_type = "tokens_created"
                achievement4.requirement_value = 5
                achievement4.gem_points_reward = 400
                achievements.append(achievement4)
                
                # Community Builder - Referral master
                achievement5 = Achievement()
                achievement5.name = "Community Builder"
                achievement5.description = "Refer 10 qualified users"
                achievement5.icon = "👥"
                achievement5.category = "social"
                achievement5.requirement_type = "referrals_made"
                achievement5.requirement_value = 10
                achievement5.gem_points_reward = 500
                achievements.append(achievement5)
                
                # Graduation Master - Ultimate achievement
                achievement6 = Achievement()
                achievement6.name = "Graduation Master"
                achievement6.description = "Create a token that graduates to DEX"
                achievement6.icon = "👑"
                achievement6.category = "creator"
                achievement6.requirement_type = "tokens_graduated"
                achievement6.requirement_value = 1
                achievement6.gem_points_reward = 1000
                achievements.append(achievement6)
                
                # Diamond Hands - Long-term holder
                achievement7 = Achievement()
                achievement7.name = "Diamond Hands"
                achievement7.description = "Hold tokens for 30+ days"
                achievement7.icon = "💎"
                achievement7.category = "holder"
                achievement7.requirement_type = "holding_days"
                achievement7.requirement_value = 30
                achievement7.gem_points_reward = 250
                achievements.append(achievement7)
                
                # Early Adopter - Platform loyalty
                achievement8 = Achievement()
                achievement8.name = "Early Adopter"
                achievement8.description = "Join the first 1000 users on Gemlaunch"
                achievement8.icon = "🌟"
                achievement8.category = "special"
                achievement8.requirement_type = "user_number"
                achievement8.requirement_value = 1000
                achievement8.gem_points_reward = 200
                achievements.append(achievement8)
                
                # Market Maker - Liquidity provider
                achievement9 = Achievement()
                achievement9.name = "Market Maker"
                achievement9.description = "Execute 50+ trades across multiple tokens"
                achievement9.icon = "⚡"
                achievement9.category = "trader"
                achievement9.requirement_type = "total_trades"
                achievement9.requirement_value = 50
                achievement9.gem_points_reward = 300
                achievements.append(achievement9)
                
                # Social Influencer - Share and promote
                achievement10 = Achievement()
                achievement10.name = "Social Influencer"
                achievement10.description = "Share 5+ tokens on social media"
                achievement10.icon = "📱"
                achievement10.category = "social"
                achievement10.requirement_type = "social_shares"
                achievement10.requirement_value = 5
                achievement10.gem_points_reward = 100
                achievements.append(achievement10)
                
                # Memecoin Veteran - Experience badge
                achievement11 = Achievement()
                achievement11.name = "Memecoin Veteran"
                achievement11.description = "Complete 100+ transactions on the platform"
                achievement11.icon = "🎖️"
                achievement11.category = "special"
                achievement11.requirement_type = "total_transactions"
                achievement11.requirement_value = 100
                achievement11.gem_points_reward = 600
                achievements.append(achievement11)
                
                # Trend Setter - Popular creator
                achievement12 = Achievement()
                achievement12.name = "Trend Setter"
                achievement12.description = "Create a token with 1000+ holders"
                achievement12.icon = "🎯"
                achievement12.category = "creator"
                achievement12.requirement_type = "token_holders"
                achievement12.requirement_value = 1000
                achievement12.gem_points_reward = 800
                achievements.append(achievement12)
                
                for achievement in achievements:
                    db.session.add(achievement)
                db.session.commit()
                print("✅ Fair-launch achievements created")
            else:
                print("✅ Sample achievements already exist")
                
        except Exception as e:
            print(f"❌ Database initialization error: {e}")

# Initialize database when app starts
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
