import os
import logging
import secrets
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
from models import db, User, Token, Trade, Holding, Achievement, UserAchievement, UserProfile, ConnectedWallet, Referral, Activity
import models_extended

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Image processing utility functions
def process_profile_image(image_file, user_id):
    """Process and compress profile image using Pillow"""
    try:
        # Open and validate image
        image = Image.open(image_file)
        
        # Convert to RGB if necessary (handles RGBA, P, etc.)
        if image.mode != 'RGB':
            if image.mode == 'RGBA':
                # Create a white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = background
            else:
                image = image.convert('RGB')
        
        # Resize to 150x150 with center crop
        image = ImageOps.fit(image, (150, 150), Image.Resampling.LANCZOS, 0, (0.5, 0.5))
        
        # Generate unique filename
        filename = f"{user_id}_{secrets.token_hex(8)}.webp"
        
        # Ensure upload directory exists
        upload_dir = os.path.join('static', 'uploads', 'profile')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save as WebP with good compression
        file_path = os.path.join(upload_dir, filename)
        image.save(file_path, 'WEBP', quality=80, optimize=True)
        
        # Return relative path for database storage
        return f"uploads/profile/{filename}"
        
    except Exception as e:
        logging.error(f"Error processing image: {str(e)}")
        return None

def cleanup_old_avatar(old_avatar_path):
    """Remove old avatar file if it exists"""
    if not old_avatar_path:
        return
        
    try:
        file_path = os.path.join('static', old_avatar_path)
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Cleaned up old avatar: {file_path}")
    except Exception as e:
        logging.error(f"Error cleaning up old avatar: {str(e)}")

def validate_image_file(file):
    """Validate uploaded image file"""
    if not file or not file.filename:
        return False, "No file selected"
    
    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    filename = secure_filename(file.filename.lower())
    if '.' not in filename or filename.rsplit('.', 1)[1] not in allowed_extensions:
        return False, "Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WebP files."
    
    # Check file size (5MB limit)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        return False, "File size must be less than 5MB"
    
    return True, "Valid file"

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
        # Clear any partial session data if session_key was defined
        try:
            for key in list(session.keys()):
                if key.startswith('auth_nonce_'):
                    session.pop(key, None)
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
        # For HTMX requests, return minimal content
        if request.headers.get('HX-Request'):
            return '<div class="connect-wallet-container"><h2>Please connect your wallet</h2><a href="/app" class="btn btn-primary">Connect Wallet</a></div>'
        return render_template('app/connect_wallet.html')
    
    # Get user's created tokens and holdings
    created_tokens = Token.query.filter_by(creator_id=user.id).all()
    holdings = Holding.query.filter_by(user_id=user.id).all()
    
    # Get user's activities
    activities = Activity.query.filter_by(user_id=user.id).order_by(Activity.created_at.desc()).limit(20).all()
    
    # Get user's achievements
    user_achievements = UserAchievement.query.filter_by(user_id=user.id).all()
    user_achievement_ids = [ua.achievement_id for ua in user_achievements]
    
    # Get all achievements for display
    all_achievements = Achievement.query.filter_by(is_active=True).order_by(
        Achievement.category, Achievement.gem_points_reward
    ).all()
    
    total_achievements = len(all_achievements)
    
    # Calculate achievement points
    achievement_points = sum(ua.achievement.gem_points_reward for ua in user_achievements)
    
    # Get referral info for achievements
    referral = Referral.query.filter_by(referrer_id=user.id).first()
    
    # Check if this is an HTMX request
    if request.headers.get('HX-Request'):
        # Return HTMX-optimized template
        return render_template('app/dashboard_htmx.html',
                             user=user, 
                             created_tokens=created_tokens, 
                             holdings=holdings,
                             activities=activities,
                             user_achievements=user_achievements,
                             user_achievement_ids=user_achievement_ids,
                             all_achievements=all_achievements,
                             total_achievements=total_achievements,
                             achievement_points=achievement_points,
                             referral=referral)
    
    return render_template('app/dashboard.html', 
                         user=user, 
                         created_tokens=created_tokens, 
                         holdings=holdings,
                         activities=activities,
                         user_achievements=user_achievements,
                         user_achievement_ids=user_achievement_ids,
                         all_achievements=all_achievements,
                         total_achievements=total_achievements,
                         achievement_points=achievement_points,
                         referral=referral)

@app.route('/app/create', methods=['GET', 'POST'])
def create_token():
    """Token creation page and form handler"""
    user = get_current_user()
    if not user:
        if request.headers.get('HX-Request'):
            return '<div class="connect-wallet-container"><h2>Please connect your wallet</h2><a href="/app" class="btn btn-primary">Connect Wallet</a></div>'
        return render_template('app/connect_wallet.html')
    
    if request.method == 'POST':
        # Handle token creation form submission (UI mockup)
        name = request.form.get('name')
        symbol = request.form.get('symbol')
        description = request.form.get('description', '')
        website = request.form.get('website', '')
        twitter = request.form.get('twitter', '')
        telegram = request.form.get('telegram', '')
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
            new_token.website = website
            new_token.twitter = twitter
            new_token.telegram = telegram
            new_token.creator_id = user.id
            new_token.total_supply = int(total_supply)
            new_token.circulating_supply = 0
            new_token.deployment_status = 'pending'  # Mock status for UI
            new_token.current_price = 0.001  # Mock starting price
            new_token.current_market_cap = 1000  # Start at $1K market cap
            
            # Generate mock contract address
            import secrets
            new_token.contract_address = f'0x{secrets.token_hex(20).lower()}'
            
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
        if request.headers.get('HX-Request'):
            return '<div class="connect-wallet-container"><h2>Please connect your wallet</h2><a href="/app" class="btn btn-primary">Connect Wallet</a></div>'
        return render_template('app/connect_wallet.html')
    
    # Show all tokens, including pending ones for UI demo
    tokens = Token.query.order_by(Token.created_at.desc()).all()
    return render_template('app/marketplace.html', tokens=tokens, user=user)

@app.route('/app/token/<contract_address>')
def token_detail(contract_address):
    """Individual token detail page"""
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Get recent trades
    recent_trades = Trade.query.filter_by(token_id=token.id, tx_status='confirmed').order_by(Trade.confirmed_at.desc()).limit(10).all()
    
    # Get user's holding if connected
    user_holding = None
    user = get_current_user()
    if user:
        user_holding = Holding.query.filter_by(user_id=user.id, token_id=token.id).first()
    
    return render_template('app/token_detail.html', 
                         token=token, 
                         recent_trades=recent_trades,
                         user_holding=user_holding,
                         user=user)

# Fallback route for legacy numeric IDs (backwards compatibility)
@app.route('/app/token/<int:token_id>')
def token_detail_legacy(token_id):
    """Legacy route for backward compatibility - redirects to contract address"""
    token = Token.query.get_or_404(token_id)
    if token.contract_address:
        return redirect(url_for('token_detail', contract_address=token.contract_address))
    else:
        # Fallback for tokens without contract addresses
        return render_template('app/token_detail.html', 
                             token=token, 
                             recent_trades=[],
                             user_holding=None,
                             user=get_current_user())

# Leaderboard routes
@app.route('/app/leaderboard')
def leaderboard():
    """Main leaderboard page with rankings and points"""
    user = get_current_user()
    if not user:
        if request.headers.get('HX-Request'):
            return '<div class="connect-wallet-container"><h2>Please connect your wallet</h2><a href="/app" class="btn btn-primary">Connect Wallet</a></div>'
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

@app.route('/app/profile', methods=['GET', 'POST'])
def profile():
    """User profile page with wallet connections and stats"""
    user = get_current_user()
    if not user:
        if request.headers.get('HX-Request'):
            return '<div class="connect-wallet-container"><h2>Please connect your wallet</h2><a href="/app" class="btn btn-primary">Connect Wallet</a></div>'
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
        # Generate referral code based on username/display_name
        base_code = None
        if user_profile and user_profile.username:
            base_code = user_profile.username
        elif user.display_name:
            base_code = user.display_name
        else:
            base_code = user.wallet_address[:8] if user.wallet_address else f"user{user.id}"
        
        # Clean and validate the code
        import re
        base_code = re.sub(r'[^a-zA-Z0-9\-_]', '', base_code.lower())
        if len(base_code) < 3:
            base_code = f"user{user.id}"
        
        # Ensure uniqueness
        referral_code = base_code
        counter = 1
        while Referral.query.filter_by(referral_code=referral_code).first():
            referral_code = f"{base_code}{counter}"
            counter += 1
        
        referral = Referral()
        referral.referrer_id = user.id
        referral.referral_code = referral_code
        referral.referral_link = f"https://gemlaunch.fun/?ref={referral_code}"
        db.session.add(referral)
        db.session.commit()
    
    if request.method == 'POST':
        # Handle profile update in a single transaction
        try:
            # Handle profile picture upload with compression
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                
                # Validate file
                is_valid, message = validate_image_file(file)
                if not is_valid:
                    flash(message, 'error')
                    return redirect(url_for('profile'))
                
                # Process and compress image
                new_avatar_path = process_profile_image(file, user.id)
                if new_avatar_path:
                    # Cleanup old avatar if it exists
                    cleanup_old_avatar(user_profile.avatar_path)
                    
                    # Update profile with new avatar
                    user_profile.avatar_path = new_avatar_path
                    user_profile.avatar_updated_at = datetime.now(timezone.utc)
                else:
                    flash('Error processing image. Please try again.', 'error')
                    return redirect(url_for('profile'))
            
            # Update User model fields
            if 'display_name' in request.form:
                user.display_name = request.form['display_name'].strip()
            
            # Update UserProfile model fields
            if 'bio' in request.form:
                user_profile.bio = request.form['bio'].strip()
                
            # Handle username with proper validation feedback
            if 'username' in request.form:
                username = request.form['username'].strip()
                if username:
                    # Check if username is unique (excluding current user)
                    existing = UserProfile.query.filter(
                        UserProfile.username == username,
                        UserProfile.user_id != user.id
                    ).first()
                    if existing:
                        flash('Username already taken. Please choose a different one.', 'error')
                        return redirect(url_for('profile'))
                    user_profile.username = username
                    
            if 'profile_picture_url' in request.form:
                user_profile.profile_picture_url = request.form['profile_picture_url'].strip()
            if 'twitter_handle' in request.form:
                user_profile.twitter_handle = request.form['twitter_handle'].strip()
            if 'telegram_handle' in request.form:
                user_profile.telegram_handle = request.form['telegram_handle'].strip()
            if 'discord_handle' in request.form:
                user_profile.discord_handle = request.form['discord_handle'].strip()
            
            # Privacy settings
            user_profile.is_profile_public = 'is_profile_public' in request.form
            user_profile.show_wallet_address = 'show_wallet_address' in request.form
            
            # Add activity log before committing
            activity = Activity()
            activity.user_id = user.id
            activity.activity_type = 'profile_updated'
            activity.title = 'Profile Updated'
            activity.description = 'Updated profile information'
            activity.points_earned = 0
            db.session.add(activity)
            
            # Commit all changes in a single transaction
            db.session.commit()
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error updating profile. Please try again.', 'error')
    
    # Get referred users for referrals tab
    referred_users = User.query.join(Referral, Referral.referee_id == User.id).filter(
        Referral.referrer_id == user.id
    ).all()
    
    return render_template('app/profile.html', 
                         user=user, 
                         user_profile=user_profile,
                         connected_wallets=connected_wallets,
                         user_achievements=user_achievements,
                         referral=referral,
                         referred_users=referred_users)

@app.route('/app/referrals')
def referrals():
    """Redirect to profile page - referrals are now part of profile"""
    return redirect(url_for('profile'))

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
            
            # Create sample tokens with contract addresses if none exist
            if not Token.query.first():
                print("Creating sample tokens...")
                
                # Create sample users for token creation
                sample_user = User.query.first()
                if not sample_user:
                    # Create a default sample user for other tokens
                    sample_user = User()
                    sample_user.wallet_address = '0x1234567890abcdef1234567890abcdef12345678'
                    sample_user.display_name = 'Sample Creator'
                    sample_user.wallet_type = 'kastle'
                    db.session.add(sample_user)
                
                # Create the specific user (you) as creator for DOGKAS and MOON
                user_creator = User.query.filter_by(wallet_address='0xa51d8f597570353ae50a25df90ade162d2305ffa').first()
                if not user_creator:
                    user_creator = User()
                    user_creator.wallet_address = '0xa51d8f597570353ae50a25df90ade162d2305ffa'
                    user_creator.display_name = 'Token Creator'
                    user_creator.wallet_type = 'kastle'
                    db.session.add(user_creator)
                
                db.session.commit()
                
                # Sample token data with contract addresses and types
                sample_tokens = [
                    {
                        'name': 'Doge Kaspa',
                        'symbol': 'DOGKAS',
                        'description': 'Much speed, very fast. The ultimate Pro memecoin on Kaspa blockchain with advanced DAO features.',
                        'contract_address': '0x80707fad25e8727117d5ff2ad0960dae2b7aa463',
                        'market_cap': 45000,
                        'price': 0.000045,
                        'image_url': 'https://upload.wikimedia.org/wikipedia/en/d/d0/Dogecoin_Logo.png',
                        'creator': user_creator  # YOU own this token
                    },
                    {
                        'name': 'Moon Rocket',
                        'symbol': 'MOON',
                        'description': 'To the moon and beyond! Basic token with solid community features.',
                        'contract_address': '0x91818fbe36d8827228e6cc7c5af1cd52e4315g74',
                        'market_cap': 28000,
                        'price': 0.000028,
                        'image_url': 'https://upload.wikimedia.org/wikipedia/commons/1/1c/Rocket_icon.png',
                        'creator': user_creator  # YOU own this token too
                    },
                    {
                        'name': 'Laser Eyes',
                        'symbol': 'LASER',
                        'description': 'Laser focus on gains. Pro token with cutting-edge features.',
                        'contract_address': '0xc3d4e5f6789012345678901234567890abcdef12',
                        'market_cap': 67000,
                        'price': 0.000067,
                        'image_url': 'https://i.imgur.com/laser-eyes.png',
                        'creator': sample_user  # Different creator
                    },
                    {
                        'name': 'PepeCoin',
                        'symbol': 'PEPE',
                        'description': 'The most memeable memecoin on Kaspa. For the culture!',
                        'contract_address': '0xa1b2c3d4e5f6789012345678901234567890abcd',
                        'market_cap': 15000,
                        'price': 0.000015,
                        'image_url': 'https://upload.wikimedia.org/wikipedia/en/thumb/6/63/Feelsbadman.jpg/256px-Feelsbadman.jpg',
                        'creator': sample_user  # Different creator
                    },
                    {
                        'name': 'FlokiKas',
                        'symbol': 'FLOKI',
                        'description': 'Viking dog conquering the Kaspa ecosystem with lightning speed.',
                        'contract_address': '0xd4e5f6789012345678901234567890abcdef1234',
                        'market_cap': 32000,
                        'price': 0.000032,
                        'image_url': 'https://s2.coinmarketcap.com/static/img/coins/200x200/10804.png',
                        'creator': sample_user  # Different creator
                    }
                ]
                
                for token_data in sample_tokens:
                    token = Token()
                    token.name = token_data['name']
                    token.symbol = token_data['symbol']
                    token.description = token_data['description']
                    token.contract_address = token_data['contract_address']
                    token.image_url = token_data['image_url']
                    token.creator_id = token_data['creator'].id
                    token.current_market_cap = token_data['market_cap']
                    token.current_price = token_data['price']
                    token.circulating_supply = 1000000000  # 1B tokens
                    token.deployment_status = 'deployed'
                    token.trade_count = 42  # Mock trades
                    token.holder_count = 156  # Mock holders
                    db.session.add(token)
                
                db.session.commit()
                print("✅ Sample tokens created with contract addresses")
            else:
                # Update existing tokens without contract addresses
                tokens_without_ca = Token.query.filter_by(contract_address=None).all()
                if tokens_without_ca:
                    import secrets
                    for token in tokens_without_ca:
                        token.contract_address = f'0x{secrets.token_hex(20).lower()}'
                    db.session.commit()
                    print(f"✅ Updated {len(tokens_without_ca)} tokens with contract addresses")
                
        except Exception as e:
            print(f"❌ Database initialization error: {e}")

@app.route('/app/add-wallet', methods=['POST'])
def add_wallet():
    """Add additional wallet to user account"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        label = data.get('label', '').strip()
        address = data.get('address', '').strip()
        
        if not label:
            return jsonify({'error': 'Wallet label is required'}), 400
        
        if not address:
            return jsonify({'error': 'Wallet address is required'}), 400
        
        if len(address) < 10:
            return jsonify({'error': 'Invalid wallet address'}), 400
        
        # Check if wallet address already exists (across ALL users)
        existing_wallet = ConnectedWallet.query.filter_by(wallet_address=address.lower()).first()
        if existing_wallet:
            return jsonify({'error': 'This wallet address is already connected to another account'}), 400
        
        # Also check if it's the primary wallet of any user
        existing_user = User.query.filter_by(wallet_address=address.lower()).first()
        if existing_user:
            return jsonify({'error': 'This wallet address is already being used as a primary wallet'}), 400
        
        # Create new connected wallet
        new_wallet = ConnectedWallet()
        new_wallet.user_id = user.id
        new_wallet.wallet_address = address.lower()
        new_wallet.wallet_type = 'additional'
        new_wallet.wallet_label = label
        new_wallet.is_primary = False
        
        db.session.add(new_wallet)
        
        # Add activity log
        activity = Activity()
        activity.user_id = user.id
        activity.activity_type = 'wallet_added'
        activity.title = 'Additional Wallet Added'
        activity.description = f'Added wallet: {label}'
        activity.points_earned = 10  # Small reward for adding wallet
        db.session.add(activity)
        
        # Update user's total points
        user.gem_points = (user.gem_points or 0) + 10
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Wallet added successfully',
            'wallet': {
                'label': label,
                'address': address,
                'points_earned': 10
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to add wallet. Please try again.'}), 500

@app.route('/app/remove-wallet/<int:wallet_id>', methods=['DELETE'])
def remove_wallet(wallet_id):
    """Remove additional wallet from user account"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        # Find the wallet and verify ownership
        wallet = ConnectedWallet.query.filter_by(id=wallet_id, user_id=user.id).first()
        if not wallet:
            return jsonify({'error': 'Wallet not found or not owned by user'}), 404
        
        # Prevent removing primary wallet
        if wallet.is_primary:
            return jsonify({'error': 'Cannot remove primary wallet'}), 400
        
        # Remove wallet
        db.session.delete(wallet)
        
        # Add activity log
        activity = Activity()
        activity.user_id = user.id
        activity.activity_type = 'wallet_removed'
        activity.title = 'Wallet Removed'
        activity.description = f'Removed wallet: {wallet.wallet_label or "Unnamed"}'
        activity.points_earned = 0
        db.session.add(activity)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Wallet removed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to remove wallet. Please try again.'}), 500

@app.route('/app/edit-wallet/<int:wallet_id>', methods=['POST'])
def edit_wallet(wallet_id):
    """Edit wallet label"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        new_label = data.get('label', '').strip()
        
        if not new_label:
            return jsonify({'error': 'Wallet label is required'}), 400
        
        if len(new_label) > 50:
            return jsonify({'error': 'Wallet label must be 50 characters or less'}), 400
        
        # Find the wallet and verify ownership
        wallet = ConnectedWallet.query.filter_by(id=wallet_id, user_id=user.id).first()
        if not wallet:
            return jsonify({'error': 'Wallet not found or not owned by user'}), 404
        
        old_label = wallet.wallet_label
        wallet.wallet_label = new_label
        
        # Add activity log
        activity = Activity()
        activity.user_id = user.id
        activity.activity_type = 'wallet_updated'
        activity.title = 'Wallet Label Updated'
        activity.description = f'Updated wallet label from "{old_label}" to "{new_label}"'
        activity.points_earned = 0
        db.session.add(activity)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Wallet label updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update wallet label. Please try again.'}), 500

@app.route('/app/update-referral-code', methods=['POST'])
def update_referral_code():
    """Update custom referral code"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        new_code = data.get('referral_code', '').strip()
        
        if not new_code:
            return jsonify({'error': 'Referral code is required'}), 400
        
        # Validate referral code format
        if len(new_code) < 3 or len(new_code) > 20:
            return jsonify({'error': 'Referral code must be 3-20 characters long'}), 400
        
        # Allow only alphanumeric characters and hyphens
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+$', new_code):
            return jsonify({'error': 'Referral code can only contain letters, numbers, hyphens, and underscores'}), 400
        
        # Check if referral code already exists (case insensitive)
        existing_referral = Referral.query.filter(
            db.func.lower(Referral.referral_code) == new_code.lower(),
            Referral.referrer_id != user.id
        ).first()
        
        if existing_referral:
            return jsonify({'error': 'This referral code is already taken. Please choose another one.'}), 400
        
        # Get or create user's referral record
        referral = Referral.query.filter_by(referrer_id=user.id).first()
        is_new_referral = False
        if not referral:
            referral = Referral()
            referral.referrer_id = user.id
            db.session.add(referral)
            is_new_referral = True
        
        # Check if code is actually changing
        old_code = referral.referral_code if referral.referral_code else None
        new_code_lower = new_code.lower()
        
        if old_code == new_code_lower:
            return jsonify({'error': 'This is already your current referral code'}), 400
        
        # Update referral code and link
        referral.referral_code = new_code_lower
        referral.referral_link = f"https://gemlaunch.fun/?ref={new_code_lower}"
        
        # Check if user has already been rewarded for customizing referral code
        has_customized_before = Activity.query.filter_by(
            user_id=user.id,
            activity_type='referral_updated'
        ).first() is not None
        
        # Award points only for first-time customization
        points_earned = 0
        if is_new_referral or not has_customized_before:
            points_earned = 5
            user.gem_points = (user.gem_points or 0) + points_earned
        
        # Add activity log
        activity = Activity()
        activity.user_id = user.id
        activity.activity_type = 'referral_updated'
        activity.title = 'Custom Referral Code Updated'
        activity.description = f'Changed referral code to: {new_code_lower}'
        activity.points_earned = points_earned
        db.session.add(activity)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Referral code updated successfully!',
            'new_link': referral.referral_link,
            'points_earned': 5
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update referral code. Please try again.'}), 500

# Admin Routes
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard - protected route"""
    # Simple protection - check for admin parameter or specific wallet
    admin_key = request.args.get('key')
    if admin_key != 'gemlaunch-admin-2024':  # Simple key for now
        return "Access Denied", 403
    
    # Get system stats
    total_users = User.query.count()
    total_tokens = Token.query.count()
    total_volume = db.session.query(db.func.sum(Trade.kas_amount)).scalar() or 0
    total_points = db.session.query(db.func.sum(User.gem_points)).scalar() or 0
    
    # Get recent activities
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(10).all()
    
    # Get top users
    top_users = User.query.order_by(User.gem_points.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_tokens=total_tokens,
                         total_volume=float(total_volume),
                         total_points=total_points,
                         recent_activities=recent_activities,
                         top_users=top_users)

@app.route('/admin/users')
def admin_users():
    """Admin user management"""
    admin_key = request.args.get('key')
    if admin_key != 'gemlaunch-admin-2024':
        return "Access Denied", 403
    
    # Get all users with profiles
    users = db.session.query(User, UserProfile).outerjoin(
        UserProfile, User.id == UserProfile.user_id
    ).order_by(User.gem_points.desc()).all()
    
    # Get all achievements for dropdown
    achievements = Achievement.query.order_by(Achievement.category, Achievement.gem_points_reward).all()
    
    return render_template('admin/users.html', users=users, achievements=achievements)

@app.route('/admin/award-points', methods=['POST'])
def admin_award_points():
    """Award points to a user"""
    admin_key = request.form.get('admin_key')
    if admin_key != 'gemlaunch-admin-2024':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        user_id = request.form.get('user_id')
        points = int(request.form.get('points', 0))
        reason = request.form.get('reason', 'Admin award')
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Award points
        user.gem_points = (user.gem_points or 0) + points
        
        # Log activity
        activity = Activity()
        activity.user_id = user.id
        activity.activity_type = 'admin_award'
        activity.title = 'Points Awarded'
        activity.description = f"{reason} (+{points} points)"
        activity.points_earned = points
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'success': True, 'new_points': user.gem_points})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/grant-accolade', methods=['POST'])
def admin_grant_accolade():
    """Grant an accolade to a user"""
    admin_key = request.form.get('admin_key')
    if admin_key != 'gemlaunch-admin-2024':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        user_id = request.form.get('user_id')
        achievement_id = request.form.get('achievement_id')
        
        user = User.query.get(user_id)
        achievement = Achievement.query.get(achievement_id)
        
        if not user or not achievement:
            return jsonify({'error': 'User or achievement not found'}), 404
        
        # Check if already has this achievement
        existing = UserAchievement.query.filter_by(
            user_id=user_id,
            achievement_id=achievement_id
        ).first()
        
        if existing:
            return jsonify({'error': 'User already has this accolade'}), 400
        
        # Grant achievement
        user_achievement = UserAchievement()
        user_achievement.user_id = user.id
        user_achievement.achievement_id = achievement.id
        db.session.add(user_achievement)
        
        # Award points
        user.gem_points = (user.gem_points or 0) + achievement.gem_points_reward
        
        # Log activity
        activity = Activity()
        activity.user_id = user.id
        activity.activity_type = 'achievement_earned'
        activity.title = f'Earned: {achievement.name}'
        activity.description = achievement.description
        activity.achievement_id = achievement.id
        activity.points_earned = achievement.gem_points_reward
        db.session.add(activity)
        
        # Create accolade log
        from datetime import datetime
        from sqlalchemy import text
        db.session.execute(
            text("INSERT INTO accolade_logs (user_id, achievement_id, awarded_by, reason, created_at) VALUES (:uid, :aid, :by, :reason, :now)"),
            {'uid': user.id, 'aid': achievement.id, 'by': 'Admin', 'reason': 'Manual grant', 'now': datetime.now()}
        )
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Granted {achievement.name} to {user.display_name}',
            'points_awarded': achievement.gem_points_reward
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/tokens')
def admin_tokens():
    """Admin token management"""
    admin_key = request.args.get('key')
    if admin_key != 'gemlaunch-admin-2024':
        return "Access Denied", 403
    
    # Get all tokens with creator info
    tokens = Token.query.join(User, Token.creator_id == User.id).order_by(
        Token.current_market_cap.desc()
    ).all()
    
    # Get partner tokens
    from sqlalchemy import text
    partner_tokens = db.session.execute(
        text("SELECT t.*, pt.* FROM token t LEFT JOIN partner_tokens pt ON t.id = pt.token_id WHERE pt.id IS NOT NULL")
    ).fetchall()
    
    return render_template('admin/tokens.html', tokens=tokens, partner_tokens=partner_tokens)

@app.route('/admin/set-partner', methods=['POST'])
def admin_set_partner():
    """Set a token as partner with multiplier"""
    admin_key = request.form.get('admin_key')
    if admin_key != 'gemlaunch-admin-2024':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        token_id = request.form.get('token_id')
        multiplier = float(request.form.get('multiplier', 1.5))
        
        # Check if already partner
        from sqlalchemy import text
        existing = db.session.execute(
            text("SELECT * FROM partner_tokens WHERE token_id = :tid"),
            {'tid': token_id}
        ).first()
        
        if existing:
            # Update multiplier
            db.session.execute(
                text("UPDATE partner_tokens SET point_multiplier = :mult WHERE token_id = :tid"),
                {'mult': multiplier, 'tid': token_id}
            )
        else:
            # Create new partner
            db.session.execute(
                text("INSERT INTO partner_tokens (token_id, point_multiplier) VALUES (:tid, :mult)"),
                {'tid': token_id, 'mult': multiplier}
            )
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Partner status updated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Initialize database when app starts
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
