import os
import logging
import secrets
import json
import time
import atexit
import random
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
from sqlalchemy.orm import joinedload, selectinload
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, User, Token, Trade, Holding, Achievement, UserAchievement, UserProfile, ConnectedWallet, Referral, Activity, LinkedWallet, WalletVerificationChallenge, TransferRequest, ReserveDistribution, TradeEvent, TokenEngagement, Position, PlatformSettings
from models_extended import ChatMessage, Poll, PollOption, PollVote, MessageReaction, TokenSettings, TokenLeaderboard
from services import TokenService
from services.achievement_service import evaluate_user_achievements
from services.web3_service import get_web3_service
from services.tx_monitor import get_tx_monitor
# Import index_all_events inside function to avoid circular import
from services.blockscout_client import get_blockscout_client
from services.graduation_completion_service import start_graduation_completion_service, stop_graduation_completion_service
from utils.validators import validate_eth_wallet_address, is_valid_eth_address
from web3 import Web3

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
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure session cookies for CORS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Custom Jinja2 filter for formatting large numbers
@app.template_filter('format_number')
def format_number_filter(num, include_decimals=False):
    """Format large numbers into human-readable format (1K, 1M, 1B, etc.)"""
    if num is None:
        return '0'
    
    try:
        # Handle Decimal types from database
        num = float(num)
        abs_num = abs(num)
        
        if abs_num >= 1e12:
            return f'{num/1e12:.{2 if include_decimals else 1}f}'.rstrip('0').rstrip('.') + 'T'
        elif abs_num >= 1e9:
            return f'{num/1e9:.{2 if include_decimals else 1}f}'.rstrip('0').rstrip('.') + 'B'
        elif abs_num >= 1e6:
            return f'{num/1e6:.{2 if include_decimals else 1}f}'.rstrip('0').rstrip('.') + 'M'
        elif abs_num >= 1e3:
            return f'{num/1e3:.{2 if include_decimals else 1}f}'.rstrip('0').rstrip('.') + 'K'
        else:
            return f'{num:,.0f}'
    except (TypeError, ValueError):
        return '0'

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize database
db.init_app(app)

# Initialize Flask-Caching for GraphQL API responses
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',  # In-memory cache
    'CACHE_DEFAULT_TIMEOUT': 10  # 10 second cache for real-time trading data
})

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize X (Twitter) OAuth
from auth_x import auth_x_bp, init_oauth
app.register_blueprint(auth_x_bp)
twitter_oauth = init_oauth(app)

# Initialize rate limiter for auth endpoints
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

# Custom rate limit error handler
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'error': 'Too many authentication attempts. Please wait a moment before trying again.',
        'retry_after': getattr(e.description, 'retry_after', 60)
    }), 429

# Prevent aggressive browser caching
@app.after_request
def add_cache_control_headers(response):
    """Add Cache-Control headers to prevent browser caching of dynamic content"""
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Initialize transaction monitor and scheduler
tx_monitor = get_tx_monitor()
scheduler = BackgroundScheduler()

# Wrapper function to run check_pending_transactions in app context
def check_pending_with_context():
    with app.app_context():
        tx_monitor.check_pending_transactions()

# Wrapper function to run event indexer in app context
def run_event_indexer_with_context():
    with app.app_context():
        try:
            # Import here to avoid circular import with services/event_indexer.py
            from services.event_indexer import index_all_events
            index_all_events()
        except Exception as e:
            logging.error(f"Error in event indexer: {str(e)}")
            db.session.rollback()

# Wrapper function to run graduation monitor in app context
def run_graduation_monitor_with_context():
    with app.app_context():
        try:
            from services.graduation_monitor import check_all_graduations
            check_all_graduations()
        except Exception as e:
            logging.error(f"Error in graduation monitor: {str(e)}")
            db.session.rollback()

# Add monitoring job - runs every 10 seconds
scheduler.add_job(
    func=check_pending_with_context,
    trigger='interval',
    seconds=10,
    id='tx_monitor',
    name='Monitor pending transactions',
    replace_existing=True
)

# Add event indexer job - runs every 30 seconds (optimized for performance)
scheduler.add_job(
    func=run_event_indexer_with_context,
    trigger='interval',
    seconds=30,
    id='event_indexer',
    name='Index blockchain events',
    replace_existing=True
)

# Add graduation monitor job - runs every 60 seconds
scheduler.add_job(
    func=run_graduation_monitor_with_context,
    trigger='interval',
    seconds=60,
    id='graduation_monitor',
    name='Monitor token graduations',
    replace_existing=True
)

# Start scheduler
scheduler.start()

# Start graduation completion service (monitors for graduations to complete)
graduation_service = start_graduation_completion_service(app)

# Ensure graceful shutdown
atexit.register(lambda: scheduler.shutdown())
atexit.register(lambda: stop_graduation_completion_service())

logging.info("Transaction monitor scheduler started - checking every 10 seconds")
logging.info("Event indexer scheduler started - checking every 30 seconds (active tokens only)")
logging.info("Graduation monitor scheduler started - checking every 60 seconds")
logging.info("Graduation completion service started - monitoring for pending graduations")

def get_current_user():
    """Get current user from session - only if wallet is verified"""
    wallet_address = session.get('wallet_address')
    wallet_verified = session.get('wallet_verified', False)
    
    if wallet_address and wallet_verified:
        user = User.resolve_wallet_to_user(wallet_address)
        if user:
            # Load profile relationship if needed
            return User.query.options(
                joinedload(User.profile)
            ).get(user.id)
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

def wallet_optional(f):
    """Decorator for routes that work with or without wallet connection"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # User will be None if not connected, views must handle this
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """Inject current user into all templates"""
    return dict(current_user=get_current_user())

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
@limiter.limit("60 per minute")
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
@limiter.limit("30 per minute")
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
        
        # Verify signature for EVM-compatible wallets (MetaMask, Kastle, KasWare on Kaspa L2)
        if wallet_type.lower() in ['metamask', 'evm', 'kastle', 'kasware']:
            try:
                # Encode message for Ethereum personal_sign standard
                encoded_message = encode_defunct(text=message)
                
                # Recover address from signature using secp256k1 ECDSA
                recovered_address = Account.recover_message(encoded_message, signature=signature)
                
                # Verify the recovered address matches the claimed address (normalized to lowercase)
                if recovered_address.lower() != wallet_address.lower():
                    # Invalidate nonce on verification failure to prevent replay attacks
                    session.pop(session_key, None)
                    return jsonify({'error': 'Signature verification failed. Invalid signature.'}), 401
                    
            except Exception as sig_error:
                # Invalidate nonce on error
                session.pop(session_key, None)
                return jsonify({'error': f'Signature verification error: {str(sig_error)}'}), 401
        
        # Clear the used nonce to prevent replay attacks
        if session_key:
            session.pop(session_key, None)
        
        # Clear all existing session data before creating new session
        session.clear()
        
        # Create or get user with verified wallet address
        user = User.get_or_create_by_wallet(wallet_address, wallet_type)
        
        # Store verified wallet in session
        session.permanent = True  # Make session persist across browser restarts
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

@app.route('/api/auth/session', methods=['GET'])
def check_session():
    """Check if user has active session"""
    user = get_current_user()
    if user:
        return jsonify({
            'authenticated': True,
            'wallet_address': user.wallet_address,
            'wallet_type': session.get('wallet_type', 'unknown')
        })
    return jsonify({'authenticated': False})

# Transaction Monitoring API
@app.route('/api/tx/<tx_hash>/status', methods=['GET'])
def api_tx_status(tx_hash):
    """Get transaction status - monitors pending transactions
    
    Returns transaction status from database or directly from blockchain.
    Frontend can poll this endpoint to get real-time transaction updates.
    
    Response:
    {
        "success": true,
        "status": "pending|confirmed|failed",
        "tx_hash": "0x...",
        "tx_type": "buy|sell|claim_fees|distribute_fees|deploy_token",
        "user_address": "0x...",
        "token_id": 123,
        "created_at": "2025-10-11T...",
        "confirmed_at": "2025-10-11T...",
        "block_number": 12345,
        "gas_used": 50000,
        "error_message": "Transaction reverted"
    }
    """
    from services.tx_monitor import get_tx_monitor
    
    try:
        tx_monitor = get_tx_monitor()
        result = tx_monitor.get_transaction_status(tx_hash)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logging.error(f"Error getting transaction status for {tx_hash}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get transaction status'
        }), 500

@app.route('/api/tx/<tx_hash>/stream')
def stream_tx_status(tx_hash):
    """
    Server-Sent Events endpoint for real-time transaction status updates
    
    Usage (client-side):
    const eventSource = new EventSource('/api/tx/0x.../stream');
    eventSource.onmessage = (event) => {
        const status = JSON.parse(event.data);
        console.log(status);
        if (status.status === 'confirmed' || status.status === 'failed') {
            eventSource.close();
        }
    };
    """
    from services.tx_monitor import get_tx_monitor
    
    def generate():
        # Push Flask app context for database access in generator
        with app.app_context():
            try:
                tx_monitor = get_tx_monitor()
                max_checks = 300  # 5 minutes (2s interval * 300 = 600s)
                
                # Send initial ping to establish connection
                yield f": keepalive\n\n"
                
                for _ in range(max_checks):
                    status = tx_monitor.get_transaction_status(tx_hash)
                    
                    # Send update to client with 'status' event type to match client listener
                    yield f"event: status\ndata: {json.dumps(status)}\n\n"
                    
                    # Stop if terminal state reached
                    if status.get('status') in ['confirmed', 'failed']:
                        # Immediately index this transaction so it appears in recent trades
                        if status.get('status') == 'confirmed':
                            try:
                                from services.event_indexer import index_transaction_immediately
                                index_result = index_transaction_immediately(tx_hash)
                                if index_result.get('success'):
                                    logging.info(f"✅ Immediately indexed confirmed tx: {tx_hash[:10]}...")
                                else:
                                    logging.warning(f"Failed to immediately index tx {tx_hash[:10]}...: {index_result.get('error')}")
                            except Exception as e:
                                logging.error(f"Error immediately indexing tx {tx_hash}: {str(e)}")
                        
                        # Send final completion event before closing stream
                        yield f"event: complete\ndata: {json.dumps({'status': 'complete'})}\n\n"
                        break
                    
                    time.sleep(2)  # Check every 2 seconds
                else:
                    # Timeout reached without confirmation - send terminal event
                    logging.warning(f"⏱️ Transaction monitoring timed out after {max_checks * 2}s for {tx_hash}")
                    timeout_data = {
                        'success': False,
                        'status': 'timeout',
                        'message': 'Transaction monitoring timed out. Please check the blockchain explorer to verify status.'
                    }
                    yield f"event: status\ndata: {json.dumps(timeout_data)}\n\n"
                    yield f"event: complete\ndata: {json.dumps({'status': 'timeout'})}\n\n"
                
            except Exception as e:
                logging.error(f"SSE stream error for {tx_hash}: {str(e)}")
                import traceback
                traceback.print_exc()
                error_data = {'success': False, 'error': str(e), 'status': 'failed'}
                yield f"event: status\ndata: {json.dumps(error_data)}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
        }
    )

# Multi-wallet linking API
@app.route('/api/wallet/request-link', methods=['POST'])
def request_wallet_link():
    """Request to link a secondary wallet to user account"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    wallet_label = data.get('wallet_label', '')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    try:
        wallet_address_lower = validate_eth_wallet_address(wallet_address)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    if wallet_address_lower == user.wallet_address.lower():
        return jsonify({'error': 'Cannot link your primary wallet address'}), 400
    
    existing_linked = LinkedWallet.query.filter_by(wallet_address=wallet_address_lower).first()
    if existing_linked:
        return jsonify({'error': 'Wallet address already linked to a profile'}), 400
    
    existing_user = User.query.filter_by(wallet_address=wallet_address_lower).first()
    if existing_user:
        return jsonify({
            'error': 'Wallet address is already a primary wallet for another user',
            'account_found': True,
            'legacy_user': {
                'display_name': existing_user.display_name,
                'gem_points': existing_user.gem_points,
                'total_tokens_created': existing_user.total_tokens_created,
                'wallet_address': existing_user.wallet_address
            }
        }), 409
    
    try:
        nonce = secrets.token_urlsafe(32)
        
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        expires_at_iso = expires_at.isoformat()
        
        challenge_message = f"Link wallet {wallet_address_lower} to primary {user.wallet_address}. Nonce: {nonce}. Expires: {expires_at_iso}"
        
        challenge = WalletVerificationChallenge(
            user_id=user.id,
            wallet_address=wallet_address_lower,
            nonce=nonce,
            challenge_message=challenge_message,
            expires_at=expires_at,
            used=False
        )
        
        db.session.add(challenge)
        db.session.commit()
        
        logging.info(f"Wallet link request created for user {user.id}, wallet {wallet_address_lower}")
        
        return jsonify({
            'success': True,
            'challenge_message': challenge_message,
            'nonce': nonce
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating wallet link request: {str(e)}")
        return jsonify({'error': f'Failed to create link request: {str(e)}'}), 500

@app.route('/api/wallet/verify-link', methods=['POST'])
def verify_wallet_link():
    """Verify signature and link secondary wallet to user account"""
    from eth_account.messages import encode_defunct
    from eth_account import Account
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    nonce = data.get('nonce')
    signature = data.get('signature')
    
    if not wallet_address or not nonce or not signature:
        return jsonify({'error': 'Wallet address, nonce, and signature required'}), 400
    
    wallet_address_lower = wallet_address.lower()
    
    try:
        challenge = WalletVerificationChallenge.query.filter_by(
            user_id=user.id,
            wallet_address=wallet_address_lower,
            nonce=nonce
        ).first()
        
        if not challenge:
            logging.warning(f"Invalid nonce for wallet link verification: user {user.id}, wallet {wallet_address_lower}")
            return jsonify({'error': 'Invalid or missing verification challenge'}), 400
        
        if challenge.used:
            logging.warning(f"Attempt to reuse nonce for wallet link: user {user.id}, wallet {wallet_address_lower}")
            return jsonify({'error': 'Verification challenge already used'}), 400
        
        if challenge.is_expired:
            logging.warning(f"Expired nonce for wallet link: user {user.id}, wallet {wallet_address_lower}")
            return jsonify({'error': 'Verification challenge expired. Please request a new one.'}), 400
        
        try:
            encoded_message = encode_defunct(text=challenge.challenge_message)
            recovered_address = Account.recover_message(encoded_message, signature=signature)
            
            if recovered_address.lower() != wallet_address_lower:
                logging.warning(f"Signature verification failed for wallet link: user {user.id}, wallet {wallet_address_lower}, recovered {recovered_address}")
                return jsonify({'error': 'Signature verification failed. The signature does not match the wallet address.'}), 401
                
        except Exception as sig_error:
            logging.error(f"Signature verification error for wallet link: {str(sig_error)}")
            return jsonify({'error': f'Signature verification error: {str(sig_error)}'}), 401
        
        existing_linked = LinkedWallet.query.filter_by(wallet_address=wallet_address_lower).first()
        if existing_linked:
            db.session.rollback()
            return jsonify({'error': 'Wallet address already linked to a profile'}), 400
        
        wallet_label = data.get('wallet_label', f'Wallet {wallet_address_lower[:8]}...')
        
        linked_wallet = LinkedWallet(
            user_id=user.id,
            wallet_address=wallet_address_lower,
            wallet_label=wallet_label,
            signature_payload=signature,
            last_verified_at=datetime.now(timezone.utc),
            status='verified'
        )
        
        challenge.mark_used()
        
        db.session.add(linked_wallet)
        db.session.commit()
        
        # Consolidate TokenEngagement records from secondary wallet to primary account
        # Check if the secondary wallet has an existing User account
        secondary_user = User.query.filter_by(wallet_address=wallet_address_lower).first()
        if secondary_user and secondary_user.id != user.id:
            # Consolidate all engagement records from secondary user to primary user
            consolidated_count = TokenEngagement.consolidate_for_linked_wallet(
                old_user_id=secondary_user.id,
                new_user_id=user.id
            )
            logging.info(f"Wallet link consolidated {consolidated_count} engagement records from secondary user {secondary_user.id} to primary user {user.id}")
        
        logging.info(f"Wallet successfully linked: user {user.id}, wallet {wallet_address_lower}")
        
        return jsonify({
            'success': True,
            'message': 'Wallet linked successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error verifying wallet link: {str(e)}")
        return jsonify({'error': f'Failed to verify and link wallet: {str(e)}'}), 500

@app.route('/api/wallet/linked', methods=['GET'])
def get_linked_wallets():
    """Get all linked wallets for current user"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    try:
        linked_wallets = LinkedWallet.query.filter_by(user_id=user.id).all()
        
        wallets_data = []
        for wallet in linked_wallets:
            wallets_data.append({
                'address': wallet.wallet_address,
                'label': wallet.wallet_label,
                'verified_at': wallet.last_verified_at.isoformat() if wallet.last_verified_at else None,
                'status': wallet.status,
                'created_at': wallet.created_at.isoformat() if wallet.created_at else None
            })
        
        return jsonify({
            'success': True,
            'wallets': wallets_data
        })
        
    except Exception as e:
        logging.error(f"Error fetching linked wallets: {str(e)}")
        return jsonify({'error': f'Failed to fetch linked wallets: {str(e)}'}), 500

@app.route('/api/wallet/unlink/<wallet_address>', methods=['DELETE'])
def unlink_wallet(wallet_address):
    """Unlink a secondary wallet from user account"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    wallet_address_lower = wallet_address.lower()
    
    try:
        linked_wallet = LinkedWallet.query.filter_by(
            user_id=user.id,
            wallet_address=wallet_address_lower
        ).first()
        
        if not linked_wallet:
            return jsonify({'error': 'Wallet not found or does not belong to your account'}), 404
        
        linked_wallet.status = 'revoked'
        linked_wallet.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        logging.info(f"Wallet unlinked: user {user.id}, wallet {wallet_address_lower}")
        
        return jsonify({
            'success': True,
            'message': 'Wallet unlinked successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error unlinking wallet: {str(e)}")
        return jsonify({'error': f'Failed to unlink wallet: {str(e)}'}), 500

# REMOVED: Legacy claim ownership endpoints (/api/wallet/request-claim and /api/wallet/verify-claim)
# These endpoints have been replaced by the TransferRequest flow which provides cleaner approval process.

# Transfer Request API (Give Ownership Flow)
@app.route('/api/wallet/request-transfer', methods=['POST'])
@require_wallet_connection
def request_transfer():
    """Request ownership transfer from another wallet's owner"""
    from models import TransferRequest
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    try:
        wallet_address_lower = validate_eth_wallet_address(wallet_address)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    if wallet_address_lower == user.wallet_address.lower():
        return jsonify({'error': 'You already own this wallet'}), 400
    
    owner_user = User.query.filter_by(wallet_address=wallet_address_lower).first()
    if not owner_user:
        return jsonify({'error': 'This wallet address is not registered as a primary wallet'}), 404
    
    if owner_user.archived:
        return jsonify({'error': 'This account has already been archived'}), 400
    
    try:
        pending_count = TransferRequest.query.filter_by(
            requester_id=user.id,
            status='pending'
        ).filter(
            TransferRequest.expires_at > datetime.now(timezone.utc)
        ).count()
        
        if pending_count >= 3:
            return jsonify({'error': 'Too many pending transfer requests. Please wait for existing requests to be processed.'}), 429
        
        existing_request = TransferRequest.query.filter_by(
            requester_id=user.id,
            owner_id=owner_user.id,
            wallet_address=wallet_address_lower,
            status='pending'
        ).filter(
            TransferRequest.expires_at > datetime.now(timezone.utc)
        ).first()
        
        if existing_request:
            return jsonify({'error': 'You already have a pending transfer request for this wallet'}), 400
        
        transfer_request = TransferRequest.create_request(
            requester_id=user.id,
            owner_id=owner_user.id,
            wallet_address=wallet_address_lower
        )
        db.session.commit()
        
        logging.info(f"Transfer request created: requester={user.id}, owner={owner_user.id}, wallet={wallet_address_lower}")
        
        return jsonify({
            'success': True,
            'request_id': transfer_request.id,
            'owner_display_name': owner_user.display_name,
            'expires_at': transfer_request.expires_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating transfer request: {str(e)}")
        return jsonify({'error': f'Failed to create transfer request: {str(e)}'}), 500

@app.route('/api/wallet/pending-transfers', methods=['GET'])
@require_wallet_connection
def get_pending_transfers():
    """Get all pending transfer requests where current user is the owner"""
    from models import TransferRequest
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    try:
        pending_requests = TransferRequest.query.filter_by(
            owner_id=user.id,
            status='pending'
        ).filter(
            TransferRequest.expires_at > datetime.now(timezone.utc)
        ).order_by(
            TransferRequest.created_at.desc()
        ).all()
        
        requests_data = []
        for req in pending_requests:
            canonical_message = f"Accept transfer request for wallet {req.wallet_address} and merge accounts.\n\nNonce: {req.nonce}\nTimestamp: {int(req.created_at.timestamp())}\n\nWarning: This will merge all data from your account into the requester's account."
            requests_data.append({
                'id': req.id,
                'requester_wallet': req.requester.wallet_address,
                'requester_display': req.requester.display_name,
                'wallet_address': req.wallet_address,
                'nonce': req.nonce,
                'created_at': req.created_at.isoformat(),
                'expires_at': req.expires_at.isoformat(),
                'message': canonical_message
            })
        
        return jsonify(requests_data)
        
    except Exception as e:
        logging.error(f"Error fetching pending transfers: {str(e)}")
        return jsonify({'error': f'Failed to fetch pending transfers: {str(e)}'}), 500

@app.route('/api/wallet/accept-transfer', methods=['POST'])
@require_wallet_connection
def accept_transfer():
    """Accept a transfer request and merge accounts"""
    from eth_account.messages import encode_defunct
    from eth_account import Account
    from services.account_merger import merge_accounts
    from models import TransferRequest
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    request_id = data.get('request_id')
    signature = data.get('signature')
    
    if not request_id or not signature:
        return jsonify({'error': 'Request ID and signature required'}), 400
    
    try:
        transfer_request = TransferRequest.query.get(request_id)
        
        if not transfer_request:
            return jsonify({'error': 'Transfer request not found'}), 404
        
        if transfer_request.owner_id != user.id:
            logging.warning(f"User {user.id} attempted to accept transfer request {request_id} owned by {transfer_request.owner_id}")
            return jsonify({'error': 'You do not have permission to accept this request'}), 403
        
        if transfer_request.status != 'pending':
            return jsonify({'error': f'Transfer request is not pending (status: {transfer_request.status})'}), 400
        
        # SECURITY: Check expiry BEFORE signature verification to prevent wasted CPU on expired requests
        # Store the expiry result to prevent race conditions from multiple property evaluations
        is_expired = transfer_request.is_expired
        if is_expired:
            transfer_request.expire()
            db.session.commit()
            logging.warning(f"Rejected expired transfer request {request_id} for user {user.id}. Request expired at {transfer_request.expires_at}")
            return jsonify({'error': 'Transfer request has expired'}), 400
        
        transfer_message = f"Accept transfer request for wallet {transfer_request.wallet_address} and merge accounts.\n\nNonce: {transfer_request.nonce}\nTimestamp: {int(transfer_request.created_at.timestamp())}\n\nWarning: This will merge all data from your account into the requester's account."
        
        try:
            encoded_message = encode_defunct(text=transfer_message)
            recovered_address = Account.recover_message(encoded_message, signature=signature)
            
            if recovered_address.lower() != user.wallet_address.lower():
                logging.warning(f"Signature verification failed for transfer: user {user.id}, wallet {user.wallet_address}, recovered {recovered_address}")
                return jsonify({'error': 'Signature verification failed. You must sign with your wallet.'}), 401
                
        except Exception as sig_error:
            logging.error(f"Signature verification error for transfer: {str(sig_error)}")
            return jsonify({'error': f'Signature verification error: {str(sig_error)}'}), 401
        
        requester_user = User.query.get(transfer_request.requester_id)
        if not requester_user:
            return jsonify({'error': 'Requester user not found'}), 404
        
        if user.archived:
            return jsonify({'error': 'Your account has already been archived'}), 400
        
        # SECURITY: Final expiry check right before acceptance to prevent race conditions
        # This ensures atomicity between validation and state change
        if transfer_request.is_expired:
            transfer_request.expire()
            db.session.commit()
            logging.warning(f"Transfer request {request_id} expired during processing (race condition prevented)")
            return jsonify({'error': 'Transfer request expired during processing'}), 400
        
        # CRITICAL: Accept the request FIRST, then merge
        # This ensures if accept() fails (e.g., expired), merge never happens
        # The accept() method will perform one final expiry check for atomicity
        transfer_request.accept()
        
        # Only merge if accept succeeded (no ValueError raised)
        merge_summary = merge_accounts(db, requester_user.id, user.id)
        
        # SECURITY: Invalidate all other pending transfer requests for this wallet
        from models import WalletVerificationChallenge
        
        other_pending_requests = TransferRequest.query.filter(
            TransferRequest.wallet_address == transfer_request.wallet_address,
            TransferRequest.id != transfer_request.id,
            TransferRequest.status == 'pending'
        ).all()
        
        for req in other_pending_requests:
            req.status = 'cancelled'
            logging.info(f"Cancelled pending transfer request {req.id} for wallet {req.wallet_address} due to accepted transfer")
        
        # Invalidate any outstanding wallet verification challenges for this wallet
        pending_challenges = WalletVerificationChallenge.query.filter(
            WalletVerificationChallenge.wallet_address == transfer_request.wallet_address,
            WalletVerificationChallenge.used == False
        ).all()
        
        for challenge in pending_challenges:
            challenge.used = True
            logging.info(f"Invalidated wallet verification challenge {challenge.id} for wallet {challenge.wallet_address} due to accepted transfer")
        
        # Commit the entire transaction atomically (accept + merge + invalidations)
        db.session.commit()
        
        logging.info(f"Transfer request {request_id} accepted and accounts merged: {merge_summary}")
        
        return jsonify({
            'success': True,
            'message': 'Transfer request accepted. All data has been merged into the requester\'s account.',
            'merge_summary': merge_summary
        })
        
    except ValueError as ve:
        db.session.rollback()
        logging.error(f"Validation error during transfer acceptance: {str(ve)}")
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error accepting transfer request: {str(e)}")
        return jsonify({'error': f'Failed to accept transfer request: {str(e)}'}), 500

@app.route('/api/wallet/decline-transfer', methods=['POST'])
@require_wallet_connection
def decline_transfer():
    """Decline a transfer request"""
    from models import TransferRequest
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    request_id = data.get('request_id')
    
    if not request_id:
        return jsonify({'error': 'Request ID required'}), 400
    
    try:
        transfer_request = TransferRequest.query.get(request_id)
        
        if not transfer_request:
            return jsonify({'error': 'Transfer request not found'}), 404
        
        if transfer_request.owner_id != user.id:
            logging.warning(f"User {user.id} attempted to decline transfer request {request_id} owned by {transfer_request.owner_id}")
            return jsonify({'error': 'You do not have permission to decline this request'}), 403
        
        if transfer_request.status != 'pending':
            return jsonify({'error': f'Transfer request is not pending (status: {transfer_request.status})'}), 400
        
        transfer_request.decline()
        
        logging.info(f"Transfer request declined: request_id={request_id}, owner={user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Transfer request declined successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error declining transfer request: {str(e)}")
        return jsonify({'error': f'Failed to decline transfer request: {str(e)}'}), 500

# App routes
@app.route('/app')
def app_home():
    """Main app - redirects to marketplace (accessible without wallet)"""
    # Always redirect to marketplace, wallet connection via modal
    return redirect(url_for('token_marketplace'))

@app.route('/app/dashboard')
def app_dashboard():
    """User dashboard with stats and portfolio - now includes activities and achievements"""
    user = get_current_user()
    if not user:
        return redirect(url_for('token_marketplace'))
    
    # Evaluate and award achievements
    achievement_progress = evaluate_user_achievements(user.id)
    
    # Get user's created tokens
    created_tokens = Token.query.filter_by(creator_id=user.id).all()
    
    # TODO: Replace with HolderService to fetch holdings from blockchain
    # For now, return empty list to remove database dependency
    holdings = []
    
    # Get user's activities with eager loading of related entities
    activities = Activity.query.options(
        joinedload(Activity.token),
        joinedload(Activity.achievement)
    ).filter_by(user_id=user.id).order_by(Activity.created_at.desc()).limit(20).all()
    
    # Get user's achievements with eager loading of achievement details
    user_achievements = UserAchievement.query.options(
        joinedload(UserAchievement.achievement)
    ).filter_by(user_id=user.id).all()
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
    
    # Get current KAS price from oracle
    from services.kas_oracle import oracle
    kas_price = oracle.get_kas_price()
    
    return render_template('app/dashboard.html', 
                         user=user,
                         achievement_progress=achievement_progress,
                         created_tokens=created_tokens, 
                         holdings=holdings,
                         activities=activities,
                         user_achievements=user_achievements,
                         user_achievement_ids=user_achievement_ids,
                         all_achievements=all_achievements,
                         total_achievements=total_achievements,
                         achievement_points=achievement_points,
                         referral=referral,
                         kas_price=kas_price)

# @app.route('/app/creator-portal')
# def creator_portal():
#     """Creator vesting portal page"""
#     user = get_current_user()
#     if not user:
#         return redirect(url_for('token_marketplace'))
#     
#     return render_template('app/creator_portal.html', user=user)

@app.route('/app/create', methods=['GET', 'POST'])
def create_token():
    """Token creation page and form handler"""
    user = get_current_user()
    if not user:
        return redirect(url_for('token_marketplace'))
    
    if request.method == 'POST':
        # Handle token creation form submission
        token_data = {
            'name': request.form.get('name'),
            'symbol': request.form.get('symbol'),
            'description': request.form.get('description', ''),
            'website': request.form.get('website', ''),
            'twitter': request.form.get('twitter', ''),
            'telegram': request.form.get('telegram', ''),
            'total_supply': request.form.get('total_supply', '1000000000'),
            'reserved_percentage': request.form.get('reserved_percentage', '0'),
            'anti_bot_enabled': request.form.get('anti_bot_enabled') == 'on',
            'airdrops_allocation': request.form.get('airdrops_allocation', '33'),
            'marketing_allocation': request.form.get('marketing_allocation', '33'),
            'team_allocation': request.form.get('team_allocation', '34')
        }
        
        # Use TokenService to create the token
        new_token = TokenService.create_token(user, token_data)
        
        if new_token:
            flash(f'🚀 Token "{new_token.name}" ({new_token.symbol}) created successfully! This is a UI demo - no actual blockchain deployment.', 'success')
            return redirect(url_for('token_marketplace'))
        else:
            flash('Error creating token. Please try again.', 'error')
            return redirect(url_for('create_token'))
    
    return render_template('app/create_token.html', user=user)

@app.route('/app/tokens')
@app.route('/app/marketplace')  # Add marketplace alias
@wallet_optional
def token_marketplace():
    """Token marketplace - main home page (pump.fun style) - accessible without wallet"""
    user = get_current_user()  # Will be None if not connected
    
    # Show only deployed tokens with eager loading of creator information
    tokens = Token.query.options(
        joinedload(Token.creator)
    ).filter(
        Token.deployment_status == 'deployed',
        Token.is_visible == True
    ).order_by(Token.created_at.desc()).all()
    
    # Add is_pro flag to each token for the template
    for token in tokens:
        token.is_pro = TokenService.is_pro_token(token)
        # Set default values for lazy loading
        token.volume_24h = 0
        token.price_change_24h = 0
        token.graduation_progress = 0
    
    # Skip server-side enrichment - will be loaded client-side via lazy loading
    # This dramatically improves page load time for marketplaces with many tokens
    
    return render_template('app/marketplace.html', tokens=tokens, user=user, now=datetime.now(timezone.utc))

@app.route('/app/token/<contract_address>')
def token_detail(contract_address):
    """Individual token detail page"""
    # Normalize address to lowercase for database lookup (Ethereum addresses are case-insensitive)
    contract_address = contract_address.lower()
    
    # Use case-insensitive comparison for PostgreSQL
    token = Token.query.options(
        joinedload(Token.creator),
        joinedload(Token.settings)  # Load token settings
    ).filter(db.func.lower(Token.contract_address) == contract_address).first_or_404()
    
    # Check if current user is the token owner
    user = get_current_user()
    is_owner = False
    if user and token.creator:
        is_owner = user.wallet_address.lower() == token.creator.wallet_address.lower()
    
    # Use TokenService to determine if token is pro
    is_pro_token = TokenService.is_pro_token(token)
    
    # Ensure token has settings using service
    token.settings = TokenService.ensure_token_settings(token)
    
    # Get KAS price from oracle (cached for 5 minutes)
    from services.kas_oracle import oracle
    kas_price = oracle.get_kas_price()
    
    # Get graduation threshold from platform settings
    graduation_threshold_usd = token.graduation_threshold  # Uses property that pulls from PlatformSettings
    
    # Calculate real-time price and market cap from blockchain (for non-graduated tokens)
    if not token.is_graduated and token.contract_address:
        try:
            from services.web3_service import get_web3_service
            web3_service = get_web3_service()
            
            # Check if contract exists on blockchain
            contract_code = web3_service.w3.eth.get_code(
                web3_service.w3.to_checksum_address(token.contract_address)
            )
            
            if len(contract_code) > 2:  # Contract exists ('0x' means no contract)
                # Get bonding pool contract to read both reserves
                pool = web3_service.get_bonding_pool_contract(token.contract_address)
                
                # Read both reserves
                kas_reserve_wei = pool.functions.virtualKasReserve().call()
                token_reserve_wei = pool.functions.virtualTokenReserve().call()
                
                kas_amount = kas_reserve_wei / 10**18
                token_amount = token_reserve_wei / 10**18
                
                # Calculate price per token (in KAS)
                if token_amount > 0:
                    price_in_kas = kas_amount / token_amount
                    token.current_price = price_in_kas
                else:
                    token.current_price = 0
                
                # Calculate real-time market cap for bonding curve
                # For constant product bonding curves (k = x * y), market cap = KAS reserve
                # This represents total value locked in pool (what users actually paid)
                # NOTE: Do NOT use price × circulating_supply - that overestimates because
                # it assumes all tokens were bought at current (high) price, but early
                # buyers paid much less due to the curve
                market_cap_kas = kas_amount  # Market cap in KAS = KAS reserve
                token.current_market_cap = market_cap_kas  # Store in KAS (will convert to USD in template using kas_price)
                
                app.logger.debug(
                    f"Real-time data for {token.symbol}: "
                    f"Price=${price_in_kas * kas_price:.8f}, "
                    f"Market Cap=${token.current_market_cap:.2f} "
                    f"(KAS reserve: {kas_amount:.8f}, Token reserve: {token_amount:.2f})"
                )
        except Exception as e:
            app.logger.debug(f"Could not fetch real-time data for {token.symbol}: {e}")
            # Keep existing database values as fallback
    
    # Calculate 24h price change percentage
    price_change_24h = TokenService.calculate_24h_price_change(token)
    
    # Get market cap ATH (in KAS)
    market_cap_ath = float(token.market_cap_ath) if token.market_cap_ath else float(token.current_market_cap)
    
    return render_template('app/token_detail.html', 
                         token=token, 
                         user=user,
                         is_owner=is_owner,
                         is_pro_token=is_pro_token,
                         kas_price=kas_price,
                         graduation_threshold_usd=graduation_threshold_usd,
                         price_change_24h=price_change_24h,
                         market_cap_ath=market_cap_ath)

# Fallback route for legacy numeric IDs (backwards compatibility)
@app.route('/app/token/<int:token_id>')
def token_detail_legacy(token_id):
    """Legacy route for backward compatibility - redirects to contract address"""
    token = Token.query.get_or_404(token_id)
    if token.contract_address:
        return redirect(url_for('token_detail', contract_address=token.contract_address))
    else:
        # Fallback for tokens without contract addresses
        user = get_current_user()
        is_owner = False
        if user and token.creator:
            is_owner = user.wallet_address.lower() == token.creator.wallet_address.lower()
        
        # Use TokenService to determine if token is pro
        is_pro_token = TokenService.is_pro_token(token)
        
        # Ensure token has settings
        token.settings = TokenService.ensure_token_settings(token)
        
        return render_template('app/token_detail.html', 
                             token=token, 
                             recent_trades=[],
                             user_holding=None,
                             user=user,
                             is_owner=is_owner,
                             is_pro_token=is_pro_token)

# Chat API endpoints
@app.route('/api/token/<contract_address>/messages', methods=['GET', 'POST'])
@require_wallet_connection
def token_messages(contract_address):
    """Get or send chat messages for a token"""
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    user = get_current_user()
    
    if request.method == 'GET':
        # Get messages with user info and profile, including reply-to relationships
        messages = ChatMessage.query.options(
            joinedload(ChatMessage.user).joinedload(User.profile),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.user).joinedload(User.profile)
        ).filter_by(
            token_id=token.id, 
            is_deleted=False
        ).order_by(ChatMessage.created_at.desc()).limit(50).all()
        
        # Get user's reactions for these messages
        message_ids = [msg.id for msg in messages]
        user_reactions = MessageReaction.query.filter(
            MessageReaction.message_id.in_(message_ids),
            MessageReaction.user_id == user.id
        ).all()
        user_loved_ids = {r.message_id for r in user_reactions}
        
        # Convert to dict format for frontend
        message_list = []
        for msg in reversed(messages):
            msg_dict = {
                'id': msg.id,
                'user': (msg.user.profile.username if msg.user.profile and msg.user.profile.username else msg.user.display_name) or msg.user.wallet_address[-6:],
                'wallet': msg.user.wallet_address,
                'is_twitter_verified': msg.user.is_twitter_verified,
                'message': msg.content,
                'message_type': msg.message_type,
                'love_count': msg.love_count,
                'is_loved_by_user': msg.id in user_loved_ids,
                'created_at': msg.created_at.isoformat(),
                'is_pinned': msg.is_pinned
            }
            
            # Add reply information if this message is a reply
            if msg.reply_to_id and msg.reply_to:
                reply_user_name = (msg.reply_to.user.profile.username if msg.reply_to.user.profile and msg.reply_to.user.profile.username else msg.reply_to.user.display_name) or msg.reply_to.user.wallet_address[-6:]
                msg_dict['reply_to'] = {
                    'id': msg.reply_to.id,
                    'user': reply_user_name,
                    'is_twitter_verified': msg.reply_to.user.is_twitter_verified,
                    'text': msg.reply_to.content[:100] + ('...' if len(msg.reply_to.content) > 100 else '')
                }
            
            message_list.append(msg_dict)
        
        return jsonify({'messages': message_list})
    
    elif request.method == 'POST':
        data = request.get_json()
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if len(message_text) > 500:
            return jsonify({'error': 'Message too long (max 500 characters)'}), 400
        
        # Create new message
        message = ChatMessage(
            token_id=token.id,
            user_id=user.id,
            content=message_text,
            message_type=data.get('message_type', 'regular'),
            reply_to_id=data.get('reply_to_id')  # Store reply_to_id if provided
        )
        db.session.add(message)
        db.session.commit()
        
        # Increment achievement counter (global tracking)
        user.total_messages_sent = (user.total_messages_sent or 0) + 1
        db.session.commit()
        
        # Track per-token engagement for PRO tokens
        from services.token_service import TokenService
        if TokenService.is_pro_token(token):
            # Creator exclusion: don't award points to token creators on their own tokens
            if user.id != token.creator_id:
                engagement = TokenEngagement.get_or_create(user.id, token.id)
                engagement.messages_sent = (engagement.messages_sent or 0) + 1
                engagement.community_points = (engagement.community_points or 0) + 1  # 1 point per message
                engagement.last_activity_at = datetime.now(timezone.utc)
                db.session.commit()
        
        # If this is a reply, load the reply_to information
        response_msg = {
            'id': message.id,
            'user': (user.profile.username if user.profile and user.profile.username else user.display_name) or user.wallet_address[-6:],
            'wallet': user.wallet_address,
            'is_twitter_verified': user.is_twitter_verified,
            'message': message.content,
            'created_at': message.created_at.isoformat()
        }
        
        if message.reply_to_id:
            db.session.refresh(message)  # Refresh to get the relationship
            if message.reply_to:
                reply_user_name = (message.reply_to.user.profile.username if message.reply_to.user.profile and message.reply_to.user.profile.username else message.reply_to.user.display_name) or message.reply_to.user.wallet_address[-6:]
                response_msg['reply_to'] = {
                    'id': message.reply_to.id,
                    'user': reply_user_name,
                    'is_twitter_verified': message.reply_to.user.is_twitter_verified,
                    'text': message.reply_to.content[:100] + ('...' if len(message.reply_to.content) > 100 else '')
                }
        
        return jsonify({
            'success': True,
            'message': response_msg
        })

@app.route('/api/token/<contract_address>/message/<int:message_id>', methods=['DELETE'])
@require_wallet_connection
def delete_message(contract_address, message_id):
    """Delete a message (token owner only)"""
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    user = get_current_user()
    
    # Verify that the user is the token owner
    if not token.creator or user.wallet_address.lower() != token.creator.wallet_address.lower():
        return jsonify({'error': 'Only token owner can delete messages'}), 403
    
    # Get the message
    message = ChatMessage.query.filter_by(id=message_id, token_id=token.id).first()
    
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    # Delete the message
    try:
        db.session.delete(message)
        db.session.commit()
        
        logging.info(f"Token owner {user.wallet_address} deleted message {message_id} in token {token.symbol}")
        
        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        })
    except Exception as e:
        logging.error(f"Failed to delete message: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete message'}), 500

@app.route('/api/token/<contract_address>/polls', methods=['GET', 'POST'])
@csrf.exempt
@require_wallet_connection
def token_polls(contract_address):
    """Get or create polls for a token"""
    from datetime import datetime, timedelta, timezone
    
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    user = get_current_user()
    
    if request.method == 'GET':
        # Get active polls with creator profile and options (avoid N+1)
        polls = Poll.query.options(
            joinedload(Poll.creator).joinedload(User.profile),
            selectinload(Poll.options)
        ).filter_by(token_id=token.id, is_active=True).all()
        
        poll_list = []
        for poll in polls:
            # Get options with vote counts
            options_data = []
            for option in poll.options:
                options_data.append({
                    'id': option.id,
                    'text': option.option_text,
                    'vote_count': option.vote_count
                })
            
            # Get creator display name safely
            creator_name = poll.creator.display_name or poll.creator.wallet_address[-6:]
            try:
                if hasattr(poll.creator, 'profile') and poll.creator.profile and poll.creator.profile.username:
                    creator_name = poll.creator.profile.username
            except:
                pass
                
            poll_list.append({
                'id': poll.id,
                'creator': creator_name,
                'question': poll.question,
                'options': options_data,
                'total_votes': poll.total_votes,
                'vote_cost': int(poll.vote_cost) if poll.vote_cost else 0,
                'created_at': poll.created_at.isoformat(),
                'ends_at': poll.ends_at.isoformat() if poll.ends_at else None
            })
        
        return jsonify({'polls': poll_list})
    
    elif request.method == 'POST':
        data = request.get_json()
        
        question = data.get('question', '').strip()
        options_text = data.get('options', [])
        vote_cost = data.get('vote_cost', 100)
        duration_hours = data.get('duration_hours', 24)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        if len(options_text) < 2:
            return jsonify({'error': 'At least 2 options required'}), 400
        
        try:
            # Create poll
            poll = Poll(
                token_id=token.id,
                creator_id=user.id,
                question=question,
                vote_cost=vote_cost,
                ends_at=datetime.now(timezone.utc) + timedelta(hours=duration_hours)
            )
            db.session.add(poll)
            db.session.flush()  # Get poll ID
            
            # Create options
            for opt_text in options_text:
                option = PollOption(
                    poll_id=poll.id,
                    option_text=opt_text
                )
                db.session.add(option)
            
            db.session.commit()
            
            # Track per-token engagement for PRO tokens
            from services.token_service import TokenService
            if TokenService.is_pro_token(token):
                # Creator exclusion: don't award points to token creators on their own tokens
                if user.id != token.creator_id:
                    engagement = TokenEngagement.get_or_create(user.id, token.id)
                    engagement.polls_created = (engagement.polls_created or 0) + 1
                    engagement.community_points = (engagement.community_points or 0) + 5  # 5 points per poll
                    engagement.last_activity_at = datetime.now(timezone.utc)
                    db.session.commit()
            
            # Get creator display name safely
            creator_name = user.display_name or user.wallet_address[-6:]
            try:
                if hasattr(user, 'profile') and user.profile and user.profile.username:
                    creator_name = user.profile.username
            except:
                pass
            
            return jsonify({
                'success': True,
                'poll': {
                    'id': poll.id,
                    'creator': creator_name,
                    'question': poll.question,
                    'created_at': poll.created_at.isoformat()
                }
            })
        except Exception as e:
            logging.error(f"Failed to create poll: {e}")
            db.session.rollback()
            return jsonify({'error': 'Failed to create poll'}), 500

@app.route('/api/token/<contract_address>/polls/<int:poll_id>/vote', methods=['POST'])
@csrf.exempt
@require_wallet_connection
def vote_on_poll(contract_address, poll_id):
    """Vote on a poll"""
    user = get_current_user()
    data = request.get_json()
    option_id = data.get('option_id')
    
    if not option_id:
        return jsonify({'error': 'Option ID required'}), 400
    
    # Get poll and option
    poll = Poll.query.get_or_404(poll_id)
    option = PollOption.query.filter_by(id=option_id, poll_id=poll_id).first_or_404()
    
    # Check if already voted
    existing_vote = PollVote.query.filter_by(poll_id=poll_id, user_id=user.id).first()
    if existing_vote:
        return jsonify({'error': 'Already voted on this poll'}), 400
    
    # Check user has enough tokens (would need holdings check here)
    # For now, just record the vote
    
    # Create vote
    vote = PollVote(
        poll_id=poll_id,
        option_id=option_id,
        user_id=user.id
    )
    db.session.add(vote)
    
    # Update vote count
    option.vote_count += 1
    
    db.session.commit()
    
    # Track per-token engagement for PRO tokens
    token = poll.token
    from services.token_service import TokenService
    if TokenService.is_pro_token(token):
        # Creator exclusion: don't award points to token creators on their own tokens
        if user.id != token.creator_id:
            engagement = TokenEngagement.get_or_create(user.id, token.id)
            engagement.polls_voted = (engagement.polls_voted or 0) + 1
            engagement.community_points = (engagement.community_points or 0) + 2  # 2 points per vote
            engagement.last_activity_at = datetime.now(timezone.utc)
            db.session.commit()
    
    return jsonify({'success': True, 'new_vote_count': option.vote_count})

@app.route('/api/token/<contract_address>/holdings', methods=['GET'])
def get_token_holdings(contract_address):
    """Get user's token holdings for verification"""
    wallet_address = request.headers.get('X-Wallet-Address')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    # Get token (case-insensitive lookup)
    token = Token.query.filter(
        db.func.lower(Token.contract_address) == contract_address.lower()
    ).first_or_404()
    
    # Use HolderService to get balance from blockchain
    from services.holder_service import HolderService
    holding_info = HolderService.get_user_holding_info(wallet_address, token.contract_address)
    
    return jsonify(holding_info)

@app.route('/api/position/<contract_address>', methods=['GET'])
@csrf.exempt
@cache.cached(timeout=5, key_prefix=lambda: f"position_{request.view_args['contract_address']}_{request.headers.get('X-Wallet-Address', 'none').lower()}")
def get_position_metrics_api(contract_address):
    """Get user's position metrics with FTX-style average-cost tracking
    
    Returns weighted average entry price, position size, and unrealized P&L
    
    Headers:
        X-Wallet-Address: User's wallet address (required)
    
    Response:
        {
            "success": true,
            "position_qty": "507.754",
            "avg_entry_price_kas": "0.922735281234",
            "avg_entry_mc_kas": "167.771",
            "unrealized_pnl_kas": "6.484",
            "unrealized_pnl_pct": "3.87",
            "realized_pnl_kas": "0.000",
            "current_price_kas": "0.964379900147"
        }
    """
    wallet_address = request.headers.get('X-Wallet-Address')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    # Get token (case-insensitive lookup)
    token = Token.query.filter(
        db.func.lower(Token.contract_address) == contract_address.lower()
    ).first_or_404()
    
    # Resolve wallet to user (handles linked wallets)
    user = User.resolve_wallet_to_user(wallet_address)
    if not user:
        # No trades yet - return zero position
        return jsonify({
            'success': True,
            'position_qty': '0',
            'avg_entry_price_kas': '0',
            'avg_entry_mc_kas': '0',
            'unrealized_pnl_kas': '0',
            'unrealized_pnl_pct': '0',
            'realized_pnl_kas': '0',
            'current_price_kas': '0'
        })
    
    # Get current price from blockchain (real-time)
    from services.web3_service import get_web3_service
    from decimal import Decimal
    web3_service = get_web3_service()
    
    try:
        # Get current reserves to calculate price and market cap
        virtual_kas_reserve = web3_service.get_virtual_kas_reserve(token.contract_address)
        virtual_token_reserve = web3_service.get_virtual_token_reserve(token.contract_address)
        
        # Convert from wei to KAS
        current_market_cap_kas = Decimal(str(virtual_kas_reserve)) / Decimal('1000000000000000000')
        
        if virtual_token_reserve > 0:
            current_price_kas = Decimal(str(virtual_kas_reserve)) / Decimal(str(virtual_token_reserve))
        else:
            current_price_kas = Decimal('0')
        
        logging.info(
            f"📊 Position API - current_market_cap_kas={current_market_cap_kas}, "
            f"current_price_kas={current_price_kas}, "
            f"virtual_kas_reserve={virtual_kas_reserve}, "
            f"virtual_token_reserve={virtual_token_reserve}"
        )
    except Exception as e:
        logging.error(f"Failed to get current price for {contract_address}: {e}")
        current_price_kas = Decimal('0')
        current_market_cap_kas = Decimal('0')
    
    # Compute position metrics with P&L
    from services.position_service import PositionService
    metrics = PositionService.get_position_metrics(user, token, current_price_kas, current_market_cap_kas)
    
    if metrics:
        logging.info(
            f"📊 Position metrics returned: avg_entry_mc_kas={metrics.get('avg_entry_mc_kas')}, "
            f"avg_entry_price_kas={metrics.get('avg_entry_price_kas')}"
        )
    
    if not metrics:
        return jsonify({'error': 'Failed to compute position'}), 500
    
    # Format response (convert Decimals to strings for JSON)
    return jsonify({
        'success': True,
        'position_qty': str(metrics['qty_remaining']),
        'avg_entry_price_kas': str(metrics['avg_entry_price_kas']),
        'avg_entry_mc_kas': str(metrics['avg_entry_mc_kas']),
        'unrealized_pnl_kas': str(metrics['unrealized_pnl_kas']),
        'unrealized_pnl_pct': str(metrics['unrealized_pnl_pct']),
        'realized_pnl_kas': str(metrics.get('realized_pnl_kas', Decimal('0'))),
        'current_price_kas': str(current_price_kas)
    })

@app.route('/api/token/<contract_address>/spotlight', methods=['GET'])
def token_spotlight_get(contract_address):
    """Get spotlight messages - no auth required"""
    try:
        from datetime import datetime, timedelta, timezone
        
        # Normalize address to lowercase for case-insensitive lookup
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == contract_address.lower()
        ).first_or_404()
        
        # Get active spotlight messages (only those less than 1 hour old)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        spotlights = ChatMessage.query.options(
            joinedload(ChatMessage.user).joinedload(User.profile)
        ).filter(
            ChatMessage.token_id == token.id,
            ChatMessage.is_pinned == True,
            ChatMessage.is_deleted == False,
            ChatMessage.created_at >= one_hour_ago
        ).order_by(ChatMessage.created_at.desc()).limit(5).all()
        
        spotlight_list = []
        for msg in spotlights:
            expires_at = msg.created_at + timedelta(hours=1)
            expires_at_ms = int(expires_at.timestamp() * 1000)
            spotlight_list.append({
                'id': msg.id,
                'user': (msg.user.profile.username if msg.user.profile and msg.user.profile.username else msg.user.display_name) or msg.user.wallet_address[-6:],
                'message': msg.content,
                'created_at': msg.created_at.isoformat(),
                'expires_at_ms': expires_at_ms
            })
        
        return jsonify({'spotlights': spotlight_list})
    except Exception as e:
        logging.error(f"❌ Spotlight GET error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to get spotlights'}), 500

@app.route('/api/token/<contract_address>/spotlight', methods=['POST'])
@csrf.exempt
@require_wallet_connection
def token_spotlight_post(contract_address):
    """Create spotlight message - TOKEN GATED, requires session auth!"""
    try:
        from datetime import datetime, timedelta, timezone
        
        # Debug: Check session
        logging.debug(f"🔍 Spotlight POST - Session data: {dict(session)}")
        logging.debug(f"🔍 Spotlight POST - Headers: {dict(request.headers)}")
        
        # Normalize address to lowercase for case-insensitive lookup
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == contract_address.lower()
        ).first_or_404()
        
        # Get authenticated user from session
        user = get_current_user()
        if not user:
            logging.error(f"❌ Spotlight: User not found in session. Session: {dict(session)}")
            return jsonify({'error': 'Wallet connection required'}), 401
        
        # Parse request
        data = request.get_json()
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'error': 'Message cannot be empty'}), 400
            
        # Get token settings for minimum tokens required
        settings = TokenSettings.query.filter_by(token_id=token.id).first()
        min_tokens_for_spotlight = 500  # Default
        if settings:
            min_tokens_for_spotlight = settings.min_tokens_for_spotlight or 500
        
        # VERIFY USER ACTUALLY HOLDS ENOUGH TOKENS (TOKEN GATE!) - Use HolderService
        from services.holder_service import HolderService
        has_enough_tokens = HolderService.user_holds_min_tokens(
            user.wallet_address, 
            token.contract_address, 
            min_tokens_for_spotlight
        )
        
        if not has_enough_tokens:
            user_balance = HolderService.get_user_balance(user.wallet_address, token.contract_address)
            return jsonify({'error': f'You need to hold at least {min_tokens_for_spotlight} {token.symbol} tokens to create spotlight messages (You hold: {int(user_balance)})'}), 403
        
        # User has enough tokens - create spotlight message (NO DEDUCTION!)
        message = ChatMessage(
            token_id=token.id,
            user_id=user.id,
            content=message_text,
            message_type='spotlight',
            is_pinned=True
        )
        db.session.add(message)
        db.session.commit()
        
        # Schedule unpinning after 1 hour (would need a background task)
        # For now, spotlight messages will stay pinned until manually removed
        
        return jsonify({
            'success': True,
            'spotlight': {
                'id': message.id,
                'user': (user.profile.username if user.profile and user.profile.username else user.display_name) or user.wallet_address[-6:],
                'message': message.content,
                'wallet': user.wallet_address,
                'created_at': message.created_at.isoformat()
            }
        })
    except Exception as e:
        logging.error(f"❌ Spotlight error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to process spotlight request'}), 500

@app.route('/api/token/<contract_address>/message/<int:message_id>/react', methods=['POST'])
@require_wallet_connection
def react_to_message(contract_address, message_id):
    """Add reaction to a message"""
    user = get_current_user()
    data = request.get_json()
    reaction_type = data.get('reaction_type', 'love')
    
    # Get message
    message = ChatMessage.query.get_or_404(message_id)
    
    # Check if already reacted
    existing = MessageReaction.query.filter_by(
        message_id=message_id,
        user_id=user.id
    ).first()
    
    if existing:
        # Toggle reaction off
        db.session.delete(existing)
        message.love_count = max(0, message.love_count - 1)
        db.session.commit()
        return jsonify({'success': True, 'removed': True, 'new_count': message.love_count})
    else:
        # Add reaction
        reaction = MessageReaction(
            message_id=message_id,
            user_id=user.id,
            reaction_type=reaction_type
        )
        db.session.add(reaction)
        message.love_count += 1
        db.session.commit()
        
        # Track per-token engagement for PRO tokens (award to message author)
        token = message.token
        from services.token_service import TokenService
        if TokenService.is_pro_token(token):
            # Creator exclusion: don't award points to token creators on their own tokens
            if message.user_id != token.creator_id:
                engagement = TokenEngagement.get_or_create(message.user_id, token.id)
                engagement.reactions_received = (engagement.reactions_received or 0) + 1
                engagement.community_points = (engagement.community_points or 0) + 1  # 1 point per reaction
                engagement.last_activity_at = datetime.now(timezone.utc)
                db.session.commit()
        
        return jsonify({'success': True, 'added': True, 'new_count': message.love_count})

@app.route('/api/token/<contract_address>/settings/update', methods=['POST'])
@require_wallet_connection
def update_token_settings(contract_address):
    """Update token settings - only accessible by token creator"""
    user = get_current_user()
    
    # Get token
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Verify user is the token creator
    if not token.creator or user.wallet_address.lower() != token.creator.wallet_address.lower():
        return jsonify({'error': 'Only the token creator can update settings'}), 403
    
    # Get JSON data
    data = request.get_json()
    
    # Get or create token settings
    settings = TokenSettings.query.filter_by(token_id=token.id).first()
    if not settings:
        settings = TokenSettings(token_id=token.id)
        db.session.add(settings)
    
    # Update settings from request data
    if 'holders_only_chat' in data:
        settings.holders_only_chat = bool(data['holders_only_chat'])
    
    if 'min_tokens_to_chat' in data:
        settings.min_tokens_to_chat = int(data['min_tokens_to_chat'])
    
    if 'min_tokens_for_spotlight' in data:
        settings.min_tokens_for_spotlight = int(data['min_tokens_for_spotlight'])
    
    if 'min_tokens_to_create_poll' in data:
        settings.min_tokens_to_create_poll = int(data['min_tokens_to_create_poll'])
    
    # Commit changes
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'settings': {
                'holders_only_chat': settings.holders_only_chat,
                'min_tokens_to_chat': int(settings.min_tokens_to_chat or 0),
                'min_tokens_for_spotlight': int(settings.min_tokens_for_spotlight or 0),
                'min_tokens_to_create_poll': int(settings.min_tokens_to_create_poll or 0)
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update settings: {str(e)}'}), 500

@app.route('/api/token/<contract_address>/recent-trades', methods=['GET'])
@cache.cached(timeout=10, query_string=True)  # Cache for 10 seconds
def get_recent_trades(contract_address):
    """
    Get recent trades for a token using TradeEvent database
    
    Uses event indexer data for accurate KAS amounts (including sell trades).
    GraphQL API can't show KAS received from pool internal transfers.
    """
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Query recent TradeEvent records (populated by event indexer)
    recent_trades = TradeEvent.query.filter(
        TradeEvent.token_id == token.id
    ).order_by(TradeEvent.timestamp.desc()).limit(10).all()
    
    # Transform to API format
    trades_data = []
    for trade in recent_trades:
        trades_data.append({
            'trade_type': trade.trade_type,
            'token_amount': str(trade.token_amount),  # Keep as string to preserve precision
            'kas_amount': float(trade.kas_amount),
            'user_wallet_address': trade.user_wallet_address,
            'timestamp': trade.timestamp.isoformat() if trade.timestamp else None,
            'tx_hash': trade.tx_hash
        })
    
    return jsonify({
        'success': True,
        'trades': trades_data,
        'source': 'database'  # Indicate data source for debugging
    })

@app.route('/api/token/<contract_address>/leaderboard', methods=['GET'])
def get_token_leaderboard(contract_address):
    """
    Get community leaderboard for a PRO token
    Returns top users by community points with engagement details
    """
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Check if this is a PRO token
    from services.token_service import TokenService
    if not TokenService.is_pro_token(token):
        return jsonify({'error': 'Leaderboard is only available for PRO tokens'}), 400
    
    # Get limit from query params (default 20)
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)  # Cap at 100
    
    # Get top users by community points with joined user profiles
    from sqlalchemy.orm import joinedload
    top_engagements = TokenEngagement.query.options(
        joinedload(TokenEngagement.user).joinedload(User.profile)
    ).filter(
        TokenEngagement.token_id == token.id,
        TokenEngagement.community_points > 0
    ).order_by(
        TokenEngagement.community_points.desc()
    ).limit(limit).all()
    
    leaderboard = []
    for rank, engagement in enumerate(top_engagements, 1):
        user = engagement.user
        if not user:
            continue
        
        # Get display name (prefer username, then display_name, then twitter_handle, then wallet)
        display_name = user.wallet_address[-6:]
        if hasattr(user, 'profile') and user.profile:
            # First priority: Custom username (profile name)
            if user.profile.username:
                display_name = user.profile.username
            # Second priority: Twitter handle
            elif user.profile.twitter_handle:
                display_name = user.profile.twitter_handle
        # Third priority: Display name (from User model)
        if display_name == user.wallet_address[-6:] and user.display_name:
            display_name = user.display_name
        
        leaderboard.append({
            'rank': rank,
            'wallet_address': user.wallet_address,
            'display_name': display_name,
            'is_twitter_verified': user.is_twitter_verified,
            'community_points': engagement.community_points or 0,
            'messages_sent': engagement.messages_sent or 0,
            'polls_created': engagement.polls_created or 0,
            'polls_voted': engagement.polls_voted or 0,
            'trades_count': engagement.trades_count or 0,
            'holding_days': engagement.holding_days or 0,
            'diamond_hands_score': engagement.diamond_hands_score or 0,
            'reactions_received': engagement.reactions_received or 0
        })
    
    return jsonify({
        'success': True,
        'leaderboard': leaderboard,
        'total_users': len(leaderboard)
    })

@app.route('/api/token/<contract_address>/airdrop/available', methods=['GET'])
@require_wallet_connection
def get_airdrop_available(contract_address):
    """Get available airdrop amount based on vesting schedule"""
    from datetime import datetime, timezone
    
    user = get_current_user()
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Verify user is the token creator
    if not token.creator or user.wallet_address.lower() != token.creator.wallet_address.lower():
        return jsonify({'error': 'Only the token creator can view airdrop availability'}), 403
    
    # Calculate airdrop allocation
    total_airdrop_allocation = float(token.reserved_tokens or 0) * (float(token.airdrops_allocation) / 100.0)
    
    # Calculate unlocked amount based on vesting schedule (5% per day)
    # Make token.created_at timezone-aware if it's naive
    created_at = token.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    days_since_creation = (datetime.now(timezone.utc) - created_at).days
    unlocked_percentage = min(days_since_creation * 5, 100)  # 5% per day, max 100%
    unlocked_amount = total_airdrop_allocation * (unlocked_percentage / 100.0)
    
    # Calculate available amount (unlocked - already airdropped)
    already_airdropped = float(token.total_airdropped or 0)
    available_amount = max(unlocked_amount - already_airdropped, 0)
    
    return jsonify({
        'success': True,
        'total_allocation': int(total_airdrop_allocation),
        'unlocked_amount': int(unlocked_amount),
        'already_airdropped': int(already_airdropped),
        'available_amount': int(available_amount),
        'unlocked_percentage': unlocked_percentage,
        'days_since_creation': days_since_creation
    })

def get_airdrop_recipients(token, airdrop_type, amount_per_recipient, parameters):
    """
    Get list of recipients based on airdrop type and filters
    
    Args:
        token: Token object
        airdrop_type: Type of airdrop (active_chatters, token_holders, top_traders, etc.)
        amount_per_recipient: Amount each recipient receives
        parameters: Dict with type-specific filters (min_balance, min_messages, etc.)
    
    Returns:
        tuple: (recipients list, amounts list)
    """
    recipients = []
    
    if airdrop_type == 'active_chatters':
        # Get users with messages in this token's community
        min_messages = parameters.get('min_messages', 5)
        engagements = TokenEngagement.query.filter(
            TokenEngagement.token_id == token.id,
            TokenEngagement.messages_sent >= min_messages
        ).order_by(TokenEngagement.messages_sent.desc()).all()
        
        recipients = [eng.user.wallet_address for eng in engagements if eng.user and eng.user.wallet_address]
    
    elif airdrop_type == 'token_holders':
        # Get users holding this token
        min_balance = parameters.get('min_balance', 100)
        holdings = Holding.query.filter(
            Holding.token_id == token.id,
            Holding.token_amount >= min_balance
        ).order_by(Holding.token_amount.desc()).all()
        
        recipients = [h.user.wallet_address for h in holdings if h.user and h.user.wallet_address]
    
    elif airdrop_type == 'top_contributors':
        # Get top traders by volume
        limit = parameters.get('limit', 20)
        engagements = TokenEngagement.query.filter(
            TokenEngagement.token_id == token.id,
            TokenEngagement.trades_count > 0
        ).order_by(TokenEngagement.total_traded_volume.desc()).limit(limit).all()
        
        recipients = [eng.user.wallet_address for eng in engagements if eng.user and eng.user.wallet_address]
    
    elif airdrop_type == 'early_supporters':
        # Get earliest token holders
        limit = parameters.get('limit', 10)
        holdings = Holding.query.filter(
            Holding.token_id == token.id
        ).order_by(Holding.first_purchase.asc()).limit(limit).all()
        
        recipients = [h.user.wallet_address for h in holdings if h.user and h.user.wallet_address]
    
    elif airdrop_type == 'top_by_points':
        # Get users with highest community points (rewards most engaged)
        min_points = parameters.get('min_points', 10)
        limit = parameters.get('limit', 50)
        engagements = TokenEngagement.query.filter(
            TokenEngagement.token_id == token.id,
            TokenEngagement.community_points >= min_points
        ).order_by(TokenEngagement.community_points.desc()).limit(limit).all()
        
        recipients = [eng.user.wallet_address for eng in engagements if eng.user and eng.user.wallet_address]
    
    elif airdrop_type == 'diamond_holders':
        # Get users who've been holding for 90+ days (true believers)
        min_holding_days = parameters.get('min_holding_days', 90)
        limit = parameters.get('limit', 50)  # Cap at 50 to prevent huge recipient lists
        engagements = TokenEngagement.query.filter(
            TokenEngagement.token_id == token.id,
            TokenEngagement.holding_days >= min_holding_days,
            TokenEngagement.first_acquired_at.isnot(None)
        ).order_by(TokenEngagement.holding_days.desc()).limit(limit).all()
        
        recipients = [eng.user.wallet_address for eng in engagements if eng.user and eng.user.wallet_address]
    
    else:
        raise ValueError(f"Unsupported airdrop type: {airdrop_type}")
    
    # Build amounts array (same amount for all recipients)
    amounts = [amount_per_recipient] * len(recipients)
    
    return recipients, amounts

@app.route('/api/token/<contract_address>/airdrop/create', methods=['POST'])
@require_wallet_connection
def create_airdrop(contract_address):
    """Build transaction bundle for batch airdrop distribution"""
    from datetime import datetime, timezone
    from services.web3_service import get_web3_service, AIRDROP_DISTRIBUTOR_ADDRESS
    
    user = get_current_user()
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Verify user is the token creator
    if not token.creator or user.wallet_address.lower() != token.creator.wallet_address.lower():
        return jsonify({'error': 'Only the token creator can create airdrops'}), 403
    
    # Verify this is a PRO token with airdrop vesting
    if not token.airdrop_vesting_address:
        return jsonify({'error': 'This token does not have airdrop allocation'}), 400
    
    # Get request data
    data = request.get_json()
    airdrop_type = data.get('type')  # active_chatters, token_holders, top_contributors, early_supporters
    amount_per_recipient = int(data.get('amount_per_recipient', 0))
    parameters = data.get('parameters', {})
    
    # Validate airdrop type
    valid_types = ['active_chatters', 'token_holders', 'top_contributors', 'early_supporters', 'top_by_points', 'diamond_holders']
    if airdrop_type not in valid_types:
        return jsonify({'error': f'Invalid airdrop type. Valid types: {", ".join(valid_types)}'}), 400
    
    # Validate amount
    if amount_per_recipient <= 0:
        return jsonify({'error': 'Amount per recipient must be positive'}), 400
    
    try:
        # Get recipients based on type
        recipients, amounts = get_airdrop_recipients(token, airdrop_type, amount_per_recipient, parameters)
        
        if len(recipients) == 0:
            return jsonify({'error': 'No eligible recipients found'}), 400
        
        total_amount = sum(amounts)
        
        # Get web3 service
        web3_service = get_web3_service()
        
        # CRITICAL: Verify AirdropDistributor is deployed
        if AIRDROP_DISTRIBUTOR_ADDRESS == "0x0000000000000000000000000000000000000000":
            return jsonify({
                'error': 'Airdrop system not yet deployed. Contact support.'
            }), 503
        
        # Check creator's token balance
        creator_balance = web3_service.w3.eth.contract(
            address=web3_service.w3.to_checksum_address(token.contract_address),
            abi=web3_service.contracts['BondingCurvePoolABI']
        ).functions.balanceOf(web3_service.w3.to_checksum_address(user.wallet_address)).call()
        
        # Check vesting unlocked balance
        unlocked_in_vesting = web3_service.check_vesting_unlocked_balance(
            token.airdrop_vesting_address,
            vesting_type='airdrop'
        )
        
        total_available = creator_balance + unlocked_in_vesting
        
        # Validate sufficient balance
        if total_available < total_amount:
            return jsonify({
                'error': f'Insufficient tokens. Need {total_amount}, have {total_available} (wallet: {creator_balance}, unlocked: {unlocked_in_vesting})'
            }), 400
        
        # Build transaction bundle
        transactions = []
        
        # TX1: Withdraw from vesting (if needed)
        if creator_balance < total_amount and unlocked_in_vesting > 0:
            withdrawal_tx = web3_service.build_vesting_withdrawal_tx(
                user.wallet_address,
                token.airdrop_vesting_address,
                vesting_type='airdrop'
            )
            transactions.append({
                'type': 'withdrawal',
                'description': f'Withdraw {unlocked_in_vesting} tokens from vesting',
                'tx': withdrawal_tx
            })
        
        # TX2: Approve AirdropDistributor
        approval_tx = web3_service.build_token_approval_tx(
            user.wallet_address,
            token.contract_address,
            AIRDROP_DISTRIBUTOR_ADDRESS,
            total_amount
        )
        transactions.append({
            'type': 'approval',
            'description': f'Approve {total_amount} tokens for distribution',
            'tx': approval_tx
        })
        
        # TX3: Batch transfer
        batch_transfer_tx = web3_service.build_batch_transfer_tx(
            user.wallet_address,
            token.contract_address,
            recipients,
            amounts
        )
        transactions.append({
            'type': 'distribution',
            'description': f'Distribute to {len(recipients)} recipients',
            'tx': batch_transfer_tx
        })
        
        # Create airdrop record in DB
        airdrop = Airdrop(
            token_id=token.id,
            creator_id=user.id,
            airdrop_type=airdrop_type,
            total_amount=total_amount,
            parameters=parameters,
            recipient_count=len(recipients),
            distribution_type='push',  # Push-based batch distribution
            status='pending'  # Will be 'completed' after TXs are signed
        )
        
        db.session.add(airdrop)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'airdrop_id': airdrop.id,
            'transactions': transactions,
            'recipient_count': len(recipients),
            'total_amount': total_amount,
            'available_balance': {
                'wallet': creator_balance,
                'unlocked_vesting': unlocked_in_vesting,
                'total': total_available
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to create airdrop: {str(e)}")
        return jsonify({'error': f'Failed to create airdrop: {str(e)}'}), 500

# Post-Graduation DEX Integration Endpoints
@app.route('/api/token/<address>/graduation-status', methods=['GET'])
@cache.cached(timeout=10, query_string=True)  # Cache for 10 seconds
def api_token_graduation_status(address):
    """
    Get graduation status for a token
    
    Response for non-graduated tokens:
    {
        "success": true,
        "is_graduated": false,
        "current_market_cap": 45000.00,
        "graduation_threshold": 70000,
        "progress_percent": 64.29,
        "message": "Token has not graduated yet"
    }
    
    Response for graduated tokens:
    {
        "success": true,
        "is_graduated": true,
        "dex_pool": {
            "pool_address": "0x...",
            "nft_position_id": 123,
            "dex_name": "Kaspa Finance",
            "dex_url": "https://kaspa.finance/pool/0x...",
            "liquidity": "N/A",
            "price": "0.000123",
            "volume_24h": "N/A"
        }
    }
    """
    try:
        # Normalize address (lowercase, strip whitespace)
        address_normalized = address.strip().lower()
        
        # Flexible validation: Accept various formats
        if not address_normalized or len(address_normalized) < 10:
            return jsonify({'success': False, 'error': 'Invalid address format'}), 400
        
        # Case-insensitive lookup
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == address_normalized
        ).first()
        
        if not token:
            logging.debug(f"Token not found: {address}")
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Check if token has graduated
        if not token.is_graduated:
            # Get real-time market cap from blockchain
            from services.web3_service import get_web3_service
            from services.kas_oracle import oracle as kas_oracle
            
            web3_service = get_web3_service()
            current_market_cap = None
            
            try:
                # Validate contract address exists
                if not token.contract_address:
                    app.logger.warning(f"Token {token.symbol} has no contract_address set - using DB value")
                    current_market_cap = float(token.current_market_cap) if token.current_market_cap else 0
                else:
                    # Check if contract exists on blockchain
                    contract_code = web3_service.w3.eth.get_code(
                        web3_service.w3.to_checksum_address(token.contract_address)
                    )
                    
                    if len(contract_code) <= 2:  # '0x' means no contract
                        app.logger.warning(
                            f"No contract deployed at {token.contract_address} for token {token.symbol} "
                            f"(likely test data) - using DB value ${token.current_market_cap}"
                        )
                        current_market_cap = float(token.current_market_cap) if token.current_market_cap else 0
                    else:
                        # Contract exists - read real-time virtualKasReserve
                        app.logger.info(f"Reading virtualKasReserve from BondingCurvePool at {token.contract_address}")
                        kas_reserve_wei = web3_service.get_virtual_kas_reserve(token.contract_address)
                        
                        # Get current KAS/USD price
                        kas_price_usd = kas_oracle.get_kas_price()
                        
                        # Calculate real-time market cap
                        kas_amount = kas_reserve_wei / 10**18
                        current_market_cap = kas_amount * kas_price_usd
                        
                        app.logger.info(
                            f"✅ Real-time market cap for {token.symbol}: ${current_market_cap:.2f} "
                            f"(virtualKasReserve: {kas_amount:.8f} KAS)"
                        )
                
            except Exception as e:
                app.logger.error(
                    f"❌ Failed to get real-time market cap for {token.contract_address}: "
                    f"{type(e).__name__}: {str(e)} - Falling back to DB value"
                )
                # Fallback to database value if blockchain call fails
                current_market_cap = float(token.current_market_cap) if token.current_market_cap else 0
            
            # Get graduation threshold from token property (which pulls from PlatformSettings)
            graduation_threshold = token.graduation_threshold
            
            # Calculate progress
            progress_percent = (current_market_cap / graduation_threshold) * 100 if graduation_threshold else 0
            
            return jsonify({
                'success': True,
                'is_graduated': False,
                'graduation_status': token.graduation_status or 'active',
                'current_market_cap': round(current_market_cap, 2),
                'graduation_threshold': graduation_threshold,
                'progress_percent': round(progress_percent, 2),
                'message': 'Token has not graduated yet'
            })
        
        # Token has graduated - return DEX pool data
        # Basic pool data from database
        pool_data = {
            'pool_address': token.liquidity_pool_address,
            'nft_position_id': token.nft_position_id,
            'dex_name': 'Kaspa Finance',
            'dex_url': f'https://kaspa.finance/pool/{token.liquidity_pool_address}'
        }
        
        # Add price data from token if available
        if token.current_price:
            pool_data['price'] = str(token.current_price)
        else:
            pool_data['price'] = 'N/A'
        
        # Liquidity and volume require pool contract integration (not in scope)
        pool_data['liquidity'] = 'N/A'
        pool_data['volume_24h'] = 'N/A'
        
        return jsonify({
            'success': True,
            'is_graduated': True,
            'graduation_status': 'graduated',
            'dex_pool': pool_data
        })
        
    except ValueError as e:
        logging.error(f"Invalid address format: {address}, error: {str(e)}")
        return jsonify({'success': False, 'error': 'Invalid address format'}), 400
    except Exception as e:
        logging.error(f"Error fetching graduation status for {address}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch graduation status'}), 500

@app.route('/api/token/<address>/trigger-graduation', methods=['POST'])
def api_trigger_graduation(address):
    """
    Real-time graduation trigger endpoint
    
    Called by frontend when market cap crosses $50 threshold for instant graduation initiation
    instead of waiting for 60-second background monitor poll.
    
    Returns:
    {
        "success": true,
        "status": "graduation_initiated",
        "token_symbol": "TEST",
        "market_cap_usd": 52.34,
        "message": "Graduation initiated successfully"
    }
    """
    try:
        # Normalize address
        address_normalized = address.strip().lower()
        
        # Get token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == address_normalized
        ).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Check if already graduated or in progress
        if token.is_graduated:
            return jsonify({
                'success': False,
                'error': 'Token already graduated',
                'status': 'already_graduated'
            }), 400
        
        if token.graduation_status in ['initiating', 'completing']:
            return jsonify({
                'success': False,
                'error': 'Graduation already in progress',
                'status': token.graduation_status
            }), 400
        
        # Call graduation monitor check function (same as background service)
        from services.graduation_monitor import check_token_graduation
        
        logging.info(f"🎯 Real-time graduation trigger for {token.symbol} ({address})")
        result = check_token_graduation(token)
        
        if result['status'] == 'graduation_initiated':
            return jsonify({
                'success': True,
                'status': result['status'],
                'token_symbol': token.symbol,
                'market_cap_usd': result['market_cap_usd'],
                'graduation_status': token.graduation_status,
                'message': 'Graduation initiated successfully'
            })
        elif result['status'] == 'not_ready':
            return jsonify({
                'success': False,
                'error': 'Market cap below graduation threshold',
                'status': 'not_ready',
                'market_cap_usd': result['market_cap_usd'],
                'progress_pct': result['progress_pct']
            }), 400
        elif result['status'] == 'error':
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'status': 'error'
            }), 500
        else:
            return jsonify({
                'success': False,
                'error': f"Unexpected status: {result['status']}",
                'status': result['status']
            }), 500
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error triggering graduation for {address}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<address>/stats', methods=['GET'])
@cache.cached(timeout=10, query_string=True)  # Cache for 10 seconds
def api_token_stats(address):
    """
    Lightweight JSON endpoint for token stats (replaces HTML scraping)
    
    Returns real-time token statistics for client-side updates without page reload.
    
    Response:
    {
        "success": true,
        "market_cap": 95.88,
        "market_cap_formatted": "$95.88",
        "price": 0.00000234,
        "price_formatted": "$0.00000234",
        "price_change_24h": 5.2,
        "holders": 123,
        "volume_24h": 1234.56,
        "is_graduated": false
    }
    """
    try:
        logging.debug(f"📊 Stats request for token: {address}")
        # Normalize address
        address_normalized = address.strip().lower()
        
        # Get token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == address_normalized
        ).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        from services.web3_service import get_web3_service
        from services.kas_oracle import oracle as kas_oracle
        
        web3_service = get_web3_service()
        kas_price_usd = float(kas_oracle.get_kas_price())
        
        # Get real-time data from blockchain
        current_price_usd = 0
        current_price_kas = 0
        current_market_cap_usd = 0
        current_market_cap_kas = 0
        
        if not token.is_graduated and token.contract_address:
            try:
                # Check if contract exists
                contract_code = web3_service.w3.eth.get_code(
                    web3_service.w3.to_checksum_address(token.contract_address)
                )
                
                if len(contract_code) > 2:  # Contract exists
                    # Read blockchain reserves
                    pool = web3_service.get_bonding_pool_contract(token.contract_address)
                    kas_reserve_wei = pool.functions.virtualKasReserve().call()
                    token_reserve_wei = pool.functions.virtualTokenReserve().call()
                    
                    kas_amount = kas_reserve_wei / 10**18
                    token_amount = token_reserve_wei / 10**18
                    
                    # Calculate price per token (in KAS first, then convert to USD)
                    if token_amount > 0:
                        current_price_kas = kas_amount / token_amount
                        current_price_usd = current_price_kas * kas_price_usd
                    
                    # Market cap = KAS reserve * KAS price (in USD)
                    current_market_cap_kas = kas_amount
                    current_market_cap_usd = kas_amount * kas_price_usd
            except Exception as e:
                logging.error(f"Error fetching real-time stats: {e}")
                # ✅ FIX: Database stores USD values directly, NO multiplication needed
                # Convert Decimal to float to avoid type errors
                current_price_usd = float(token.current_price if token.current_price else 0)
                current_price_kas = current_price_usd / kas_price_usd if kas_price_usd > 0 else 0
                current_market_cap_usd = float(token.current_market_cap if token.current_market_cap else 0)
                current_market_cap_kas = current_market_cap_usd / kas_price_usd if kas_price_usd > 0 else 0
        else:
            # ✅ FIX: Graduated tokens - database values are already in USD
            # Convert Decimal to float to avoid type errors
            current_price_usd = float(token.current_price if token.current_price else 0)
            current_price_kas = current_price_usd / kas_price_usd if kas_price_usd > 0 else 0
            current_market_cap_usd = float(token.current_market_cap if token.current_market_cap else 0)
            current_market_cap_kas = current_market_cap_usd / kas_price_usd if kas_price_usd > 0 else 0
        
        # Format values for display
        def format_usd(val):
            if val >= 1e6:
                return f"${val/1e6:.2f}M"
            elif val >= 1e3:
                return f"${val/1e3:.2f}K"
            else:
                return f"${val:.2f}"
        
        def format_price(val):
            if val >= 1:
                return f"${val:.4f}"
            else:
                return f"${val:.8f}"
        
        # Calculate graduation progress
        # Get threshold from platform settings (dynamic)
        from models import PlatformSettings
        graduation_threshold_usd = float(PlatformSettings.get_settings().graduation_threshold_usd)
        progress_to_graduation = min(100, (current_market_cap_usd / graduation_threshold_usd * 100)) if graduation_threshold_usd > 0 else 0
        
        # Format numbers
        def format_number(val):
            if val >= 1e9:
                return f"{val/1e9:.2f}B"
            elif val >= 1e6:
                return f"{val/1e6:.2f}M"
            elif val >= 1e3:
                return f"{val/1e3:.2f}K"
            else:
                return f"{val:.2f}"
        
        # Get 24h metrics from MarketplaceService (cached for 10s)
        price_change_24h = 0
        volume_24h = 0
        volume_24h_formatted = '$0'
        
        try:
            from services.marketplace_service import MarketplaceService
            metrics = MarketplaceService.get_24h_metrics(token.contract_address)
            price_change_24h = metrics['price_change_24h']
            volume_24h = metrics['volume_24h']
            volume_24h_formatted = format_usd(volume_24h)
        except Exception as e:
            logging.debug(f"Could not fetch 24h metrics for {token.contract_address}: {e}")
        
        # Get DEX pool data for graduated tokens
        dex_pool_data = None
        if token.is_graduated and token.liquidity_pool_address:
            try:
                reserves = web3_service.get_dex_pool_reserves(token.liquidity_pool_address)
                dex_pool_data = {
                    'pool_address': token.liquidity_pool_address,
                    'price': reserves.get('price', 0),
                    'liquidity': reserves.get('liquidity', 0),
                    'sqrtPriceX96': str(reserves.get('sqrtPriceX96', 0)),
                    'fee_tier': token.dex_pool_fee_tier or 3000
                }
            except Exception as e:
                logging.debug(f"Could not fetch DEX pool reserves for {token.contract_address}: {e}")
        
        # Return single response with all data
        response_data = {
            'success': True,
            # Price data
            'price': current_price_usd,
            'price_formatted': format_price(current_price_usd),
            'price_kas': current_price_kas,
            'price_kas_formatted': f"{current_price_kas:.6f} KAS",
            
            # Market cap data
            'market_cap': current_market_cap_usd,
            'market_cap_formatted': format_usd(current_market_cap_usd),
            'market_cap_kas': current_market_cap_kas,
            'market_cap_kas_formatted': f"{format_number(current_market_cap_kas)} KAS",
            
            # Supply and holders
            'circulating_supply': float(token.circulating_supply if token.circulating_supply else 0),
            'circulating_supply_formatted': format_number(float(token.circulating_supply if token.circulating_supply else 0)),
            'holders': token.holder_count or 0,
            
            # Graduation progress
            'progress_to_graduation': round(progress_to_graduation, 1),
            'graduation_threshold_usd': graduation_threshold_usd,
            'graduation_threshold_formatted': format_usd(graduation_threshold_usd),
            
            # Trading metrics (enriched from MarketplaceService)
            'price_change_24h': price_change_24h,
            'volume_24h': volume_24h,
            'volume_24h_formatted': volume_24h_formatted,
            
            # Status
            'is_graduated': token.is_graduated,
            'graduation_status': token.graduation_status or 'active'
        }
        
        # Add DEX pool data if available
        if dex_pool_data:
            response_data['dex'] = dex_pool_data
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"❌ Error fetching token stats for {address}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'Failed to fetch stats: {str(e)}'}), 500

@app.route('/api/token/<address>/user-trades', methods=['GET'])
def api_token_user_trades(address):
    """
    Get user's trade history for a specific token (for chart markers)
    
    Query Parameters:
        wallet_address: User's wallet address
    
    Response:
    {
        "success": true,
        "trades": [
            {
                "timestamp": "2025-10-20T10:30:00",
                "type": "buy",
                "price_usd": 0.00000234,
                "price_kas": 0.000045,
                "kas_amount": 100.0,
                "token_amount": 1000000.0,
                "tx_hash": "0x..."
            }
        ],
        "average_entry_price_usd": 0.00000234,
        "average_entry_price_kas": 0.000045,
        "total_tokens_bought": 1000000.0,
        "total_tokens_sold": 0.0,
        "net_position": 1000000.0
    }
    """
    try:
        # Get wallet address from query parameter
        wallet_address = request.args.get('wallet_address')
        if not wallet_address:
            return jsonify({'success': False, 'error': 'wallet_address parameter required'}), 400
        
        # Normalize addresses
        address_normalized = address.strip().lower()
        wallet_normalized = wallet_address.strip().lower()
        
        # Get token
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == address_normalized
        ).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        from services.kas_oracle import oracle as kas_oracle
        kas_price_usd = float(kas_oracle.get_kas_price())
        
        # Query all trades for this user and token, ordered by timestamp
        trades = TradeEvent.query.filter(
            TradeEvent.token_id == token.id,
            db.func.lower(TradeEvent.user_wallet_address) == wallet_normalized
        ).order_by(TradeEvent.timestamp.asc()).all()
        
        # Format trades for chart
        formatted_trades = []
        total_kas_spent = 0
        total_tokens_bought = 0
        total_tokens_sold = 0
        
        for trade in trades:
            # Calculate price (price per token in KAS)
            # Token amounts are stored in wei (10^18), need to normalize
            kas_amount = float(trade.kas_amount)
            token_amount_wei = float(trade.token_amount)
            token_amount = token_amount_wei / 10**18  # Convert from wei to tokens
            
            if token_amount > 0:
                price_kas = kas_amount / token_amount
                price_usd = price_kas * kas_price_usd
            else:
                price_kas = 0
                price_usd = 0
            
            # Track buy/airdrop totals for average entry calculation
            if trade.trade_type == 'buy':
                total_kas_spent += kas_amount
                total_tokens_bought += token_amount
            elif trade.trade_type == 'airdrop':
                # Airdrops add to position at $0 cost (reduces average entry)
                total_tokens_bought += token_amount
                # Do NOT add to total_kas_spent (airdrops are free)
            elif trade.trade_type == 'sell':
                total_tokens_sold += token_amount
            
            formatted_trades.append({
                'timestamp': trade.timestamp.isoformat() if trade.timestamp else None,
                'type': trade.trade_type,
                'price_usd': price_usd,
                'price_kas': price_kas,
                'kas_amount': kas_amount,
                'token_amount': token_amount,  # Now in human-readable format
                'tx_hash': trade.tx_hash
            })
        
        # Calculate weighted average entry price (only from buys)
        average_entry_price_kas = 0
        average_entry_price_usd = 0
        
        if total_tokens_bought > 0:
            average_entry_price_kas = total_kas_spent / total_tokens_bought
            average_entry_price_usd = average_entry_price_kas * kas_price_usd
        
        return jsonify({
            'success': True,
            'trades': formatted_trades,
            'average_entry_price_usd': average_entry_price_usd,
            'average_entry_price_kas': average_entry_price_kas,
            'total_tokens_bought': total_tokens_bought,
            'total_tokens_sold': total_tokens_sold,
            'net_position': total_tokens_bought - total_tokens_sold
        })
        
    except Exception as e:
        logging.error(f"Error fetching user trades for {address}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch user trades'}), 500

@app.route('/api/token/<address>/dex-pool', methods=['GET'])
def api_token_dex_pool(address):
    """
    Get DEX pool information for graduated token
    
    Response for graduated tokens:
    {
        "success": true,
        "is_graduated": true,
        "dex_pool": {
            "pool_address": "0x...",
            "nft_position_id": 123,
            "dex_name": "Kaspa Finance",
            "dex_url": "https://kaspa.finance/pool/0x...",
            "liquidity": "N/A",
            "price": "0.000123",
            "volume_24h": "N/A"
        }
    }
    
    Response for non-graduated tokens:
    {
        "success": true,
        "is_graduated": false,
        "message": "Token has not graduated yet"
    }
    """
    try:
        # Normalize address (lowercase, strip whitespace)
        address_normalized = address.strip().lower()
        
        # Flexible validation: Accept various formats
        # - EVM format: 0x... (42 chars)
        # - Kaspa native format: kas:... or other prefixes
        # - Just check it's not empty and reasonable length
        if not address_normalized or len(address_normalized) < 10:
            return jsonify({'success': False, 'error': 'Invalid address format'}), 400
        
        # Case-insensitive lookup - let DB determine if valid
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == address_normalized
        ).first()
        
        if not token:
            logging.debug(f"Token not found: {address}")
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Check if token has graduated
        if not token.is_graduated:
            return jsonify({
                'success': True,
                'is_graduated': False,
                'message': 'Token has not graduated yet'
            })
        
        # Get web3 service (for potential future blockchain data fetching)
        web3_service = get_web3_service()
        
        # Basic pool data from database
        pool_data = {
            'pool_address': token.liquidity_pool_address,
            'nft_position_id': token.nft_position_id,
            'dex_name': 'Kaspa Finance',
            'dex_url': f'https://kaspa.finance/pool/{token.liquidity_pool_address}'
        }
        
        # Add price data from token if available
        if token.current_price:
            pool_data['price'] = str(token.current_price)
        else:
            pool_data['price'] = 'N/A'
        
        # Liquidity and volume require pool contract integration (not in scope)
        pool_data['liquidity'] = 'N/A'
        pool_data['volume_24h'] = 'N/A'
        
        # Try to fetch live pool data from blockchain if needed in the future
        try:
            # Placeholder for future pool contract integration
            # pool_contract = web3_service.get_contract(token.liquidity_pool_address, POOL_ABI)
            # reserves = pool_contract.functions.getReserves().call()
            # pool_data['liquidity'] = calculate_liquidity(reserves)
            pass
        except Exception as e:
            logging.debug(f"Could not fetch live pool data: {str(e)}")
        
        return jsonify({
            'success': True,
            'is_graduated': True,
            'dex_pool': pool_data
        })
        
    except ValueError as e:
        logging.error(f"Invalid address format: {address}, error: {str(e)}")
        return jsonify({'success': False, 'error': 'Invalid address format'}), 400
    except Exception as e:
        logging.error(f"Error fetching DEX pool data for {address}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch DEX pool data'}), 500

@app.route('/app/token/<address>/trade')
def redirect_to_dex(address):
    """Redirect to Kaspa Finance DEX for graduated tokens"""
    try:
        # Normalize address (lowercase, strip whitespace)
        address_normalized = address.strip().lower()
        
        # Flexible validation: Accept various formats
        # - EVM format: 0x... (42 chars)
        # - Kaspa native format: kas:... or other prefixes
        # - Just check it's not empty and reasonable length
        if not address_normalized or len(address_normalized) < 10:
            flash('Invalid token address', 'error')
            return redirect(url_for('index'))
        
        # Case-insensitive lookup - let DB determine if valid
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == address_normalized
        ).first()
        
        if not token:
            flash('Token not found', 'error')
            return redirect(url_for('index'))
        
        # Check if token has graduated and has pool address
        if not token.is_graduated or not token.liquidity_pool_address:
            flash('Token has not graduated yet', 'info')
            return redirect(url_for('token_detail', contract_address=address))
        
        # Redirect to Kaspa Finance DEX
        dex_url = f'https://kaspa.finance/pool/{token.liquidity_pool_address}'
        logging.info(f"Redirecting to Kaspa Finance DEX: {dex_url}")
        return redirect(dex_url)
        
    except ValueError as e:
        logging.error(f"Invalid address format for trade redirect: {address}, error: {str(e)}")
        flash('Invalid token address', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error redirecting to DEX for {address}: {str(e)}")
        flash('Failed to redirect to DEX', 'error')
        return redirect(url_for('index'))

# Leaderboard routes
@app.route('/app/leaderboard')
@wallet_optional
def leaderboard():
    """Main leaderboard page with rankings and points - accessible without wallet"""
    user = get_current_user()  # Will be None if not connected
    
    # Get top users by GEM points with eager loading of related data
    top_users = User.query.options(
        selectinload(User.earned_achievements).joinedload(UserAchievement.achievement),
        joinedload(User.profile)
    ).order_by(User.gem_points.desc()).limit(50).all()
    
    # Get user's rank (only if user is connected)
    user_rank = None
    if user:
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

@app.route('/api/user/<int:user_id>/profile')
def get_user_profile(user_id):
    """API endpoint to get user profile data for modal display"""
    try:
        # Get user with profile and achievements
        user = User.query.options(
            joinedload(User.profile),
            selectinload(User.earned_achievements).joinedload(UserAchievement.achievement)
        ).get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get profile data
        profile = user.profile
        
        # Get achievements
        achievements = []
        for ua in user.earned_achievements:
            achievements.append({
                'name': ua.achievement.name,
                'description': ua.achievement.description,
                'icon': ua.achievement.icon,
                'category': ua.achievement.category,
                'earned_at': ua.earned_at.strftime('%Y-%m-%d') if ua.earned_at else None
            })
        
        # Calculate user's rank
        users_above = User.query.filter(User.gem_points > user.gem_points).count()
        rank = users_above + 1
        
        # Build avatar URL
        avatar_url = None
        if profile:
            if profile.avatar_path:
                # Use new compressed avatar path
                from flask import url_for
                avatar_url = url_for('static', filename=profile.avatar_path, _external=True)
                if profile.avatar_updated_at:
                    avatar_url += f"?v={int(profile.avatar_updated_at.timestamp())}"
        
        # Build response
        profile_data = {
            'user_id': user.id,
            'display_name': user.display_name or 'Anonymous Trader',
            'wallet_address': user.wallet_address,
            'created_at': user.created_at.strftime('%B %Y') if user.created_at else None,
            'rank': rank,
            'gem_points': user.gem_points or 0,
            'total_tokens_created': user.total_tokens_created or 0,
            'total_trading_volume': float(user.total_trading_volume or 0),
            'total_trades_count': user.total_trades_count or 0,
            'total_messages_sent': user.total_messages_sent or 0,
            'is_twitter_verified': user.is_twitter_verified,
            'achievements': achievements,
            'profile': {
                'bio': profile.bio if profile else None,
                'username': profile.username if profile else None,
                'avatar_url': avatar_url,
                'twitter_handle': profile.twitter_handle if profile and profile.is_twitter_verified else None,
                'telegram_handle': profile.telegram_handle if profile and profile.is_telegram_verified else None,
                'discord_handle': profile.discord_handle if profile else None,
                'account_type': profile.account_type if profile else 'Standard',
                'member_since': profile.member_since.strftime('%B %Y') if profile and profile.member_since else user.created_at.strftime('%B %Y') if user.created_at else None
            }
        }
        
        return jsonify({'success': True, 'profile': profile_data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/app/profile', methods=['GET', 'POST'])
def profile():
    """User profile page with wallet connections and stats"""
    user = get_current_user()
    if not user:
        return redirect(url_for('token_marketplace'))
    
    # Get or create user profile
    user_profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not user_profile:
        user_profile = UserProfile()
        user_profile.user_id = user.id
        db.session.add(user_profile)
        db.session.commit()
    
    # Get connected wallets
    connected_wallets = ConnectedWallet.query.filter_by(user_id=user.id).all()
    
    # Get linked wallets (verified secondary wallets)
    linked_wallets = LinkedWallet.query.filter_by(user_id=user.id, status='verified').all()
    
    # Get user's achievements with eager loading
    user_achievements = UserAchievement.query.options(
        joinedload(UserAchievement.achievement)
    ).filter_by(user_id=user.id).all()
    
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
    
    # Get referred users for referrals tab with eager loading
    referred_users = User.query.options(
        joinedload(User.profile)
    ).join(Referral, Referral.referee_id == User.id).filter(
        Referral.referrer_id == user.id
    ).all()
    
    # Get pending transfer requests (where current user is the owner)
    pending_requests_query = TransferRequest.query.options(
        joinedload(TransferRequest.requester).joinedload(User.profile)
    ).filter_by(
        owner_id=user.id,
        status='pending'
    ).filter(
        TransferRequest.expires_at > datetime.now(timezone.utc)
    ).order_by(
        TransferRequest.created_at.desc()
    ).all()
    
    # Convert to JSON-serializable dictionaries
    pending_requests = []
    for req in pending_requests_query:
        # Generate canonical message (must match accept_transfer format exactly)
        canonical_message = f"Accept transfer request for wallet {req.wallet_address} and merge accounts.\n\nNonce: {req.nonce}\nTimestamp: {int(req.created_at.timestamp())}\n\nWarning: This will merge all data from your account into the requester's account."
        
        pending_requests.append({
            'id': req.id,
            'requester_wallet': req.requester.wallet_address,
            'requester_display': req.requester.display_name,
            'wallet_address': req.wallet_address,
            'created_at': req.created_at.isoformat(),
            'expires_at': req.expires_at.isoformat(),
            'nonce': req.nonce,
            'message': canonical_message
        })
    
    return render_template('app/profile.html', 
                         user=user, 
                         user_profile=user_profile,
                         connected_wallets=connected_wallets,
                         linked_wallets=linked_wallets,
                         user_achievements=user_achievements,
                         referral=referral,
                         referred_users=referred_users,
                         pending_requests=pending_requests)

@app.route('/app/referrals')
def referrals():
    """Redirect to profile page - referrals are now part of profile"""
    return redirect(url_for('profile'))

@app.route('/app/activities')
def activities():
    """User activities and achievement progress page"""
    user = get_current_user()
    if not user:
        return redirect(url_for('app_marketplace'))
    
    # Get user's recent activities with eager loading
    user_activities = Activity.query.options(
        joinedload(Activity.token),
        joinedload(Activity.achievement),
        joinedload(Activity.trade)
    ).filter_by(user_id=user.id).order_by(
        Activity.created_at.desc()
    ).limit(50).all()
    
    # Get available achievements and user's progress with eager loading
    all_achievements = Achievement.query.filter_by(is_active=True).all()
    user_achievements = {ua.achievement_id: ua for ua in UserAchievement.query.options(
        joinedload(UserAchievement.achievement)
    ).filter_by(user_id=user.id).all()}
    
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
                
                # Chat Champion - Active community member
                achievement10 = Achievement()
                achievement10.name = "Chat Champion"
                achievement10.description = "Send 50+ messages in token chats"
                achievement10.icon = "💬"
                achievement10.category = "social"
                achievement10.requirement_type = "chat_messages_sent"
                achievement10.requirement_value = 50
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
                
                # Create the specific user (you) as creator for LASER and MOON
                user_creator = User.query.filter_by(wallet_address='0xa51d8f597570353ae50a25df90ade162d2305ffa').first()
                if not user_creator:
                    user_creator = User()
                    user_creator.wallet_address = '0xa51d8f597570353ae50a25df90ade162d2305ffa'
                    user_creator.display_name = 'Degen'
                    user_creator.wallet_type = 'kastle'
                    db.session.add(user_creator)
                
                # Create different sample users for other tokens
                doge_creator = User.query.filter_by(wallet_address='0x2a3b4c5d6e7f8901234567890abcdef123456789').first()
                if not doge_creator:
                    doge_creator = User()
                    doge_creator.wallet_address = '0x2a3b4c5d6e7f8901234567890abcdef123456789'
                    doge_creator.display_name = 'DogeLord'
                    doge_creator.wallet_type = 'kastle'
                    db.session.add(doge_creator)
                
                pepe_creator = User.query.filter_by(wallet_address='0x9f8e7d6c5b4a39281726354647382910abcdef12').first()
                if not pepe_creator:
                    pepe_creator = User()
                    pepe_creator.wallet_address = '0x9f8e7d6c5b4a39281726354647382910abcdef12'
                    pepe_creator.display_name = 'PepeKing'
                    pepe_creator.wallet_type = 'kastle'
                    db.session.add(pepe_creator)
                
                floki_creator = User.query.filter_by(wallet_address='0x5d4c3b2a1908765432101234567890abcdef1234').first()
                if not floki_creator:
                    floki_creator = User()
                    floki_creator.wallet_address = '0x5d4c3b2a1908765432101234567890abcdef1234'
                    floki_creator.display_name = 'VikingDev'
                    floki_creator.wallet_type = 'kastle'
                    db.session.add(floki_creator)
                
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
                        'creator': doge_creator,  # Different creator
                        'website': 'https://dogekaspa.io',
                        'twitter': 'https://x.com/dogekaspa',
                        'telegram': 'https://t.me/dogekaspa'
                    },
                    {
                        'name': 'Moon Rocket',
                        'symbol': 'MOON',
                        'description': 'To the moon and beyond! Basic token with solid community features.',
                        'contract_address': '0x91818fbe36d8827228e6cc7c5af1cd52e4315g74',
                        'market_cap': 28000,
                        'price': 0.000028,
                        'image_url': 'https://upload.wikimedia.org/wikipedia/commons/1/1c/Rocket_icon.png',
                        'creator': user_creator,  # YOU own this token
                        'website': 'https://moonrocket.kas',
                        'twitter': 'https://x.com/moonrocketkaspa',
                        'telegram': 'https://t.me/moonrocketkaspa'
                    },
                    {
                        'name': 'Laser Eyes',
                        'symbol': 'LASER',
                        'description': 'Laser focus on gains. Pro token with cutting-edge features.',
                        'contract_address': '0xc3d4e5f6789012345678901234567890abcdef12',
                        'market_cap': 67000,
                        'price': 0.000067,
                        'image_url': 'https://i.imgur.com/laser-eyes.png',
                        'creator': user_creator,  # YOU own this token
                        'website': 'https://lasereyes.pro',
                        'twitter': 'https://x.com/lasereyeskaspa',
                        'trade_count': 400,  # Example: $200k volume
                        'volume': 200000  # $200k total volume
                    },
                    {
                        'name': 'PepeCoin',
                        'symbol': 'PEPE',
                        'description': 'The most memeable memecoin on Kaspa. For the culture!',
                        'contract_address': '0xa1b2c3d4e5f6789012345678901234567890abcd',
                        'market_cap': 15000,
                        'price': 0.000015,
                        'image_url': 'https://upload.wikimedia.org/wikipedia/en/thumb/6/63/Feelsbadman.jpg/256px-Feelsbadman.jpg',
                        'creator': pepe_creator,  # Different creator
                        'twitter': 'https://x.com/pepekaspa',
                        'telegram': 'https://t.me/pepekaspa_official'
                    },
                    {
                        'name': 'FlokiKas',
                        'symbol': 'FLOKI',
                        'description': 'Viking dog conquering the Kaspa ecosystem with lightning speed.',
                        'contract_address': '0xd4e5f6789012345678901234567890abcdef1234',
                        'market_cap': 32000,
                        'price': 0.000032,
                        'image_url': 'https://s2.coinmarketcap.com/static/img/coins/200x200/10804.png',
                        'creator': floki_creator,  # Different creator
                        'website': 'https://flokikas.org',
                        'telegram': 'https://t.me/flokikaspa'
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
                    token.trade_count = token_data.get('trade_count', 42)  # Use custom or default
                    token.holder_count = 156  # Mock holders
                    # Make some tokens pro (with reserved percentage)
                    if token_data['symbol'] in ['KAS', 'KDOG']:
                        token.reserved_percentage = 25.0  # Pro token with max treasury
                    else:
                        token.reserved_percentage = 0.0  # Basic token
                    # Add social links
                    token.website = token_data.get('website')
                    token.twitter = token_data.get('twitter')
                    token.telegram = token_data.get('telegram')
                    db.session.add(token)
                
                db.session.commit()
                print("✅ Sample tokens created with contract addresses")
            else:
                # Clean up old pending tokens (older than 24 hours)
                from datetime import datetime, timedelta, timezone
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                old_pending = Token.query.filter(
                    Token.deployment_status == 'pending',
                    Token.created_at < cutoff_time
                ).all()
                if old_pending:
                    for token in old_pending:
                        db.session.delete(token)
                    db.session.commit()
                    print(f"✅ Cleaned up {len(old_pending)} old pending tokens")
                
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
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Referral code updated successfully!',
            'new_link': referral.referral_link
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
    
    # Get KAS oracle status
    from services.kas_oracle import oracle
    oracle_status = oracle.get_oracle_status()
    
    # Get recent activities
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(10).all()
    
    # Get top users
    top_users = User.query.order_by(User.gem_points.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_tokens=total_tokens,
                         total_volume=float(total_volume),
                         total_points=total_points,
                         oracle_status=oracle_status,
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

@app.route('/admin/settings')
def admin_settings():
    """Admin platform settings"""
    admin_key = request.args.get('key')
    if admin_key != 'gemlaunch-admin-2024':
        return "Access Denied", 403
    
    from models import PlatformSettings
    settings = PlatformSettings.get_settings()
    
    # Get KAS oracle status
    from services.kas_oracle import oracle
    oracle_status = oracle.get_oracle_status()
    
    return render_template('admin/settings.html', 
                         settings=settings, 
                         oracle_status=oracle_status)

@app.route('/admin/update-settings', methods=['POST'])
def admin_update_settings():
    """Update platform settings"""
    admin_key = request.form.get('admin_key')
    if admin_key != 'gemlaunch-admin-2024':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        from models import PlatformSettings
        settings = PlatformSettings.get_settings()
        
        # Update graduation threshold
        threshold = float(request.form.get('graduation_threshold_usd', 200))
        if threshold < 100:
            return jsonify({'error': 'Threshold must be at least $100'}), 400
        
        settings.graduation_threshold_usd = threshold
        settings.updated_at = datetime.now(timezone.utc)
        
        # Store admin wallet if available
        if 'wallet_address' in session:
            settings.updated_by = session['wallet_address']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Graduation threshold updated to ${threshold:,.2f}',
            'new_threshold': float(threshold)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/gemmy/suggest', methods=['POST'])
def gemmy_suggest():
    """Gemmy AI Assistant endpoint for token creation suggestions with Zeroday Memification"""
    import requests as req
    
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        context = data.get('context', {})
        mode = data.get('mode', 'creative')  # 'creative', 'trends', or 'kaspa_tech'
        history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        openrouter_key = os.environ.get("OPENROUTER")
        if not openrouter_key:
            return jsonify({'error': 'AI service not configured. Please contact support.'}), 503
        
        context_info = ""
        if context.get('tokenName'):
            context_info += f"\nCurrent token name: {context['tokenName']}"
        if context.get('symbol'):
            context_info += f"\nCurrent symbol: {context['symbol']}"
        
        conversation_context = ""
        if history and len(history) > 1:
            conversation_context = "\n\nPrevious conversation:\n"
            for msg in history[:-1]:
                role = "User" if msg.get('role') == 'user' else "Gemmy"
                conversation_context += f"{role}: {msg.get('content', '')}\n"
        
        system_prompt = "You are Gemmy, a friendly AI assistant that helps creators launch memecoins on Kaspa."
        
        if mode == 'trends':
            from services.trend_analyzer import get_trending_memes
            trending = get_trending_memes()
            if trending:
                system_prompt += "\n\n🔥 ZERODAY MEMIFICATION ENGINE - ACTIVE"
                system_prompt += "\n\nI've detected these emerging trends from 4chan /biz/ and Reddit:"
                for t in trending[:3]:
                    title = t['meme_data'].get('title', 'Unknown')
                    keywords = ', '.join(t['meme_data'].get('keywords', [])[:5])
                    system_prompt += f"\n- '{title}' (Keywords: {keywords})"
                
                system_prompt += "\n\nYour job: Transform these raw trends into MEMECOIN IDEAS."
                system_prompt += "\n\nFor EACH trend, create a token concept using the **Name:** **Symbol:** **Description:** format shown below."
                system_prompt += "\nDon't just list the trends - turn them into actionable, clickable token concepts!"
            else:
                system_prompt += "\n\n🔥 TRENDING MEMES: No trending data available right now. Suggest the user try Creative Mode or Kaspa Tech Mode instead."
        else:
            system_prompt += " You have access to:"
            system_prompt += "\n\n🔥 TRENDING MEMES (Zeroday Memification Engine):"
            system_prompt += "\n- Real-time data from 4chan /biz/ and Reddit CryptoMoonShots available in Trending Memes mode"
        
        system_prompt += "\n\n⚡ KASPA TECH MEMES:"
        if mode == 'kaspa_tech':
            from services.kaspa_knowledge import get_kaspa_meme_suggestions
            kaspa_memes = get_kaspa_meme_suggestions()[:3]
            system_prompt += "\n" + "\n".join([
                f"- {m['concept']}: {m['name']} (Ticker: ${m['ticker_suggestion']})"
                for m in kaspa_memes
            ])
            system_prompt += "\n\nYour job: Create memecoin ideas based on Kaspa's technical concepts."
            system_prompt += "\nUse the **Name:** **Symbol:** **Description:** format shown below for each suggestion."
        else:
            system_prompt += "\n- GHOSTDAG → SpookyCoin ($SPOOK)"
            system_prompt += "\n- DAGKnight → KnightRider ($KNIGHT)"
            system_prompt += "\n- 10 BPS → TenSpeed ($TENX)"
        
        system_prompt += "\n\nProvide creative, catchy suggestions for token names, symbols, and marketing copy."
        system_prompt += "\nFor Kaspa-native memes, only use K-prefix when it sounds natural (KDOGE works, KPEPE doesn't)."
        system_prompt += "\nKeep responses concise and fun. Use emojis sparingly to add personality."
        system_prompt += "\n\n📋 REQUIRED FORMAT for token suggestions:"
        system_prompt += "\nWhen providing token ideas, use this EXACT format for EACH suggestion:"
        system_prompt += "\n\n1. **Name:** [Token Name Here]"
        system_prompt += "\n**Symbol:** $[TICKER]"
        system_prompt += "\n**Description:** [One compelling sentence about the token]"
        system_prompt += "\n\n2. **Name:** [Next Token Name]"
        system_prompt += "\n**Symbol:** $[TICKER]"
        system_prompt += "\n**Description:** [One compelling sentence]"
        system_prompt += "\n\nAlways use **bold** for labels (Name:, Symbol:, Description:). Keep each field on its own line."
        system_prompt += "\nRemember previous suggestions from the conversation and build upon them when users ask follow-up questions."
        
        # Build messages array for OpenRouter (OpenAI-compatible format)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        if history and len(history) > 1:
            for msg in history[:-1]:
                messages.append({
                    "role": msg.get('role', 'user'),
                    "content": msg.get('content', '')
                })
        
        # Add current user message with context
        user_content = user_message
        if context_info:
            user_content += f"\n\nContext:{context_info}"
        messages.append({"role": "user", "content": user_content})
        
        logging.debug(f"Calling OpenRouter with mode: {mode}, messages count: {len(messages)}")
        
        # Call OpenRouter API
        response = req.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {openrouter_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': request.headers.get('Referer', 'https://gemlaunch.fun'),
                'X-Title': 'Gemlaunch.fun'
            },
            json={
                'model': 'meta-llama/llama-3.1-70b-instruct',
                'messages': messages,
                'temperature': 0.8,
                'max_tokens': 1000,
                'top_p': 0.9
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        response_text = result['choices'][0]['message']['content']
        
        return jsonify({
            'success': True,
            'response': response_text.strip()
        })
        
    except Exception as e:
        logging.error(f"Gemmy AI error: {str(e)}")
        return jsonify({
            'error': 'Sorry, I encountered an error. Please try again!',
            'details': str(e) if app.debug else None
        }), 500

@app.route('/api/kas-price', methods=['GET'])
def get_kas_price():
    """Get current KAS/USD price from oracle"""
    try:
        from services.kas_oracle import oracle
        status = oracle.get_oracle_status()
        return jsonify({
            'success': True,
            'kas_price': status['kas_price'],
            'graduation_threshold_kas': status['graduation_threshold_kas'],
            'api_source': status['api_source'],
            'last_update': status['last_update'].isoformat() if status['last_update'] else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def validate_chain_id():
    """Ensure we're connected to Kasplex Testnet (167012)"""
    web3_service = get_web3_service()
    current_chain_id = web3_service.w3.eth.chain_id
    
    if current_chain_id != 167012:
        raise ValueError(f"Wrong network! Expected 167012, got {current_chain_id}")

@app.route('/api/gas/estimate', methods=['POST'])
@csrf.exempt
def api_gas_estimate():
    """
    Estimate gas for a transaction with breakdown
    
    Request:
    {
        "to": "0x...",
        "from": "0x...",
        "data": "0x...",
        "value": "0x0"
    }
    
    Response:
    {
        "success": true,
        "gas_estimate": 123456,
        "gas_with_buffer": 148147,
        "gas_price_wei": "1000000000",
        "gas_price_gwei": "1.0",
        "estimated_cost_kas": "0.000148147",
        "estimated_cost_usd": null
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Request data required'}), 400
        
        # Build transaction for estimation
        tx = {
            'to': data.get('to'),
            'from': data.get('from'),
            'data': data.get('data', '0x'),
            'value': data.get('value', '0x0')
        }
        
        # Validate required fields
        if not tx['to'] or not tx['from']:
            return jsonify({'success': False, 'error': 'to and from addresses required'}), 400
        
        # Get Web3Service
        web3_service = get_web3_service()
        
        # Estimate gas
        gas_estimate = web3_service.w3.eth.estimate_gas(tx)
        gas_with_buffer = int(gas_estimate * 1.2)
        
        # Get current gas price
        gas_price = web3_service.w3.eth.gas_price
        gas_price_gwei = web3_service.w3.from_wei(gas_price, 'gwei')
        
        # Calculate cost
        cost_wei = gas_with_buffer * gas_price
        cost_kas = web3_service.w3.from_wei(cost_wei, 'ether')
        
        return jsonify({
            'success': True,
            'gas_estimate': gas_estimate,
            'gas_with_buffer': gas_with_buffer,
            'gas_price_wei': str(gas_price),
            'gas_price_gwei': str(gas_price_gwei),
            'estimated_cost_kas': str(cost_kas),
            'estimated_cost_usd': None
        })
    except Exception as e:
        logging.error(f"Gas estimation failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/status', methods=['GET'])
def api_network_status():
    """Get current network status and connection info"""
    try:
        web3_service = get_web3_service()
        
        return jsonify({
            'success': True,
            'connected': web3_service.w3.is_connected(),
            'chain_id': web3_service.w3.eth.chain_id,
            'block_number': web3_service.w3.eth.block_number,
            'gas_price_gwei': str(web3_service.w3.from_wei(web3_service.w3.eth.gas_price, 'gwei')),
            'network_name': 'Kasplex Testnet'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'connected': False,
            'error': str(e)
        }), 500

def calculate_anti_bot_fee(kas_amount_wei, token):
    """
    Calculate anti-bot fee for a token purchase
    
    Args:
        kas_amount_wei (int): KAS amount in wei
        token (Token): Token object from database
    
    Returns:
        dict: {
            'fee_wei': int,
            'fee_kas': float,
            'elapsed_seconds': int
        }
    """
    if not token.anti_bot_enabled:
        return {'fee_wei': 0, 'fee_kas': 0.0, 'elapsed_seconds': 0}
    
    created_at_utc = token.created_at.replace(tzinfo=timezone.utc) if token.created_at.tzinfo is None else token.created_at
    
    if not token.deployment_block_number:
        elapsed_seconds = int((datetime.now(timezone.utc) - created_at_utc).total_seconds())
    else:
        elapsed_seconds = int((datetime.now(timezone.utc) - created_at_utc).total_seconds())
    
    if elapsed_seconds >= 60:
        fee_percent = 100
    else:
        fee_percent = 9500 - (9400 * elapsed_seconds // 60)
    
    fee_wei = kas_amount_wei * fee_percent // 10000
    fee_kas = float(Web3.from_wei(fee_wei, 'ether'))
    
    return {
        'fee_wei': fee_wei,
        'fee_kas': fee_kas,
        'elapsed_seconds': elapsed_seconds
    }

@app.route('/api/trade/quote-buy', methods=['POST'])
@csrf.exempt
def api_quote_buy():
    """
    Get buy quote for a token (bidirectional: accepts kas_amount OR token_amount)
    
    Request JSON:
    {
        "token_address": "0x...",
        "kas_amount": 10.5,           // Option 1: provide KAS amount
        "token_amount": 1000000,      // Option 2: provide desired token amount
        "slippage_bps": 100           // Optional: custom slippage in basis points (0.5% = 50)
    }
    
    Response JSON:
    {
        "success": true,
        "kas_amount": 10.5,
        "token_amount": 1000000,
        "tokens_out": 1000000,        // Backward compatibility
        "min_tokens_out": 990000,
        "min_tokens_out_wei": "990000000000000000",
        "price_per_token": "0.0000105",
        "total_cost": 10.5,
        "fees": {
            "anti_bot": 0,
            "platform": 0.0945,
            "creator": 0.0105
        },
        "slippage_bps": 100,
        "price_impact_percent": 2.3
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        logging.info(f"📥 [QUOTE-BUY DEBUG] Received request: {data}")
        
        token_address = data.get('token_address', '').strip()
        kas_amount = data.get('kas_amount')
        token_amount = data.get('token_amount')
        custom_slippage_bps = data.get('slippage_bps')
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        
        # Validate exactly one of kas_amount or token_amount is provided
        if kas_amount is not None and token_amount is not None:
            return jsonify({'success': False, 'error': 'Provide either kas_amount OR token_amount, not both'}), 400
        
        if kas_amount is None and token_amount is None:
            return jsonify({'success': False, 'error': 'Either kas_amount or token_amount is required'}), 400
        
        # Convert string inputs to floats
        if kas_amount is not None:
            kas_amount = float(kas_amount)
        if token_amount is not None:
            token_amount = float(token_amount)
        
        # Validate amounts
        if kas_amount is not None and kas_amount <= 0:
            return jsonify({'success': False, 'error': 'kas_amount must be greater than 0'}), 400
        
        if token_amount is not None and token_amount <= 0:
            return jsonify({'success': False, 'error': 'token_amount must be greater than 0'}), 400
        
        try:
            token_address = Web3.to_checksum_address(token_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid token address format'}), 400
        
        # Case-insensitive query (database stores lowercase addresses)
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        if token.deployment_status != 'deployed':
            return jsonify({'success': False, 'error': 'Token not deployed yet'}), 400
        
        web3_service = get_web3_service()
        
        # Convert amounts to wei
        kas_amount_wei = Web3.to_wei(kas_amount, 'ether') if kas_amount is not None else None
        # Frontend sends token_amount in wei for consistency with sell endpoint
        token_amount_wei = int(token_amount) if token_amount is not None else None
        
        # Calculate anti-bot fees (applied to KAS amount)
        # Note: For inverse calculation (token_amount provided), we'll need to account for this after solving
        if kas_amount_wei is not None:
            anti_bot_result = calculate_anti_bot_fee(kas_amount_wei, token)
            anti_bot_fee_wei = anti_bot_result['fee_wei']
            anti_bot_fee_kas = anti_bot_result['fee_kas']
            
            remaining_kas_wei = kas_amount_wei - anti_bot_fee_wei
            platform_fee_wei = remaining_kas_wei * 90 // 10000
            creator_fee_wei = remaining_kas_wei * 10 // 10000
            trade_amount_wei = remaining_kas_wei - platform_fee_wei - creator_fee_wei
            
            # Forward calculation: kas_amount → token_amount
            quote_result = web3_service.get_bonding_curve_quote(
                pool_address=token.contract_address,
                direction='buy',
                kas_amount=trade_amount_wei
            )
            tokens_out_wei = quote_result['token_amount']
            final_kas_amount = kas_amount
        else:
            # Inverse calculation: token_amount → kas_amount
            # Call unified quote service to solve for kas_amount
            quote_result = web3_service.get_bonding_curve_quote(
                pool_address=token.contract_address,
                direction='buy',
                token_amount=token_amount_wei
            )
            trade_amount_wei = quote_result['kas_amount']
            tokens_out_wei = quote_result['token_amount']
            
            # Calculate fees from the solved trade amount
            platform_fee_wei = trade_amount_wei * 90 // 10000
            creator_fee_wei = trade_amount_wei * 10 // 10000
            remaining_kas_wei = trade_amount_wei + platform_fee_wei + creator_fee_wei
            
            # Calculate anti-bot fee from total KAS
            anti_bot_result = calculate_anti_bot_fee(remaining_kas_wei, token)
            anti_bot_fee_wei = anti_bot_result['fee_wei']
            anti_bot_fee_kas = anti_bot_result['fee_kas']
            
            # Total KAS amount user needs to provide
            total_kas_wei = remaining_kas_wei + anti_bot_fee_wei
            final_kas_amount = float(Web3.from_wei(total_kas_wei, 'ether'))
        
        # Use custom slippage or auto-calculated slippage
        if custom_slippage_bps is not None:
            if not isinstance(custom_slippage_bps, (int, float)) or custom_slippage_bps < 0 or custom_slippage_bps > 2000:
                return jsonify({'success': False, 'error': 'slippage_bps must be between 0 and 2000 (0-20%)'}), 400
            slippage_bps = int(custom_slippage_bps)
        else:
            slippage_bps = quote_result.get('auto_slippage_bps', 50)
        
        # Calculate minimum tokens out with slippage
        min_tokens_out_wei = tokens_out_wei * (10000 - slippage_bps) // 10000
        
        # Convert wei to ether for display
        tokens_out = float(Web3.from_wei(tokens_out_wei, 'ether'))
        min_tokens_out = float(Web3.from_wei(min_tokens_out_wei, 'ether'))
        price_per_token = final_kas_amount / tokens_out if tokens_out > 0 else 0
        price_impact = quote_result.get('price_impact_percent', 0.0)
        
        return jsonify({
            'success': True,
            'kas_amount': float(final_kas_amount),
            'token_amount': float(tokens_out),
            'tokens_out': float(tokens_out),  # Backward compatibility
            'min_tokens_out': float(min_tokens_out),
            'min_tokens_out_wei': str(min_tokens_out_wei),
            'price_per_token': float(price_per_token),
            'total_cost': float(final_kas_amount),
            'fees': {
                'anti_bot': float(anti_bot_fee_kas) if anti_bot_fee_kas > 0 else 0.0,
                'platform': float(Web3.from_wei(platform_fee_wei, 'ether')),
                'creator': float(Web3.from_wei(creator_fee_wei, 'ether'))
            },
            'slippage_bps': int(slippage_bps),
            'price_impact_percent': float(round(price_impact, 2))
        })
        
    except ValueError as e:
        logging.debug(f"Validation error in quote-buy: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in quote-buy: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get buy quote'}), 500

@app.route('/api/trade/quote-sell', methods=['POST'])
@csrf.exempt
def api_quote_sell():
    """
    Get sell quote for a token (bidirectional: accepts token_amount OR kas_amount)
    
    Request JSON:
    {
        "token_address": "0x...",
        "token_amount": "1000000000000000000",  // Option 1: provide token amount to sell
        "kas_amount": 10.5,                     // Option 2: provide desired KAS amount
        "slippage_bps": 100                     // Optional: custom slippage in basis points
    }
    
    Response JSON:
    {
        "success": true,
        "kas_amount": 9.45,
        "token_amount": 1000000,
        "kas_out": 9.45,            // Backward compatibility
        "min_kas_out": 9.35,
        "min_kas_out_wei": "9350000000000000000",
        "price_per_token": "0.00000945",
        "net_kas": 9.345,
        "fees": {
            "anti_bot": 0.0,
            "platform": 0.0945,
            "creator": 0.0105
        },
        "slippage_bps": 100,
        "price_impact_percent": 1.8
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        logging.info(f"📥 [QUOTE-SELL DEBUG] Received request: {data}")
        
        token_address = data.get('token_address', '').strip()
        token_amount = data.get('token_amount')
        kas_amount = data.get('kas_amount')
        custom_slippage_bps = data.get('slippage_bps')
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        
        # Validate exactly one of token_amount or kas_amount is provided
        if token_amount is not None and kas_amount is not None:
            return jsonify({'success': False, 'error': 'Provide either token_amount OR kas_amount, not both'}), 400
        
        if token_amount is None and kas_amount is None:
            return jsonify({'success': False, 'error': 'Either token_amount or kas_amount is required'}), 400
        
        # Convert string inputs to proper types
        if token_amount is not None:
            try:
                token_amount_wei = int(token_amount)
                if token_amount_wei <= 0:
                    return jsonify({'success': False, 'error': 'token_amount must be greater than 0'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Invalid token_amount format'}), 400
        
        if kas_amount is not None:
            kas_amount = float(kas_amount)
            if kas_amount <= 0:
                return jsonify({'success': False, 'error': 'kas_amount must be greater than 0'}), 400
        
        try:
            token_address = Web3.to_checksum_address(token_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid token address format'}), 400
        
        # Case-insensitive query (database stores lowercase addresses)
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        if token.deployment_status != 'deployed':
            return jsonify({'success': False, 'error': 'Token not deployed yet'}), 400
        
        web3_service = get_web3_service()
        
        # Convert amounts to wei
        token_amount_wei = int(token_amount) if token_amount is not None else None
        kas_amount_wei = Web3.to_wei(kas_amount, 'ether') if kas_amount is not None else None
        
        # Call unified quote service
        quote_result = web3_service.get_bonding_curve_quote(
            pool_address=token.contract_address,
            direction='sell',
            kas_amount=kas_amount_wei,
            token_amount=token_amount_wei
        )
        
        kas_net_wei = quote_result['kas_amount']  # NET amount user receives
        final_token_amount_wei = quote_result['token_amount']
        platform_fee_wei = quote_result['fees']['platform']
        creator_fee_wei = quote_result['fees']['creator']
        
        # Calculate gross for display
        kas_gross_wei = kas_net_wei + platform_fee_wei + creator_fee_wei
        
        # Use custom slippage or auto-calculated slippage
        if custom_slippage_bps is not None:
            if not isinstance(custom_slippage_bps, (int, float)) or custom_slippage_bps < 0 or custom_slippage_bps > 2000:
                return jsonify({'success': False, 'error': 'slippage_bps must be between 0 and 2000 (0-20%)'}), 400
            slippage_bps = int(custom_slippage_bps)
        else:
            slippage_bps = quote_result.get('auto_slippage_bps', 50)
        
        # Calculate minimum KAS out with slippage
        min_kas_out_wei = kas_net_wei * (10000 - slippage_bps) // 10000
        
        # Convert wei to ether for display
        kas_gross = float(Web3.from_wei(kas_gross_wei, 'ether'))
        kas_net = float(Web3.from_wei(kas_net_wei, 'ether'))
        min_kas_out = float(Web3.from_wei(min_kas_out_wei, 'ether'))
        final_token_amount = float(final_token_amount_wei / 1e18)
        
        price_per_token = kas_gross / final_token_amount if final_token_amount > 0 else 0
        price_impact = quote_result.get('price_impact_percent', 0.0)
        
        return jsonify({
            'success': True,
            'kas_amount': float(kas_gross),
            'token_amount': float(final_token_amount),
            'kas_out': float(kas_gross),  # Backward compatibility
            'min_kas_out': float(min_kas_out),
            'min_kas_out_wei': str(min_kas_out_wei),
            'net_kas': float(kas_net),
            'price_per_token': float(price_per_token),
            'fees': {
                'anti_bot': 0.0,
                'platform': float(Web3.from_wei(platform_fee_wei, 'ether')),
                'creator': float(Web3.from_wei(creator_fee_wei, 'ether'))
            },
            'slippage_bps': int(slippage_bps),
            'price_impact_percent': float(round(price_impact, 2))
        })
        
    except ValueError as e:
        logging.debug(f"Validation error in quote-sell: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in quote-sell: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get sell quote'}), 500

@app.route('/api/trade/buy', methods=['POST'])
@csrf.exempt
def api_trade_buy():
    """
    Build unsigned buy transaction
    
    Frontend sends:
    {
        "token_address": "0x...",
        "kas_amount": 10.5,
        "min_tokens_out": 950000,
        "deadline": 1728741234
    }
    
    Returns:
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "value": "0x...",
            "data": "0x...",
            "gas": "0x..."
        },
        "estimated_gas": 150000
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        # Validate chain ID
        validate_chain_id()
        
        # Get user_address from session or request
        user_address = session.get('wallet_address')
        if not user_address:
            user_address = data.get('user_address', '').strip()
        
        token_address = data.get('token_address', '').strip()
        kas_amount = data.get('kas_amount')
        min_tokens_out = data.get('min_tokens_out')
        deadline = data.get('deadline')
        
        if not user_address:
            return jsonify({'success': False, 'error': 'user_address is required (connect wallet)'}), 400
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        
        if kas_amount is None or kas_amount <= 0:
            return jsonify({'success': False, 'error': 'kas_amount must be greater than 0'}), 400
        
        try:
            user_address = Web3.to_checksum_address(user_address)
            token_address = Web3.to_checksum_address(token_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid address format'}), 400
        
        # Case-insensitive query (database stores lowercase addresses)
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        if token.deployment_status != 'deployed':
            return jsonify({'success': False, 'error': 'Token not deployed yet'}), 400
        
        # Block trading during graduation process
        if token.graduation_status in ['initiating', 'completing']:
            return jsonify({
                'success': False, 
                'error': 'Trading temporarily paused during graduation to DEX',
                'graduation_status': token.graduation_status
            }), 400
        
        web3_service = get_web3_service()
        kas_amount_wei = Web3.to_wei(kas_amount, 'ether')
        
        # Use provided min_tokens_out or calculate with slippage
        if min_tokens_out is None:
            anti_bot_result = calculate_anti_bot_fee(kas_amount_wei, token)
            remaining_kas_wei = kas_amount_wei - anti_bot_result['fee_wei']
            platform_fee_wei = remaining_kas_wei * 90 // 10000
            creator_fee_wei = remaining_kas_wei * 10 // 10000
            trade_amount_wei = remaining_kas_wei - platform_fee_wei - creator_fee_wei
            tokens_out_wei = web3_service.get_buy_quote(token.contract_address, trade_amount_wei)
            min_tokens_out = tokens_out_wei * 9950 // 10000  # 0.5% default slippage
        
        # Use provided deadline or default to 5 minutes from now
        if deadline is None:
            deadline = int(datetime.now(timezone.utc).timestamp()) + 300
        
        # Build unsigned transaction
        unsigned_tx = web3_service.buy_tokens_tx_data(
            user_address,
            token.contract_address,
            kas_amount_wei,
            int(min_tokens_out),
            int(deadline)
        )
        
        # Format response for frontend
        tx_data = {
            'to': unsigned_tx['to'],
            'value': hex(unsigned_tx['value']),
            'data': unsigned_tx['data'],
            'gas': hex(unsigned_tx['gas'])
        }
        
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'estimated_gas': unsigned_tx['gas']
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in trade/buy: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in trade/buy: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to execute buy trade'}), 500

@app.route('/api/trade/sell', methods=['POST'])
@csrf.exempt
def api_trade_sell():
    """
    Build unsigned sell transaction
    
    Frontend sends:
    {
        "token_address": "0x...",
        "token_amount": "1000000",
        "min_kas_out": 9.2,
        "deadline": 1728741234
    }
    
    Returns:
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "value": "0x...",
            "data": "0x...",
            "gas": "0x..."
        },
        "estimated_gas": 150000
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        # Validate chain ID
        validate_chain_id()
        
        # Get user_address from session or request
        user_address = session.get('wallet_address')
        if not user_address:
            user_address = data.get('user_address', '').strip()
        
        token_address = data.get('token_address', '').strip()
        token_amount = data.get('token_amount')
        min_kas_out = data.get('min_kas_out')
        deadline = data.get('deadline')
        
        if not user_address:
            return jsonify({'success': False, 'error': 'user_address is required (connect wallet)'}), 400
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        
        if token_amount is None:
            return jsonify({'success': False, 'error': 'token_amount is required'}), 400
        
        try:
            token_amount_wei = int(token_amount)
            if token_amount_wei <= 0:
                return jsonify({'success': False, 'error': 'token_amount must be greater than 0'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid token_amount format'}), 400
        
        try:
            user_address = Web3.to_checksum_address(user_address)
            token_address = Web3.to_checksum_address(token_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid address format'}), 400
        
        # Case-insensitive query (database stores lowercase addresses)
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        if token.deployment_status != 'deployed':
            return jsonify({'success': False, 'error': 'Token not deployed yet'}), 400
        
        # Block trading during graduation process
        if token.graduation_status in ['initiating', 'completing']:
            return jsonify({
                'success': False, 
                'error': 'Trading temporarily paused during graduation to DEX',
                'graduation_status': token.graduation_status
            }), 400
        
        web3_service = get_web3_service()
        
        # Use provided min_kas_out or calculate with slippage
        if min_kas_out is None:
            quote_result = web3_service.get_sell_quote(token.contract_address, token_amount_wei)
            kas_net_wei = quote_result['kas_out']  # NET amount user receives
            min_kas_out_wei = kas_net_wei * 9950 // 10000  # 0.5% default slippage on net amount
            logging.info(f"Sell tx - No min_kas_out provided, calculated from quote: kas_net={kas_net_wei} wei, min_kas_out={min_kas_out_wei} wei")
        else:
            # Accept either wei (int/string) or KAS (float) for backwards compatibility
            try:
                # Try parsing as wei first (if it's a large integer or string of digits)
                min_kas_out_wei = int(min_kas_out)
                logging.info(f"Sell tx - Using provided min_kas_out (wei): {min_kas_out_wei} wei")
            except (ValueError, TypeError):
                # Fall back to KAS (float) conversion
                min_kas_out_wei = Web3.to_wei(min_kas_out, 'ether')
                logging.info(f"Sell tx - Using provided min_kas_out (KAS): {min_kas_out} KAS = {min_kas_out_wei} wei")
        
        # Use provided deadline or default to 5 minutes from now
        if deadline is None:
            deadline = int(datetime.now(timezone.utc).timestamp()) + 300
        
        # Build unsigned transaction
        unsigned_tx = web3_service.sell_tokens_tx_data(
            user_address,
            token.contract_address,
            token_amount_wei,
            int(min_kas_out_wei),
            int(deadline)
        )
        
        # Format response for frontend
        tx_data = {
            'to': unsigned_tx['to'],
            'value': hex(unsigned_tx['value']),
            'data': unsigned_tx['data'],
            'gas': hex(unsigned_tx['gas'])
        }
        
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'estimated_gas': unsigned_tx['gas']
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in trade/sell: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error in trade/sell: {error_msg}")
        
        # Extract revert reason from web3 errors
        if 'execution reverted' in error_msg.lower():
            # Extract the actual revert message
            if 'Slippage too high' in error_msg:
                error_msg = 'Slippage too high - price moved too much. Try increasing slippage tolerance or using a smaller amount.'
            elif ':' in error_msg:
                # Try to extract message after colon
                parts = error_msg.split(':')
                if len(parts) > 1:
                    error_msg = parts[-1].strip()
        
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/trade/<action>/estimate-gas', methods=['POST'])
@csrf.exempt
def api_estimate_gas(action):
    """
    Estimate gas for buy/sell transaction
    
    Frontend sends:
    {
        "token_address": "0x...",
        "kas_amount": 10.5 (for buy) or "token_amount": "1000000" (for sell),
        "from_address": "0x..." (optional)
    }
    
    Returns:
    {
        "success": true,
        "gas_estimate": 150000,
        "gas_with_buffer": 180000,
        "gas_price": "0x...",
        "estimated_cost_kas": 0.0015
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        if action not in ['buy', 'sell']:
            return jsonify({'success': False, 'error': 'Invalid action. Must be "buy" or "sell"'}), 400
        
        token_address = data.get('token_address', '').strip()
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        
        try:
            token_address = Web3.to_checksum_address(token_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid token address format'}), 400
        
        # Case-insensitive query (database stores lowercase addresses)
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        web3_service = get_web3_service()
        
        # Build params for estimate_trade_gas
        params = {
            'pool_address': token.contract_address
        }
        
        # Only add from_address if provided (web3_service will default to oracle)
        from_address = data.get('from_address') or session.get('wallet_address')
        if from_address:
            params['from_address'] = from_address
        
        if action == 'buy':
            kas_amount = data.get('kas_amount', 1.0)  # Default 1 KAS for estimation
            params['kas_amount'] = Web3.to_wei(kas_amount, 'ether')
        else:
            token_amount = data.get('token_amount', 1000000)  # Default 1M tokens for estimation
            params['token_amount'] = int(token_amount)
        
        # Call web3_service.estimate_trade_gas()
        gas_result = web3_service.estimate_trade_gas(action, params)
        
        return jsonify({
            'success': True,
            'gas_estimate': gas_result['gas'],
            'gas_with_buffer': gas_result['gas'],  # Already includes 20% buffer
            'gas_price': hex(gas_result['gas_price']),
            'estimated_cost_kas': gas_result['cost_kas']
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in estimate-gas: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in estimate-gas: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to estimate gas'}), 500

@app.route('/api/dex/quote', methods=['POST'])
@csrf.exempt
def api_dex_quote():
    """
    Get DEX quote for graduated tokens
    
    Request:
    {
        "token_address": "0x...",
        "side": "buy" | "sell",
        "amount_in": "10.5" (KAS for buy, token amount for sell),
        "slippage_bps": 50 (optional, default 50 = 0.5%),
        "fee_tier": 3000 (optional, default 0.3%)
    }
    
    Response:
    {
        "success": true,
        "amount_out": "1234.56",
        "execution_price": "0.045",
        "price_impact_pct": 0.5,
        "gas_estimate": "150000",
        "fee_tier": 3000
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        # Validate required fields
        token_address = data.get('token_address', '').strip()
        side = data.get('side', '').strip().lower()
        amount_in = data.get('amount_in')
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        if side not in ['buy', 'sell']:
            return jsonify({'success': False, 'error': 'side must be "buy" or "sell"'}), 400
        if amount_in is None:
            return jsonify({'success': False, 'error': 'amount_in is required'}), 400
        
        # Normalize address
        try:
            token_address = Web3.to_checksum_address(token_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid token address format'}), 400
        
        # Get token from database
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Validate token is graduated
        if not token.is_graduated:
            return jsonify({'success': False, 'error': 'Token has not graduated yet. Use /api/trade/quote-buy or /api/trade/quote-sell for bonding curve trading.'}), 400
        
        # Parse optional parameters
        slippage_bps = data.get('slippage_bps', 50)
        fee_tier = data.get('fee_tier', token.dex_pool_fee_tier or 3000)
        
        # Validate slippage
        if not isinstance(slippage_bps, (int, float)) or slippage_bps < 0 or slippage_bps > 10000:
            return jsonify({'success': False, 'error': 'slippage_bps must be between 0 and 10000 (0% to 100%)'}), 422
        
        # Convert amount_in to wei
        try:
            if side == 'buy':
                amount_in_wei = Web3.to_wei(float(amount_in), 'ether')
            else:
                amount_in_wei = int(float(amount_in))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid amount_in format'}), 400
        
        # Get quote from web3_service
        web3_service = get_web3_service()
        quote = web3_service.get_dex_quote(side, token_address, amount_in_wei, fee_tier)
        
        # Format response
        if side == 'buy':
            amount_out_formatted = str(Web3.from_wei(quote['amount_out'], 'ether'))
        else:
            amount_out_formatted = str(Web3.from_wei(quote['amount_out'], 'ether'))
        
        return jsonify({
            'success': True,
            'amount_out': amount_out_formatted,
            'execution_price': str(quote['execution_price']),
            'price_impact_pct': quote['price_impact_pct'],
            'gas_estimate': str(quote['gas_estimate']),
            'fee_tier': fee_tier
        })
        
    except ValueError as e:
        logging.error(f"Validation error in DEX quote: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error getting DEX quote: {error_msg}")
        
        # Map specific errors to user-friendly messages
        if 'pool does not exist' in error_msg.lower() or 'pool not found' in error_msg.lower():
            return jsonify({'success': False, 'error': 'DEX pool not found - graduation may have failed'}), 404
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return jsonify({'success': False, 'error': 'RPC timeout - please try again'}), 503
        
        return jsonify({'success': False, 'error': f'Failed to get DEX quote: {error_msg}'}), 500

@app.route('/api/dex/buy', methods=['POST'])
@csrf.exempt
def api_dex_buy():
    """
    Build DEX buy transaction for graduated tokens
    
    Request:
    {
        "token_address": "0x...",
        "kas_amount": "10.5",
        "min_tokens_out": "1000000",
        "deadline": 1234567890 (unix timestamp),
        "user_address": "0x..."
    }
    
    Response:
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "value": "0x...",
            "data": "0x...",
            "gas": "0x..."
        },
        "requires_approval": false
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        # Validate required fields
        token_address = data.get('token_address', '').strip()
        kas_amount = data.get('kas_amount')
        min_tokens_out = data.get('min_tokens_out')
        deadline = data.get('deadline')
        user_address = data.get('user_address', '').strip()
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        if kas_amount is None:
            return jsonify({'success': False, 'error': 'kas_amount is required'}), 400
        if min_tokens_out is None:
            return jsonify({'success': False, 'error': 'min_tokens_out is required'}), 400
        if deadline is None:
            return jsonify({'success': False, 'error': 'deadline is required'}), 400
        if not user_address:
            return jsonify({'success': False, 'error': 'user_address is required'}), 400
        
        # Normalize addresses
        try:
            token_address = Web3.to_checksum_address(token_address)
            user_address = Web3.to_checksum_address(user_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid address format'}), 400
        
        # Get token from database
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Validate token is graduated
        if not token.is_graduated:
            return jsonify({'success': False, 'error': 'Token has not graduated yet. Use /api/trade/buy for bonding curve trading.'}), 400
        
        # Convert amounts to wei
        try:
            kas_amount_wei = Web3.to_wei(float(kas_amount), 'ether')
            min_tokens_out_wei = int(float(min_tokens_out))
            deadline_int = int(deadline)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid amount or deadline format'}), 400
        
        # Get fee tier from token
        fee_tier = data.get('fee_tier', token.dex_pool_fee_tier or 3000)
        
        # Build transaction
        web3_service = get_web3_service()
        tx_data = web3_service.build_dex_buy_tx(
            token_address=token_address,
            kas_amount_wei=kas_amount_wei,
            min_tokens_out=min_tokens_out_wei,
            user_address=user_address,
            deadline=deadline_int,
            fee_tier=fee_tier
        )
        
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'requires_approval': False
        })
        
    except ValueError as e:
        logging.error(f"Validation error in DEX buy: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error building DEX buy tx: {error_msg}")
        
        # Map specific errors
        if 'pool does not exist' in error_msg.lower() or 'pool not found' in error_msg.lower():
            return jsonify({'success': False, 'error': 'DEX pool not found - graduation may have failed'}), 404
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return jsonify({'success': False, 'error': 'RPC timeout - please try again'}), 503
        
        return jsonify({'success': False, 'error': f'Failed to build DEX buy transaction: {error_msg}'}), 500

@app.route('/api/dex/sell', methods=['POST'])
@csrf.exempt
def api_dex_sell():
    """
    Build DEX sell transaction for graduated tokens
    
    Request:
    {
        "token_address": "0x...",
        "token_amount": "1000000",
        "min_kas_out": "10.5",
        "deadline": 1234567890 (unix timestamp),
        "user_address": "0x...",
        "unwrap_wkas": true (optional, default false)
    }
    
    Response:
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "value": "0x0",
            "data": "0x...",
            "gas": "0x..."
        },
        "requires_approval": true,
        "approval_address": "0x..." (SwapRouter address),
        "unwrap_tx": {...} (optional, if unwrap_wkas is true)
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        # Validate required fields
        token_address = data.get('token_address', '').strip()
        token_amount = data.get('token_amount')
        min_kas_out = data.get('min_kas_out')
        deadline = data.get('deadline')
        user_address = data.get('user_address', '').strip()
        unwrap_wkas = data.get('unwrap_wkas', False)
        
        if not token_address:
            return jsonify({'success': False, 'error': 'token_address is required'}), 400
        if token_amount is None:
            return jsonify({'success': False, 'error': 'token_amount is required'}), 400
        if min_kas_out is None:
            return jsonify({'success': False, 'error': 'min_kas_out is required'}), 400
        if deadline is None:
            return jsonify({'success': False, 'error': 'deadline is required'}), 400
        if not user_address:
            return jsonify({'success': False, 'error': 'user_address is required'}), 400
        
        # Normalize addresses
        try:
            token_address = Web3.to_checksum_address(token_address)
            user_address = Web3.to_checksum_address(user_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid address format'}), 400
        
        # Get token from database
        token = Token.query.filter(db.func.lower(Token.contract_address) == token_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Validate token is graduated
        if not token.is_graduated:
            return jsonify({'success': False, 'error': 'Token has not graduated yet. Use /api/trade/sell for bonding curve trading.'}), 400
        
        # Convert amounts to wei
        try:
            token_amount_wei = int(float(token_amount))
            min_kas_out_wei = Web3.to_wei(float(min_kas_out), 'ether')
            deadline_int = int(deadline)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid amount or deadline format'}), 400
        
        # Get fee tier from token
        fee_tier = data.get('fee_tier', token.dex_pool_fee_tier or 3000)
        
        # Build transaction
        web3_service = get_web3_service()
        tx_data = web3_service.build_dex_sell_tx(
            token_address=token_address,
            token_amount=token_amount_wei,
            min_kas_out_wei=min_kas_out_wei,
            user_address=user_address,
            deadline=deadline_int,
            fee_tier=fee_tier
        )
        
        response = {
            'success': True,
            'tx_data': tx_data,
            'requires_approval': True,
            'approval_address': web3_service.KASPA_FINANCE_SWAP_ROUTER
        }
        
        # Optionally build WKAS unwrap transaction
        if unwrap_wkas:
            try:
                # Get user's WKAS balance
                wkas_balance = web3_service.get_wkas_balance(user_address)
                if wkas_balance > 0:
                    unwrap_tx = web3_service.build_wkas_unwrap_tx(user_address, wkas_balance)
                    response['unwrap_tx'] = unwrap_tx
            except Exception as e:
                logging.warning(f"Failed to build WKAS unwrap tx: {str(e)}")
        
        return jsonify(response)
        
    except ValueError as e:
        logging.error(f"Validation error in DEX sell: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error building DEX sell tx: {error_msg}")
        
        # Map specific errors
        if 'pool does not exist' in error_msg.lower() or 'pool not found' in error_msg.lower():
            return jsonify({'success': False, 'error': 'DEX pool not found - graduation may have failed'}), 404
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return jsonify({'success': False, 'error': 'RPC timeout - please try again'}), 503
        
        return jsonify({'success': False, 'error': f'Failed to build DEX sell transaction: {error_msg}'}), 500

@app.route('/api/relay/transaction', methods=['POST'])
@csrf.exempt
def api_relay_transaction():
    """
    Relay a signed transaction to the blockchain
    
    Frontend sends:
    {
        "signed_tx": "0x...",
        "tx_type": "buy" | "sell" | "create_token" (optional),
        "user_address": "0x..." (optional)
    }
    
    Returns:
    {
        "success": true,
        "tx_hash": "0x..."
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        signed_tx = data.get('signed_tx', '').strip()
        
        if not signed_tx:
            return jsonify({'success': False, 'error': 'signed_tx is required'}), 400
        
        if not isinstance(signed_tx, str) or not signed_tx.startswith('0x'):
            return jsonify({'success': False, 'error': 'signed_tx must be a hex string starting with 0x'}), 400
        
        web3_service = get_web3_service()
        tx_hash = web3_service.relay_signed_transaction(signed_tx)
        
        # Add to monitoring queue
        tx_monitor = get_tx_monitor()
        tx_monitor.add_pending_transaction(
            tx_hash=tx_hash,
            tx_type=data.get('tx_type', 'unknown'),
            user_address=data.get('user_address')
        )
        
        return jsonify({
            'success': True,
            'tx_hash': tx_hash
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in relay-transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in relay-transaction: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to relay transaction'}), 500

@app.route('/api/token/<address>/claim-creator-fees', methods=['POST'])
@csrf.exempt
def api_claim_creator_fees(address):
    """
    Claim accumulated creator fees - builds unsigned tx or relays signed tx
    
    Request JSON (Step 1 - Get Unsigned TX):
    {
        "action": "build_tx",
        "creator_address": "0x..."
    }
    
    Response (Step 1):
    {
        "success": true,
        "unsigned_tx": {
            "from": "0x...",
            "to": "0x...",
            "data": "0x...",
            "value": "0x0",
            "gas": "0x...",
            "gasPrice": "0x...",
            "nonce": "0x...",
            "chainId": 167012
        },
        "claimable_amount": "1.234",
        "claimable_amount_wei": "1234000000000000000"
    }
    
    Request JSON (Step 2 - Relay Signed TX):
    {
        "action": "relay_tx",
        "signed_tx": "0x..."
    }
    
    Response (Step 2):
    {
        "success": true,
        "tx_hash": "0x...",
        "status": "pending"
    }
    
    Example curl (build_tx):
    curl -X POST http://localhost:5000/api/token/0x.../claim-creator-fees \
      -H "Content-Type: application/json" \
      -d '{"action": "build_tx", "creator_address": "0x..."}'
    
    Example curl (relay_tx):
    curl -X POST http://localhost:5000/api/token/0x.../claim-creator-fees \
      -H "Content-Type: application/json" \
      -d '{"action": "relay_tx", "signed_tx": "0x..."}'
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        action = data.get('action', '').strip()
        
        if action == 'build_tx':
            # Validate chain ID
            validate_chain_id()
            
            creator_address = data.get('creator_address', '').strip()
            
            if not creator_address:
                return jsonify({'success': False, 'error': 'creator_address is required'}), 400
            
            if not address:
                return jsonify({'success': False, 'error': 'Token address is required'}), 400
            
            try:
                creator_address = Web3.to_checksum_address(creator_address)
                pool_address = Web3.to_checksum_address(address)
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid address format'}), 400
            
            token = Token.query.filter_by(contract_address=pool_address).first()
            if not token:
                return jsonify({'success': False, 'error': 'Token not found'}), 404
            
            if token.deployment_status != 'deployed':
                return jsonify({'success': False, 'error': 'Token not deployed yet'}), 400
            
            if not token.creator:
                return jsonify({'success': False, 'error': 'Token creator not found'}), 404
            
            if creator_address.lower() != token.creator.wallet_address.lower():
                return jsonify({
                    'success': False,
                    'error': 'Only token creator can claim fees'
                }), 403
            
            web3_service = get_web3_service()
            
            claimable_wei = web3_service.get_creator_claimable(pool_address)
            
            if claimable_wei == 0:
                return jsonify({
                    'success': False,
                    'error': 'No fees available to claim'
                }), 400
            
            claimable_kas = float(Web3.from_wei(claimable_wei, 'ether'))
            
            unsigned_tx = web3_service.withdraw_creator_fees_tx_data(
                creator_address,
                pool_address
            )
            
            unsigned_tx_formatted = {
                'from': unsigned_tx['from'],
                'to': unsigned_tx['to'],
                'data': unsigned_tx['data'],
                'value': hex(unsigned_tx['value']),
                'gas': hex(unsigned_tx['gas']),
                'gasPrice': hex(unsigned_tx['gasPrice']),
                'nonce': hex(unsigned_tx['nonce']),
                'chainId': 167012
            }
            
            logging.info(f"Built claim fees tx for {creator_address} - Claimable: {claimable_kas} KAS")
            
            return jsonify({
                'success': True,
                'unsigned_tx': unsigned_tx_formatted,
                'claimable_amount': str(claimable_kas),
                'claimable_amount_wei': str(claimable_wei)
            })
        
        elif action == 'relay_tx':
            # Validate chain ID
            validate_chain_id()
            
            signed_tx = data.get('signed_tx', '').strip()
            
            if not signed_tx:
                return jsonify({'success': False, 'error': 'signed_tx is required'}), 400
            
            if not isinstance(signed_tx, str) or not signed_tx.startswith('0x'):
                return jsonify({'success': False, 'error': 'signed_tx must be a hex string starting with 0x'}), 400
            
            web3_service = get_web3_service()
            tx_hash = web3_service.relay_signed_transaction(signed_tx)
            
            # Add to monitoring queue
            tx_monitor = get_tx_monitor()
            tx_monitor.add_pending_transaction(
                tx_hash=tx_hash,
                tx_type='claim_fees',
                user_address=data.get('creator_address'),
                token_id=None  # Get from context if available
            )
            
            logging.info(f"Relayed claim fees tx: {tx_hash}")
            
            return jsonify({
                'success': True,
                'tx_hash': tx_hash,
                'status': 'pending'
            })
        
        else:
            return jsonify({'success': False, 'error': 'Invalid action. Must be "build_tx" or "relay_tx"'}), 400
    
    except ValueError as e:
        logging.debug(f"Validation error in claim-creator-fees: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in claim-creator-fees: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to claim creator fees'}), 500

@app.route('/api/token/<address>/fee-stats', methods=['GET'])
def api_token_fee_stats(address):
    """
    Get comprehensive fee statistics for a token
    
    Response:
    {
        "success": true,
        "token_address": "0x...",
        "token_name": "MyToken",
        "token_symbol": "MTK",
        "deployment_status": "deployed",
        "graduation_status": "bonding_curve",
        "creator_fees": {
            "total_accumulated": "10.0",
            "claimed": "3.0",
            "available": "7.0"
        },
        "platform_fees": {
            "total_accumulated": "9.0",
            "distributed": "2.0",
            "available": "7.0"
        },
        "total_fees_generated": "19.0"
    }
    
    Example curl:
    curl -X GET http://localhost:5000/api/token/0x.../fee-stats
    """
    try:
        pool_address = Web3.to_checksum_address(address)
        
        from sqlalchemy import func
        token = Token.query.filter(func.lower(Token.contract_address) == pool_address.lower()).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        creator_fees_db = token.creator_fees_accumulated or Decimal('0')
        
        graduation_status = "graduated" if token.is_graduated else "bonding_curve"
        
        stats = {
            'success': True,
            'token_address': pool_address,
            'token_name': token.name,
            'token_symbol': token.symbol,
            'deployment_status': token.deployment_status,
            'graduation_status': graduation_status
        }
        
        if token.deployment_status == 'deployed':
            web3_service = get_web3_service()
            
            try:
                from models import TradeEvent
                from sqlalchemy import func
                
                creator_available_wei = web3_service.get_creator_claimable(pool_address)
                platform_available_wei = web3_service.get_platform_claimable(pool_address)
                
                creator_total_db = token.creator_fees_accumulated or Decimal('0')
                creator_total_wei = Web3.to_wei(creator_total_db, 'ether')
                creator_claimed_wei = max(0, creator_total_wei - creator_available_wei)
                
                platform_total_result = db.session.query(
                    func.coalesce(func.sum(TradeEvent.platform_fee), 0)
                ).filter(TradeEvent.token_id == token.id).scalar()
                platform_total_db = Decimal(str(platform_total_result)) if platform_total_result else Decimal('0')
                platform_total_wei = Web3.to_wei(platform_total_db, 'ether')
                platform_distributed_wei = max(0, platform_total_wei - platform_available_wei)
                
                total_fees_wei = creator_total_wei + platform_total_wei
                
                stats['creator_fees'] = {
                    'total_accumulated': str(Web3.from_wei(creator_total_wei, 'ether')),
                    'claimed': str(Web3.from_wei(creator_claimed_wei, 'ether')),
                    'available': str(Web3.from_wei(creator_available_wei, 'ether'))
                }
                
                stats['platform_fees'] = {
                    'total_accumulated': str(Web3.from_wei(platform_total_wei, 'ether')),
                    'distributed': str(Web3.from_wei(platform_distributed_wei, 'ether')),
                    'available': str(Web3.from_wei(platform_available_wei, 'ether'))
                }
                
                stats['total_fees_generated'] = str(Web3.from_wei(total_fees_wei, 'ether'))
                
            except Exception as e:
                logging.error(f"Blockchain fee lookup failed: {str(e)}")
                stats['creator_fees'] = {
                    'total_accumulated': str(creator_fees_db),
                    'claimed': 'N/A',
                    'available': 'N/A'
                }
                stats['platform_fees'] = {
                    'total_accumulated': 'N/A',
                    'distributed': 'N/A',
                    'available': 'N/A'
                }
                stats['total_fees_generated'] = str(creator_fees_db)
        else:
            stats['creator_fees'] = {
                'total_accumulated': '0',
                'claimed': '0',
                'available': '0'
            }
            stats['platform_fees'] = {
                'total_accumulated': '0',
                'distributed': '0',
                'available': '0'
            }
            stats['total_fees_generated'] = '0'
        
        return jsonify(stats)
    
    except ValueError as e:
        logging.debug(f"Validation error in fee-stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in fee-stats: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get fee stats'}), 500

@app.route('/api/token/<address>/distribute-reserve', methods=['POST'])
def api_distribute_reserve(address):
    """
    POST /api/token/<address>/distribute-reserve
    
    Distribute reserve tokens to recipients (team, marketing, airdrops) - PRO tokens only
    Creator-only endpoint, one-time distribution enforced by smart contract
    
    Request body:
    {
        "recipients": ["0x...", "0x...", "0x..."],
        "amounts": ["1000000000", "500000000", "500000000"],
        "allocation_types": ["team", "marketing", "airdrop"]
    }
    
    Response:
    {
        "success": true,
        "tx_data": {...},
        "gas_estimate": {...}
    }
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        from sqlalchemy import func
        pool_address = Web3.to_checksum_address(address)
        token = Token.query.filter(func.lower(Token.contract_address) == pool_address.lower()).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        if token.creator.wallet_address.lower() != user.wallet_address.lower():
            return jsonify({'success': False, 'error': 'Only token creator can distribute reserve'}), 403
        
        data = request.get_json()
        recipients = data.get('recipients', [])
        amounts = data.get('amounts', [])
        allocation_types = data.get('allocation_types', [])
        
        if not recipients or not amounts or not allocation_types:
            return jsonify({'success': False, 'error': 'recipients, amounts, and allocation_types are required'}), 400
        
        if len(recipients) != len(amounts) or len(recipients) != len(allocation_types):
            return jsonify({'success': False, 'error': 'recipients, amounts, and allocation_types must have same length'}), 400
        
        amounts_int = [int(amt) for amt in amounts]
        
        web3_service = get_web3_service()
        tx_data = web3_service.distribute_reserve_tx_data(
            user_address=user.wallet_address,
            pool_address=pool_address,
            recipients=recipients,
            amounts=amounts_int
        )
        
        for i, recipient in enumerate(recipients):
            distribution = ReserveDistribution(
                token_id=token.id,
                recipient_wallet=recipient.lower(),
                allocation_type=allocation_types[i],
                amount=amounts_int[i],
                tx_hash=None,
                distributed_at=None
            )
            db.session.add(distribution)
        
        db.session.commit()
        
        logging.info(f"Reserve distribution prepared for token {token.symbol} by {user.wallet_address}")
        
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'gas_estimate': {
                'gas': tx_data['gas'],
                'gas_price': tx_data['gasPrice'],
                'cost_kas': Web3.from_wei(tx_data['gas'] * tx_data['gasPrice'], 'ether')
            }
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in distribute-reserve: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in distribute-reserve: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to prepare reserve distribution'}), 500

@app.route('/api/token/<address>/reserve-status', methods=['GET'])
def api_reserve_status(address):
    """
    GET /api/token/<address>/reserve-status
    
    Get reserve distribution status for a token
    
    Response:
    {
        "success": true,
        "distributed": false,
        "total_reserve": 250000000,
        "available_reserve": 250000000,
        "distribution_history": [],
        "can_distribute": true,
        "allocations": {
            "team": 34.0,
            "marketing": 33.0,
            "airdrops": 33.0
        }
    }
    """
    try:
        from sqlalchemy import func
        pool_address = Web3.to_checksum_address(address)
        token = Token.query.filter(func.lower(Token.contract_address) == pool_address.lower()).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        web3_service = get_web3_service()
        reserve_status = web3_service.get_reserve_status(pool_address)
        
        distribution_history = []
        distributions = ReserveDistribution.query.filter_by(token_id=token.id).all()
        
        for dist in distributions:
            distribution_history.append({
                'id': dist.id,
                'recipient_wallet': dist.recipient_wallet,
                'allocation_type': dist.allocation_type,
                'amount': str(dist.amount),
                'tx_hash': dist.tx_hash,
                'distributed_at': dist.distributed_at.isoformat() if dist.distributed_at else None,
                'created_at': dist.created_at.isoformat() if dist.created_at else None
            })
        
        user = get_current_user()
        can_distribute = (
            not reserve_status['distributed'] and 
            user and 
            token.creator and 
            user.wallet_address.lower() == token.creator.wallet_address.lower()
        )
        
        return jsonify({
            'success': True,
            'distributed': reserve_status['distributed'],
            'total_reserve': reserve_status['total_reserve'],
            'available_reserve': reserve_status['available_reserve'],
            'distribution_history': distribution_history,
            'can_distribute': can_distribute,
            'allocations': {
                'team': token.team_allocation,
                'marketing': token.marketing_allocation,
                'airdrops': token.airdrops_allocation
            }
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in reserve-status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in reserve-status: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get reserve status'}), 500

@app.route('/api/token/<address>/upload-image', methods=['POST'])
def api_token_upload_image(address):
    """Upload token image to IPFS via Pinata"""
    try:
        from services import PinataService
        
        # Get token
        token = Token.query.filter_by(contract_address=address).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Check if file provided
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file'}), 400
        
        file = request.files['image']
        if not file.filename:
            return jsonify({'success': False, 'error': 'Empty filename'}), 400
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'webp'}
        filename = secure_filename(file.filename.lower())
        if '.' not in filename or filename.rsplit('.', 1)[1] not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload PNG, JPG, JPEG, or WebP files.'}), 400
        
        # Save temp file
        temp_path = f'/tmp/{token.symbol}_image.webp'
        file.save(temp_path)
        
        # Upload to Pinata
        pinata = PinataService()
        ipfs_hash = pinata.upload_file(temp_path, f'{token.symbol}_image')
        
        if not ipfs_hash:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'success': False, 'error': 'IPFS upload failed'}), 500
        
        # Update token
        token.ipfs_image_hash = ipfs_hash
        token.ipfs_image_url = pinata.get_ipfs_url(ipfs_hash)
        db.session.commit()
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'ipfs_hash': ipfs_hash,
            'ipfs_url': token.ipfs_image_url
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error uploading image: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<address>/generate-metadata', methods=['POST'])
def api_token_generate_metadata(address):
    """Generate and upload token metadata to IPFS"""
    try:
        from services import PinataService
        
        # Get token
        token = Token.query.filter_by(contract_address=address).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Check if image is on IPFS
        if not token.ipfs_image_url:
            return jsonify({'success': False, 'error': 'Upload image first'}), 400
        
        # Generate metadata (ERC-721/ERC-1155 standard)
        metadata = {
            'name': token.name,
            'symbol': token.symbol,
            'description': token.description or f'{token.name} token on Gemlaunch.fun',
            'image': token.ipfs_image_url,
            'external_url': f'https://gemlaunch.fun/token/{token.contract_address}',
            'attributes': [
                {'trait_type': 'Creator', 'value': token.creator.wallet_address if token.creator else 'Unknown'},
                {'trait_type': 'Total Supply', 'value': str(token.total_supply)},
                {'trait_type': 'Is Graduated', 'value': 'Yes' if token.is_graduated else 'No'}
            ]
        }
        
        # Upload metadata to IPFS
        pinata = PinataService()
        ipfs_hash = pinata.upload_json(metadata, f'{token.symbol}_metadata')
        
        if not ipfs_hash:
            return jsonify({'success': False, 'error': 'Metadata upload failed'}), 500
        
        # Update token
        token.ipfs_metadata_hash = ipfs_hash
        token.ipfs_metadata_url = pinata.get_ipfs_url(ipfs_hash)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'ipfs_hash': ipfs_hash,
            'ipfs_url': token.ipfs_metadata_url,
            'metadata': metadata
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error generating metadata: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<address>/metadata', methods=['GET'])
def api_token_metadata(address):
    """Get token metadata from IPFS or generate on-the-fly"""
    try:
        token = Token.query.filter_by(contract_address=address).first()
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # If metadata exists on IPFS, return URL
        if token.ipfs_metadata_url:
            return jsonify({
                'success': True,
                'ipfs_url': token.ipfs_metadata_url,
                'ipfs_hash': token.ipfs_metadata_hash
            })
        
        # Otherwise, generate metadata on-the-fly (not on IPFS)
        metadata = {
            'name': token.name,
            'symbol': token.symbol,
            'description': token.description or f'{token.name} token',
            'image': token.image_url or token.ipfs_image_url,
            'attributes': [
                {'trait_type': 'Creator', 'value': token.creator.wallet_address if token.creator else 'Unknown'},
                {'trait_type': 'Total Supply', 'value': str(token.total_supply)}
            ]
        }
        
        return jsonify({
            'success': True,
            'metadata': metadata,
            'note': 'Metadata not on IPFS yet'
        })
        
    except Exception as e:
        logging.error(f"Error fetching metadata: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-token-image', methods=['POST'])
def generate_token_image_api():
    """Generate token image using AI (OpenRouter Llama + Replicate FLUX)"""
    try:
        from services.image_generator import generate_token_image
        
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid JSON payload. Expected JSON object with tokenName, symbol, and description fields.'}), 400
        
        token_name = data.get('tokenName', '').strip()
        symbol = data.get('symbol', '').strip()
        description = data.get('description', '').strip()
        
        if not token_name:
            return jsonify({'error': 'Token name is required'}), 400
        if not symbol:
            return jsonify({'error': 'Token symbol is required'}), 400
        if not description:
            return jsonify({'error': 'Token description is required'}), 400
        
        logging.info(f"Generating AI image for token: {token_name} ({symbol})")
        
        result = generate_token_image(token_name, symbol, description)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logging.error(f"Error in generate_token_image_api: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to generate image: {str(e)}'
        }), 500

@app.route('/api/token/create', methods=['POST'])
@csrf.exempt
def api_create_token():
    """
    Create token with wallet signing (decentralized approach)
    
    Request Format:
    {
        "name": "MyToken",
        "symbol": "MTK",
        "description": "My awesome token",
        "total_supply": "1000000000",
        "reserved_percentage": "10",
        "anti_bot_enabled": true,
        "image_file": "<base64>",  // OR
        "ipfs_hash": "Qm...",  // if already uploaded
        "website": "https://...",
        "twitter": "https://twitter.com/...",
        "telegram": "https://t.me/..."
    }
    
    Response Format (Success):
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "value": "0x0",
            "data": "0x...",
            "gas": "0x..."
        },
        "estimated_gas": 500000,
        "token_id": 123
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        # Validate chain ID
        validate_chain_id()
        
        # Get user_address from session or request
        user_address = session.get('wallet_address')
        if not user_address:
            user_address = (data.get('user_address') or '').strip()
        
        if not user_address:
            return jsonify({'success': False, 'error': 'Wallet connection required'}), 400
        
        # Validate required fields
        name = (data.get('name') or '').strip()
        symbol = (data.get('symbol') or '').strip().upper()
        description = (data.get('description') or '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'Token name is required'}), 400
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Token symbol is required'}), 400
        
        # Validate total_supply
        try:
            total_supply = int(data.get('total_supply', 1000000000))
            # Contract enforces: min 1M, max 1B tokens
            if total_supply < 1_000_000:
                return jsonify({'success': False, 'error': 'Total supply must be at least 1,000,000 (1M) tokens'}), 400
            if total_supply > 1_000_000_000:
                return jsonify({'success': False, 'error': 'Total supply cannot exceed 1,000,000,000 (1B) tokens'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid total_supply format'}), 400
        
        # Validate reserved_percentage
        try:
            reserved_percentage = float(data.get('reserved_percentage', 0))
            if reserved_percentage < 0 or reserved_percentage > 25:
                return jsonify({'success': False, 'error': 'Reserved percentage must be between 0 and 25'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid reserved_percentage format'}), 400
        
        # Check if we're resuming an existing pending token (crash recovery)
        resuming_token_id = data.get('resuming_token_id')
        existing_token = None
        
        if resuming_token_id:
            # Resuming: validate the token exists and is pending
            existing_token = Token.query.filter_by(id=resuming_token_id, deployment_status='pending').first()
            if not existing_token:
                return jsonify({'success': False, 'error': 'Cannot resume: token not found or already deployed'}), 400
        else:
            # New token: check name/symbol uniqueness
            existing_by_name = Token.query.filter(db.func.lower(Token.name) == name.lower()).first()
            if existing_by_name:
                return jsonify({'success': False, 'error': f'Token name "{name}" already exists'}), 400
            
            existing_by_symbol = Token.query.filter(db.func.lower(Token.symbol) == symbol.lower()).first()
            if existing_by_symbol:
                return jsonify({'success': False, 'error': f'Token symbol "{symbol}" already exists'}), 400
        
        # Handle IPFS image upload/hash
        ipfs_hash = (data.get('ipfs_hash') or '').strip()
        image_file_base64 = (data.get('image_file') or '').strip()
        existing_ipfs_url = (data.get('existing_ipfs_url') or '').strip()
        ipfs_image_url = None
        
        if not ipfs_hash and not image_file_base64 and not existing_ipfs_url:
            return jsonify({'success': False, 'error': 'Either ipfs_hash, image_file, or existing_ipfs_url is required'}), 400
        
        # If existing IPFS URL provided (crash recovery), use it directly
        if existing_ipfs_url:
            ipfs_image_url = existing_ipfs_url
            # Extract hash from URL if possible (format: https://gateway.pinata.cloud/ipfs/QmXXX...)
            if '/ipfs/' in existing_ipfs_url:
                ipfs_hash = existing_ipfs_url.split('/ipfs/')[1].split('?')[0]
        # If image_file provided, upload to IPFS
        elif image_file_base64 and not ipfs_hash:
            try:
                from services.pinata_service import PinataService
                import base64
                import tempfile
                
                pinata = PinataService()
                
                # Decode base64 image
                image_data = base64.b64decode(image_file_base64)
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                    tmp_file.write(image_data)
                    tmp_file_path = tmp_file.name
                
                # Upload to IPFS
                ipfs_hash = pinata.upload_file(tmp_file_path, f"{symbol}_image")
                
                # Clean up temp file
                os.remove(tmp_file_path)
                
                if not ipfs_hash:
                    return jsonify({'success': False, 'error': 'Failed to upload image to IPFS'}), 500
                
            except Exception as e:
                logging.error(f"Error uploading image to IPFS: {str(e)}")
                return jsonify({'success': False, 'error': f'IPFS upload failed: {str(e)}'}), 500
        
        # Generate IPFS URL (if not already set from existing_ipfs_url)
        if ipfs_hash and not ipfs_image_url:
            from services.pinata_service import PinataService
            pinata = PinataService()
            ipfs_image_url = pinata.get_ipfs_url(ipfs_hash)
        
        # Get or create user
        user = User.get_or_create_by_wallet(user_address)
        
        # Either update existing token (crash recovery) or create new one
        if existing_token:
            # Resume: update the existing pending token
            new_token = existing_token
            new_token.name = name
            new_token.symbol = symbol
            new_token.description = description
            new_token.total_supply = total_supply
            new_token.reserved_percentage = reserved_percentage
            new_token.anti_bot_enabled = bool(data.get('anti_bot_enabled', False))
            
            # Vesting allocation percentages (PRO tokens)
            new_token.airdrops_allocation = int(data.get('airdrops_allocation', 33))
            new_token.marketing_allocation = int(data.get('marketing_allocation', 33))
            new_token.team_allocation = int(data.get('team_allocation', 34))
            
            # Calculate reserved tokens
            if reserved_percentage > 0:
                new_token.reserved_tokens = int(total_supply * (reserved_percentage / 100))
            else:
                new_token.reserved_tokens = 0
            
            # Social links
            new_token.website = (data.get('website') or '').strip()
            new_token.twitter = (data.get('twitter') or '').strip()
            new_token.telegram = (data.get('telegram') or '').strip()
            
            # IPFS data (update if new image provided)
            if ipfs_hash:
                new_token.ipfs_image_hash = ipfs_hash
            if ipfs_image_url:
                new_token.ipfs_image_url = ipfs_image_url
                new_token.image_url = ipfs_image_url
            
            token_id = new_token.id
            logging.info(f"Resuming token deployment - ID: {token_id}, Name: {name}, Symbol: {symbol}")
        else:
            # New token: create database record with status='pending'
            new_token = Token()
            new_token.name = name
            new_token.symbol = symbol
            new_token.description = description
            new_token.total_supply = total_supply
            new_token.reserved_percentage = reserved_percentage
            new_token.anti_bot_enabled = bool(data.get('anti_bot_enabled', False))
            
            # Vesting allocation percentages (PRO tokens)
            new_token.airdrops_allocation = int(data.get('airdrops_allocation', 33))
            new_token.marketing_allocation = int(data.get('marketing_allocation', 33))
            new_token.team_allocation = int(data.get('team_allocation', 34))
            
            # Calculate reserved tokens
            if reserved_percentage > 0:
                new_token.reserved_tokens = int(total_supply * (reserved_percentage / 100))
            else:
                new_token.reserved_tokens = 0
            
            # Social links
            new_token.website = (data.get('website') or '').strip()
            new_token.twitter = (data.get('twitter') or '').strip()
            new_token.telegram = (data.get('telegram') or '').strip()
            
            # IPFS data
            new_token.ipfs_image_hash = ipfs_hash
            new_token.ipfs_image_url = ipfs_image_url
            new_token.image_url = ipfs_image_url
            
            # Set creator and status
            new_token.creator_id = user.id
            new_token.deployment_status = 'pending'
            new_token.circulating_supply = 0
            new_token.current_price = 0.001
            new_token.current_market_cap = 1000
            
            # Add to database and flush to get ID
            db.session.add(new_token)
            db.session.flush()
            
            token_id = new_token.id
            
            # Create default token settings
            from models_extended import TokenSettings
            token_settings = TokenSettings(token_id=token_id)
            db.session.add(token_settings)
            
            logging.info(f"Token database record created - ID: {token_id}, Name: {name}, Symbol: {symbol}")
        
        # Commit to database
        db.session.commit()
        
        # Build unsigned transaction
        try:
            user_address_checksum = Web3.to_checksum_address(user_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid wallet address format'}), 400
        
        web3_service = get_web3_service()
        
        # Convert total_supply to wei (assuming 18 decimals)
        total_supply_wei = total_supply * (10 ** 18)
        
        unsigned_tx = web3_service.create_token_tx_data(
            user_address_checksum,
            name,
            symbol,
            total_supply_wei,
            description or f"{name} token",
            ipfs_image_url or "",
            new_token.twitter or "",
            new_token.telegram or "",
            new_token.website or "",
            new_token.anti_bot_enabled,
            int(new_token.reserved_percentage),
            int(new_token.airdrops_allocation),
            int(new_token.marketing_allocation),
            int(new_token.team_allocation)
        )
        
        # Format response for frontend
        tx_data = {
            'to': unsigned_tx['to'],
            'value': hex(unsigned_tx['value']),
            'data': unsigned_tx['data'],
            'gas': hex(unsigned_tx['gas'])
        }
        
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'estimated_gas': unsigned_tx['gas'],
            'token_id': token_id
        })
    
    except ValueError as e:
        logging.debug(f"Validation error in token/create: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in token/create: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Failed to create token: {str(e)}'}), 500

@app.route('/api/token/<int:token_id>/confirm-deployment', methods=['POST'])
@csrf.exempt
def confirm_token_deployment(token_id):
    """
    Confirm token deployment after blockchain transaction succeeds.
    
    SECURITY: 
    - Verifies tx_hash on blockchain (prevents fake contract addresses)
    - Checks caller is token creator (prevents unauthorized confirmation)
    - Extracts real contract address from blockchain receipt
    
    Request JSON:
    {
        "tx_hash": "0x...",
        "block_number": 1234567
    }
    
    Response:
    {
        "success": true,
        "contract_address": "0x...",
        "token": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        token = Token.query.get_or_404(token_id)
        
        # SECURITY: Only accept wallet from authenticated and verified session
        caller_address = session.get('wallet_address')
        wallet_verified = session.get('wallet_verified', False)
        
        if not caller_address or not wallet_verified:
            return jsonify({
                'success': False, 
                'error': 'Wallet not connected or not verified. Please connect your wallet first.'
            }), 401
        
        # Get token creator
        creator = User.query.get(token.creator_id)
        if not creator:
            return jsonify({'success': False, 'error': 'Token creator not found'}), 500
        
        # SECURITY: Verify caller is the creator (case-insensitive comparison)
        if caller_address.lower() != creator.wallet_address.lower():
            return jsonify({
                'success': False, 
                'error': 'Only token creator can confirm deployment'
            }), 403
        
        # If already deployed, return success (idempotent)
        if token.deployment_status == 'deployed' and token.contract_address:
            return jsonify({
                'success': True,
                'message': 'Token already deployed',
                'contract_address': token.contract_address,
                'token': {
                    'id': token.id,
                    'name': token.name,
                    'symbol': token.symbol,
                    'contract_address': token.contract_address
                }
            })
        
        # SECURITY: Get tx_hash from request (don't trust contract_address from frontend)
        tx_hash = (data.get('tx_hash') or '').strip()
        if not tx_hash:
            return jsonify({'success': False, 'error': 'tx_hash is required'}), 400
        
        # Validate tx_hash format
        if not tx_hash.startswith('0x') or len(tx_hash) != 66:
            return jsonify({'success': False, 'error': 'Invalid transaction hash format'}), 400
        
        # SECURITY: Extract contract address from blockchain with full verification
        web3_service = get_web3_service()
        
        try:
            # Pass creator wallet for event verification
            contract_address = web3_service.extract_token_address_from_receipt(
                tx_hash,
                expected_creator=creator.wallet_address
            )
            
            # Extract vesting addresses if PRO token
            vesting_addresses = None
            if token.reserved_percentage > 0:
                try:
                    vesting_addresses = web3_service.extract_vesting_addresses_from_receipt(tx_hash)
                    logging.info(f"Extracted vesting addresses for PRO token {token_id}: {vesting_addresses}")
                except Exception as e:
                    logging.error(f"Failed to extract vesting addresses for token {token_id}: {str(e)}")
            
            # Get transaction to verify sender
            tx = web3_service.w3.eth.get_transaction(tx_hash)
            
            # SECURITY: Verify transaction sender matches creator
            if tx['from'].lower() != creator.wallet_address.lower():
                return jsonify({
                    'success': False,
                    'error': 'Transaction was not sent by token creator'
                }), 403
                
        except ValueError as e:
            return jsonify({
                'success': False, 
                'error': f'Deployment verification failed: {str(e)}'
            }), 400
        except Exception as e:
            logging.error(f"Blockchain verification failed for tx {tx_hash}: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to verify deployment on blockchain'
            }), 500
        
        # Check for duplicate contract addresses
        existing = Token.query.filter(
            db.func.lower(Token.contract_address) == contract_address.lower(),
            Token.id != token_id
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': f'Contract address already exists for token ID {existing.id} ({existing.name})'
            }), 400
        
        # For bonding curve tokens, use total_supply from database since blockchain totalSupply() 
        # starts at 0 and only increases as tokens are bought
        circulating_supply_tokens = token.total_supply
        logging.info(f"✅ Setting circulating_supply for token {token_id} ({token.symbol}) to total_supply: {circulating_supply_tokens:,} tokens")
        
        # Update token record with verified data
        token.contract_address = contract_address
        token.deployment_tx = tx_hash
        token.deployment_block_number = data.get('block_number')
        token.deployment_status = 'deployed'
        token.is_active = True
        token.graduation_status = 'active'  # CRITICAL: Enable bonding curve trading and graduation eligibility
        token.circulating_supply = circulating_supply_tokens
        
        logging.info(f"📝 Updating token {token_id} ({token.symbol}) - Setting circulating_supply to {circulating_supply_tokens:,} tokens")
        
        # Save vesting addresses for PRO tokens
        if vesting_addresses and token.reserved_percentage > 0:
            token.airdrop_vesting_address = vesting_addresses.get('airdrop_vesting_address')
            token.marketing_vesting_address = vesting_addresses.get('marketing_vesting_address')
            token.team_vesting_address = vesting_addresses.get('team_vesting_address')
            logging.info(f"Saved vesting addresses for PRO token {token_id}")
        
        db.session.commit()
        
        # Log activity for token launch
        activity = Activity()
        activity.user_id = creator.id
        activity.activity_type = 'token_launch'
        activity.title = 'Token launch'
        activity.description = f'Launched {token.name} ({token.symbol})'
        activity.token_id = token.id
        activity.points_earned = 100
        activity.is_public = True
        db.session.add(activity)
        db.session.commit()
        
        logging.info(f"✅ Token {token_id} ({token.symbol}) deployment confirmed by creator {caller_address} - Contract: {contract_address}, TX: {tx_hash}, Circulating Supply: {circulating_supply_tokens:,} tokens")
        
        return jsonify({
            'success': True,
            'contract_address': token.contract_address,
            'token': {
                'id': token.id,
                'name': token.name,
                'symbol': token.symbol,
                'contract_address': token.contract_address,
                'deployment_status': token.deployment_status
            }
        })
        
    except Exception as e:
        logging.error(f"Confirm deployment failed for token {token_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Failed to confirm deployment: {str(e)}'}), 500

@app.route('/api/token/<int:token_id>/delete-pending', methods=['POST'])
@csrf.exempt
def delete_pending_token(token_id):
    """Delete pending token record if deployment failed (cleanup)"""
    try:
        token = Token.query.get(token_id)
        
        if not token:
            return jsonify({'success': True, 'message': 'Token not found (may already be deleted)'}), 200
        
        # Only delete if status is 'pending'
        if token.deployment_status != 'pending':
            return jsonify({
                'success': False, 
                'error': f'Cannot delete token with status: {token.deployment_status}'
            }), 400
        
        # Delete token_settings first (foreign key constraint)
        from models_extended import TokenSettings
        TokenSettings.query.filter_by(token_id=token_id).delete()
        
        # Delete token
        db.session.delete(token)
        db.session.commit()
        
        logging.info(f"Cleaned up pending token {token_id} ({token.name}) after failed deployment")
        
        return jsonify({'success': True, 'message': 'Pending token deleted'}), 200
        
    except Exception as e:
        logging.error(f"Failed to delete pending token {token_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/check-pending', methods=['GET'])
@csrf.exempt
def check_pending_tokens():
    """Check if user has any pending (undeployed) tokens"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        # Find pending tokens for this user (status=pending, created <24h ago)
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        pending = Token.query.filter(
            Token.creator_id == user.id,
            Token.deployment_status == 'pending',
            Token.created_at > cutoff
        ).order_by(Token.created_at.desc()).first()  # Get most recent
        
        if pending:
            return jsonify({
                'success': True,
                'has_pending': True,
                'token': {
                    'id': pending.id,
                    'name': pending.name,
                    'symbol': pending.symbol,
                    'description': pending.description,
                    'image_url': pending.image_url,
                    'ipfs_metadata_uri': pending.ipfs_metadata_url,
                    'created_at': pending.created_at.isoformat()
                }
            })
        else:
            return jsonify({'success': True, 'has_pending': False})
            
    except Exception as e:
        logging.error(f"Check pending tokens failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<int:token_id>/resume-deployment', methods=['POST'])
@csrf.exempt
def resume_token_deployment(token_id):
    """Resume deployment for a pending token (crash recovery)"""
    # Get pending token (let 404 propagate correctly)
    token = Token.query.get_or_404(token_id)
    
    # Verify status is pending
    if token.deployment_status != 'pending':
        return jsonify({
            'success': False,
            'error': f'Token status is {token.deployment_status}, cannot resume'
        }), 400
    
    # Verify user is creator
    user = get_current_user()
    if not user or token.creator_id != user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Check if token has IPFS metadata - required for deployment
    ipfs_url = token.ipfs_metadata_url or token.ipfs_image_url
    if not ipfs_url:
        return jsonify({
            'success': False,
            'error': 'Token does not have IPFS metadata. Please create a new token with proper metadata upload.'
        }), 400
    
    try:
        # Build unsigned transaction using existing token data
        try:
            user_address_checksum = Web3.to_checksum_address(user.wallet_address)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid wallet address format'}), 400
        
        web3_service = get_web3_service()
        
        # Convert total_supply to wei (assuming 18 decimals)
        # Must be int for Web3 uint256 encoding (database stores as Decimal)
        total_supply_wei = int(token.total_supply * (10 ** 18))
        
        # Match exact parameter order from /api/token/create endpoint
        unsigned_tx = web3_service.create_token_tx_data(
            user_address_checksum,
            token.name,
            token.symbol,
            total_supply_wei,
            token.description or f"{token.name} token",
            ipfs_url,  # Use metadata URL if available, fallback to image URL
            token.twitter or "",
            token.telegram or "",
            token.website or "",
            token.anti_bot_enabled,
            int(token.reserved_percentage),
            int(token.airdrops_allocation),
            int(token.marketing_allocation),
            int(token.team_allocation)
        )
        
        # Format response for frontend
        tx_data = {
            'to': unsigned_tx['to'],
            'value': hex(unsigned_tx['value']),
            'data': unsigned_tx['data'],
            'gas': hex(unsigned_tx['gas'])
        }
        
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'estimated_gas': unsigned_tx['gas'],
            'token_id': token_id
        })
        
    except Exception as e:
        logging.error(f"Resume deployment failed for token {token_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<contract_address>/sync-supply', methods=['POST'])
@csrf.exempt
def sync_token_supply(contract_address):
    """
    Sync circulating supply from blockchain for deployed tokens.
    
    This endpoint fixes tokens with 0 supply by fetching totalSupply from blockchain.
    Can be called manually, via retry logic, or by background jobs.
    
    Response:
    {
        "success": true,
        "circulating_supply": 1000000000,
        "message": "Supply synced successfully"
    }
    """
    try:
        # Find token by contract address
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == contract_address.lower()
        ).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Only sync deployed tokens
        if token.deployment_status != 'deployed':
            return jsonify({
                'success': False,
                'error': f'Token not deployed (status: {token.deployment_status})'
            }), 400
        
        if not token.contract_address:
            return jsonify({'success': False, 'error': 'No contract address set'}), 400
        
        # Fetch totalSupply from blockchain
        try:
            import json
            with open('artifacts/contracts/BondingCurvePool.sol/BondingCurvePool.json') as f:
                pool_abi = json.load(f)['abi']
            
            web3_service = get_web3_service()
            pool_contract = web3_service.w3.eth.contract(
                address=Web3.to_checksum_address(token.contract_address),
                abi=pool_abi
            )
            
            total_supply_wei = pool_contract.functions.totalSupply().call()
            circulating_supply_tokens = total_supply_wei // (10 ** 18)  # Convert from wei to tokens
            
            # Update token
            token.circulating_supply = circulating_supply_tokens
            db.session.commit()
            
            logging.info(f"Supply synced for token {token.id} ({token.symbol}): {circulating_supply_tokens:,} tokens")
            
            return jsonify({
                'success': True,
                'circulating_supply': circulating_supply_tokens,
                'message': 'Supply synced successfully from blockchain'
            })
            
        except Exception as e:
            logging.error(f"Failed to fetch totalSupply from blockchain for {contract_address}: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch supply from blockchain: {str(e)}'
            }), 500
        
    except Exception as e:
        logging.error(f"Supply sync failed for {contract_address}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<contract_address>/chart-data', methods=['GET'])
@cache.cached(timeout=5, query_string=True)  # Cache for 5 seconds (real-time charts need fresher data)
def get_token_chart_data(contract_address):
    """
    Get real trade history data for token price/volume chart with OHLC candlesticks
    NOW USING GRAPHQL - Fetches trades directly from blockchain via Blockscout
    
    Query params:
    - timeframe: '24h' (default), '7d', '30d'
    - interval: '1m', '5m', '15m', '1h', '4h', '1d' (default: auto-select based on timeframe)
    - format: 'candlestick' (OHLC) or 'area' (default: auto-select based on trade count)
    
    Response (candlestick):
    {
        "success": true,
        "data": [
            {"time": "2025-10-16T10:00:00Z", "open": 0.000015, "high": 0.000017, "low": 0.000014, "close": 0.000016, "volume": 1500},
            ...
        ],
        "format": "candlestick"
    }
    
    Response (area - fallback for <3 trades):
    {
        "success": true,
        "data": [
            {"time": "2025-10-16T10:00:00Z", "value": 15000, "volume": 1500},
            ...
        ],
        "format": "area"
    }
    """
    try:
        # Find token by contract address
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == contract_address.lower()
        ).first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        # Get KAS price from oracle (cached for 5 minutes)
        from services.kas_oracle import oracle
        kas_to_usd = oracle.get_kas_price()
        
        # Get query parameters
        timeframe = request.args.get('timeframe', '24h')
        requested_interval = request.args.get('interval', None)
        requested_format = request.args.get('format', None)
        chart_type = request.args.get('type', 'marketcap')  # 'price' or 'marketcap'
        
        # Calculate time window
        now = datetime.now(timezone.utc)
        if timeframe == '7d':
            start_time = now - timedelta(days=7)
            default_interval = '1h'
        elif timeframe == '30d':
            start_time = now - timedelta(days=30)
            default_interval = '4h'
        else:  # Default 24h
            start_time = now - timedelta(hours=24)
            default_interval = '5m'
        
        interval = requested_interval or default_interval
        
        # Use TradeEvent database for chart data (indexed by event indexer)
        # GraphQL has complexity limits that prevent fetching complete history
        all_db_trades = TradeEvent.query.filter(
            TradeEvent.token_id == token.id
        ).order_by(TradeEvent.timestamp.asc()).all()
        
        if not all_db_trades:
            # No trades yet, return current stats as area chart
            current_price_kas = float(token.current_price or 0)
            current_mc_kas = float(token.current_market_cap or 0)
            current_price_usd = current_price_kas * kas_to_usd
            current_mc_usd = current_mc_kas * kas_to_usd
            
            value = current_mc_usd if chart_type == 'marketcap' else current_price_usd
            return jsonify({
                'success': True,
                'data': [{
                    'time': int(now.timestamp()),
                    'value': value,
                    'volume': 0
                }],
                'format': 'area',
                'timeframe': timeframe,
                'interval': interval
            })
        
        # Convert database trades to dict format
        all_trades = []
        for trade in all_db_trades:
            all_trades.append({
                'trade_type': trade.trade_type,
                'timestamp': trade.timestamp,
                'kas_amount': float(trade.kas_amount or 0),
                'token_amount': float(trade.token_amount or 0),
                'trader_address': trade.user_wallet_address,
                'tx_hash': trade.tx_hash
            })
        
        # Filter trades within the requested timeframe (ensure timezone-aware comparison)
        # Make start_time timezone-aware if it isn't already
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        
        # Ensure all timestamps are timezone-aware for comparison
        for trade in all_trades:
            if trade['timestamp'].tzinfo is None:
                trade['timestamp'] = trade['timestamp'].replace(tzinfo=timezone.utc)
        
        trades_in_window = [t for t in all_trades if t['timestamp'] >= start_time]
        prior_trades = [t for t in all_trades if t['timestamp'] < start_time]
        
        # If no trades in time window but trades exist, show all available data
        if not trades_in_window and all_trades:
            logging.info(f"No trades in {timeframe} window for {token.symbol}, showing all {len(all_trades)} trades")
            trades_in_window = all_trades
            prior_trades = []
            # Adjust start_time to earliest trade
            if all_trades:
                start_time = min(t['timestamp'] for t in all_trades)
        
        # Get CURRENT blockchain reserves (live state)
        web3_service = get_web3_service()
        try:
            current_kas_wei = web3_service.get_virtual_kas_reserve(token.contract_address)
            current_token_wei = web3_service.get_virtual_token_reserve(token.contract_address)
            current_kas_reserve = float(Web3.from_wei(current_kas_wei, 'ether'))
            current_token_reserve = float(current_token_wei)
            
            app.logger.info(
                f"[Chart] Starting from CURRENT blockchain reserves for {token.symbol}: "
                f"KAS={current_kas_reserve:.2f}, Tokens={current_token_reserve/1e18:.2f}"
            )
            
            # Work BACKWARDS through trades in window to get starting reserves for the chart
            for trade in reversed(trades_in_window):
                kas_amt = float(trade['kas_amount'])
                token_amt = float(trade['token_amount'])
                
                if trade['trade_type'] == 'buy':
                    # Undo buy: remove KAS, add back tokens
                    current_kas_reserve -= kas_amt
                    current_token_reserve += token_amt
                else:
                    # Undo sell: add back KAS, remove tokens
                    current_kas_reserve += kas_amt
                    current_token_reserve -= token_amt
            
            # Clamp to prevent negative reserves from incomplete trade history
            current_kas_reserve = max(0.001, current_kas_reserve)
            current_token_reserve = max(1e18, current_token_reserve)
            
        except Exception as e:
            app.logger.error(f"Failed to get blockchain reserves for {token.symbol}, using fallback: {e}")
            # Fallback: Calculate from database (less accurate)
            total_supply_tokens = float(token.total_supply or 0)
            reserved_pct = float(token.reserved_percentage or 0)
            bonding_curve_tokens = total_supply_tokens * ((100 - reserved_pct) / 100)
            current_token_reserve = bonding_curve_tokens * 1e18
            current_kas_reserve = float(token.kas_reserve or 0) if token.kas_reserve else 200 / kas_to_usd
        
        app.logger.debug(
            f"Chart starting reserves for {token.symbol}: "
            f"KAS={current_kas_reserve:.2f}, Tokens={current_token_reserve/1e18:.0f}"
        )
        
        # Build trade points by processing trades in window
        trade_points = []
        for trade in trades_in_window:
            kas_amt = float(trade['kas_amount'])
            token_amt = float(trade['token_amount'])
            
            # Update reserves based on trade type
            if trade['trade_type'] == 'buy':
                current_kas_reserve += kas_amt
                current_token_reserve -= token_amt
            else:
                current_kas_reserve -= kas_amt
                current_token_reserve += token_amt
            
            # Calculate spot price from reserve ratio (bonding curve formula)
            if current_token_reserve > 0:
                price_per_token_kas = current_kas_reserve / (current_token_reserve / 1e18)
            else:
                price_per_token_kas = 0
            
            # Convert to USD using oracle price
            price_per_token_usd = price_per_token_kas * kas_to_usd
            
            # Market cap for bonding curve = KAS reserve (total value locked)
            # NOTE: Do NOT use price × circulating_supply - that overestimates
            # because it assumes all tokens were bought at current price
            market_cap_usd = current_kas_reserve * kas_to_usd
            
            trade_points.append({
                'timestamp': trade['timestamp'],
                'price': price_per_token_usd,
                'market_cap': market_cap_usd,
                'volume': kas_amt,
                'trade_type': trade['trade_type']
            })
        
        # Decide format based on trade count
        if requested_format:
            use_format = requested_format
        else:
            # Always use candlesticks when there's trade data
            use_format = 'candlestick' if len(trade_points) > 0 else 'area'
        
        # If no trades, return current stats as area chart
        if not trade_points:
            # Convert current price/mcap to USD
            current_price_kas = float(token.current_price or 0)
            current_mc_kas = float(token.current_market_cap or 0)
            current_price_usd = current_price_kas * kas_to_usd
            current_mc_usd = current_mc_kas * kas_to_usd
            
            value = current_mc_usd if chart_type == 'marketcap' else current_price_usd
            return jsonify({
                'success': True,
                'data': [{
                    'time': int(now.timestamp()),  # Unix timestamp (seconds)
                    'value': value,
                    'volume': 0
                }],
                'format': 'area',
                'timeframe': timeframe,
                'interval': interval
            })
        
        # Generate chart data based on format
        if use_format == 'candlestick':
            # Pass deployment timestamp to enable synthetic zero-market-cap starting candle
            chart_data = aggregate_ohlc_data(
                trade_points, 
                interval, 
                start_time, 
                now, 
                chart_type,
                deployment_timestamp=token.created_at
            )
        else:  # area format
            chart_data = []
            for point in trade_points:
                # Use price or market cap based on chart type
                value = point['price'] if chart_type == 'price' else point['market_cap']
                chart_data.append({
                    'time': int(point['timestamp'].timestamp()),  # Unix timestamp (seconds)
                    'value': value,
                    'volume': point['volume']
                })
            
            # Ensure we always have at least one point for area chart
            if not chart_data:
                if chart_type == 'price':
                    value = float(token.current_price or 0) * kas_to_usd
                else:  # marketcap
                    value = float(token.current_market_cap or 0) * kas_to_usd
                chart_data.append({
                    'time': int(now.timestamp()),
                    'value': value,
                    'volume': 0
                })
        
        return jsonify({
            'success': True,
            'data': chart_data,
            'format': use_format,
            'timeframe': timeframe,
            'interval': interval
        })
        
    except Exception as e:
        logging.error(f"Error fetching chart data for {contract_address}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


def aggregate_ohlc_data(trade_points, interval, start_time, end_time, chart_type='marketcap', deployment_timestamp=None):
    """
    Aggregate trade data into OHLC candlesticks
    
    Args:
        trade_points: List of dicts with timestamp, price, market_cap, volume
        interval: '1m', '5m', '15m', '1h', '4h', '1d'
        start_time: Start of time window
        end_time: End of time window
        chart_type: 'price' or 'marketcap' - determines which values to use for OHLC
        deployment_timestamp: Token deployment datetime (for synthetic zero candle)
    
    Returns:
        List of OHLC candles: [{"time": unix_seconds, "open": x, "high": y, "low": z, "close": w, "volume": v}, ...]
    """
    from collections import defaultdict
    
    # Validate and parse interval to seconds
    valid_intervals = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400
    }
    
    if interval not in valid_intervals:
        logging.warning(f"Invalid interval '{interval}', defaulting to 5m")
        interval = '5m'
    
    interval_seconds = valid_intervals[interval]
    
    # Group trades into time buckets
    buckets = defaultdict(list)
    
    for point in trade_points:
        # Calculate bucket timestamp (floor to ABSOLUTE interval boundaries)
        timestamp = point['timestamp']
        
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Get Unix timestamp (seconds since epoch)
        unix_timestamp = int(timestamp.timestamp())
        
        # Floor to absolute interval boundary
        # This ensures candles align to proper time boundaries:
        # - 1h: :00 of each hour (e.g., 13:00, 14:00, 15:00)
        # - 15m: :00, :15, :30, :45 of each hour
        # - 5m: :00, :05, :10, etc.
        # - 4h: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
        # - 1d: 00:00:00 of each day
        bucket_key = (unix_timestamp // interval_seconds) * interval_seconds
        buckets[bucket_key].append(point)
    
    # If no trades, return empty list
    if not buckets:
        return []
    
    # Calculate the full range of candles from first trade to current time
    # Ensure start_time and end_time are timezone-aware
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    # Floor start_time to interval boundary
    start_unix = int(start_time.timestamp())
    start_bucket = (start_unix // interval_seconds) * interval_seconds
    
    # Floor end_time to interval boundary
    end_unix = int(end_time.timestamp())
    end_bucket = (end_unix // interval_seconds) * interval_seconds
    
    # Build OHLC candles with proper open/close tracking and gap filling
    candles = []
    previous_close = None
    
    # Handle synthetic deployment candle if appropriate
    deployment_bucket_idx = None
    actual_start_bucket = start_bucket  # Will be adjusted to deployment/first trade bucket
    
    if deployment_timestamp and trade_points:
        # Ensure deployment_timestamp is timezone-aware
        if deployment_timestamp.tzinfo is None:
            deployment_timestamp = deployment_timestamp.replace(tzinfo=timezone.utc)
        
        deployment_unix = int(deployment_timestamp.timestamp())
        deployment_bucket = (deployment_unix // interval_seconds) * interval_seconds
        
        # Only add deployment candle if it's before the first trade and within chart window
        first_trade_time = min(t['timestamp'].timestamp() for t in trade_points)
        first_trade_bucket = (int(first_trade_time) // interval_seconds) * interval_seconds
        
        if deployment_unix < first_trade_time and deployment_bucket >= start_bucket:
            # Get first trade's close value for high/close of deployment candle
            first_trade_value = trade_points[0]['price'] if chart_type == 'price' else trade_points[0]['market_cap']
            
            # Check if deployment shares a bucket with any trade
            if deployment_bucket == first_trade_bucket:
                # Same bucket: we'll mutate the first candle later (mark for mutation)
                deployment_bucket_idx = deployment_bucket
                actual_start_bucket = deployment_bucket  # Start from deployment
                app.logger.debug(
                    f"Deployment shares bucket with first trade, will mutate first candle to start at 0"
                )
            else:
                # Different bucket: prepend synthetic zero-start candle
                candles.append({
                    'time': deployment_bucket,
                    'open': 0,
                    'high': first_trade_value,
                    'low': 0,
                    'close': first_trade_value,
                    'volume': 0
                })
                previous_close = first_trade_value
                actual_start_bucket = deployment_bucket  # Start from deployment
                
                app.logger.debug(
                    f"Prepended deployment candle at {deployment_timestamp} "
                    f"(0 → {first_trade_value:.2f} {chart_type})"
                )
        else:
            # No deployment candle needed, start from first trade
            actual_start_bucket = first_trade_bucket
    else:
        # No deployment timestamp, start from first trade bucket
        if trade_points:
            first_trade_time = min(t['timestamp'].timestamp() for t in trade_points)
            first_trade_bucket = (int(first_trade_time) // interval_seconds) * interval_seconds
            actual_start_bucket = first_trade_bucket
    
    # Iterate through time buckets from actual_start_bucket (deployment or first trade)
    # This prevents showing hundreds of empty candles before the token existed
    current_bucket = actual_start_bucket
    while current_bucket <= end_bucket:
        bucket_trades = buckets.get(current_bucket, [])
        
        if bucket_trades:
            # This bucket has trades - calculate OHLC normally
            # Get values based on chart type (price or market cap)
            if chart_type == 'price':
                values = [t['price'] for t in bucket_trades]
            else:  # marketcap
                values = [t['market_cap'] for t in bucket_trades]
            
            # OHLC calculation with proper open tracking
            # Open: use previous candle's close, or first trade if no previous
            if previous_close is not None:
                open_value = previous_close
            else:
                open_value = values[0]
            
            # Close: always the last value in this bucket
            close_value = values[-1]
            
            # High: max of all values AND the open (to ensure wick shows properly)
            high_value = max(max(values), open_value)
            
            # Low: min of all values AND the open (to ensure wick shows properly)
            low_value = min(min(values), open_value)
            
            # Sum volume in bucket
            total_volume = sum(t['volume'] for t in bucket_trades)
        else:
            # Empty bucket - fill with flat candle (previous close)
            if previous_close is not None:
                open_value = previous_close
                high_value = previous_close
                low_value = previous_close
                close_value = previous_close
                total_volume = 0
            else:
                # Skip empty buckets before first trade
                current_bucket += interval_seconds
                continue
        
        candle = {
            'time': current_bucket,  # Unix timestamp (seconds)
            'open': open_value,
            'high': high_value,
            'low': low_value,
            'close': close_value,
            'volume': total_volume
        }
        
        # If this is the first candle and deployment shares this bucket, mutate to start at 0
        if deployment_bucket_idx is not None and current_bucket == deployment_bucket_idx and len(candles) == 0:
            candle['open'] = 0
            candle['low'] = 0
            app.logger.debug(
                f"Mutated first candle (same bucket as deployment) to start at 0: "
                f"open=0, low=0, high={candle['high']:.2f}, close={candle['close']:.2f}"
            )
        
        candles.append(candle)
        
        # Update previous close for next candle
        previous_close = close_value
        
        # Move to next bucket
        current_bucket += interval_seconds
    
    # Ensure candles are sorted by time (should already be, but guarantee it)
    candles.sort(key=lambda c: c['time'])
    
    return candles

# ========================================
# PRO Token Vesting API Endpoints
# ========================================

@app.route('/api/token/<int:token_id>/vesting/status', methods=['GET'])
@cache.cached(timeout=30, query_string=True)  # Cache for 30 seconds (vesting changes slowly)
@csrf.exempt
def get_token_vesting_status(token_id):
    """
    Get vesting status for a PRO token (marketing, team, airdrop contracts)
    
    Response:
    {
        "success": true,
        "vesting": {
            "marketing": {
                "contract_address": "0x...",
                "total_amount": 1000000,
                "unlocked_amount": 250000,
                "claimed_amount": 100000,
                "available_to_claim": 150000,
                "duration": 31536000,
                "start_time": 1234567890,
                "beneficiary": "0x..."
            },
            "team": { ... },
            "airdrop": { ... }
        }
    }
    """
    # Let 404s propagate correctly
    token = Token.query.get_or_404(token_id)
    
    # Check if this is a PRO token with vesting
    if not token.reserved_percentage or token.reserved_percentage == 0:
        return jsonify({
            'success': False,
            'error': 'This is not a PRO token with vesting'
        }), 400
    
    # Check if token is deployed
    if token.deployment_status != 'deployed':
        return jsonify({
            'success': False,
            'error': 'Token not deployed yet'
        }), 400
    
    try:
        web3_service = get_web3_service()
        vesting_status = {}
        
        # Get marketing vesting status
        if token.marketing_vesting_address:
            try:
                marketing_status = web3_service.get_marketing_vesting_status(token.marketing_vesting_address)
                vesting_status['marketing'] = {
                    'contract_address': token.marketing_vesting_address,
                    **marketing_status
                }
            except Exception as e:
                logging.error(f"Failed to get marketing vesting status: {e}")
                vesting_status['marketing'] = {'error': str(e)}
        
        # Get team vesting status
        if token.team_vesting_address:
            try:
                team_status = web3_service.get_team_vesting_status(token.team_vesting_address)
                vesting_status['team'] = {
                    'contract_address': token.team_vesting_address,
                    **team_status
                }
            except Exception as e:
                logging.error(f"Failed to get team vesting status: {e}")
                vesting_status['team'] = {'error': str(e)}
        
        # Get airdrop vesting status
        if token.airdrop_vesting_address:
            try:
                airdrop_status = web3_service.get_airdrop_vesting_status(token.airdrop_vesting_address)
                vesting_status['airdrop'] = {
                    'contract_address': token.airdrop_vesting_address,
                    **airdrop_status
                }
            except Exception as e:
                logging.error(f"Failed to get airdrop vesting status: {e}")
                vesting_status['airdrop'] = {'error': str(e)}
        
        return jsonify({
            'success': True,
            'vesting': vesting_status
        })
        
    except Exception as e:
        logging.error(f"Failed to get vesting status for token {token_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/token/<int:token_id>/vesting/withdraw-marketing', methods=['POST'])
@csrf.exempt
def build_marketing_vesting_withdraw(token_id):
    """
    Build transaction to withdraw unlocked marketing tokens
    
    Request JSON:
    {
        "creator_address": "0x..."
    }
    
    Response:
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "data": "0x...",
            "value": "0x0",
            "gas": "0x..."
        },
        "available_to_claim": 150000
    }
    """
    # Let 404s propagate correctly
    token = Token.query.get_or_404(token_id)
    
    # Check if still in cooldown
    if token.marketing_next_claim_available:
        now = datetime.utcnow()
        if now < token.marketing_next_claim_available:
            seconds_remaining = (token.marketing_next_claim_available - now).total_seconds()
            hours_remaining = int(seconds_remaining / 3600)
            minutes_remaining = int((seconds_remaining % 3600) / 60)
            return jsonify({
                'success': False,
                'error': f'Claim cooldown active. Next claim available in {hours_remaining}h {minutes_remaining}m',
                'next_claim_available': token.marketing_next_claim_available.isoformat(),
                'seconds_remaining': int(seconds_remaining)
            }), 429
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        creator_address = data.get('creator_address')
        
        if not creator_address:
            return jsonify({'success': False, 'error': 'creator_address is required'}), 400
        
        # Check if token has marketing vesting
        if not token.marketing_vesting_address:
            return jsonify({
                'success': False,
                'error': 'Token does not have marketing vesting contract'
            }), 400
        
        web3_service = get_web3_service()
        
        # Get vesting status to check available amount
        try:
            status = web3_service.get_marketing_vesting_status(token.marketing_vesting_address)
            available = status['available_to_claim']
        except Exception as e:
            logging.error(f"Failed to get marketing vesting status: {e}")
            available = 0
        
        # Build withdraw transaction
        unsigned_tx = web3_service.build_marketing_vesting_withdraw_tx(
            token.marketing_vesting_address,
            creator_address
        )
        
        # Format response
        tx_data = {
            'to': unsigned_tx['to'],
            'value': hex(unsigned_tx['value']),
            'data': unsigned_tx['data'],
            'gas': hex(unsigned_tx['gas'])
        }
        
        # SET COOLDOWN IMMEDIATELY (BEFORE returning tx_data)
        # This ensures cooldown is enforced even if client doesn't call set-cooldown
        # Random 12-24 hour cooldown prevents gaming
        base_cooldown = 12 * 3600  # 12 hours in seconds
        random_addition = random.randint(0, 12 * 3600)  # 0-12 hours random
        total_cooldown = base_cooldown + random_addition
        
        token.marketing_next_claim_available = datetime.utcnow() + timedelta(seconds=total_cooldown)
        db.session.commit()
        
        # Return tx_data WITH cooldown info for frontend display
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'available_to_claim': available,
            'estimated_gas': unsigned_tx['gas'],
            'next_claim_available': token.marketing_next_claim_available.isoformat(),
            'cooldown_hours': total_cooldown / 3600
        })
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Failed to build marketing vesting withdraw tx: {error_msg}")
        
        # Clean up error messages for user-friendly display
        if 'exceeds max wallet' in error_msg.lower():
            return jsonify({
                'success': False,
                'error': 'Token Limit Reached: Your wallet already holds the maximum allowed amount (10% of total supply). This is a rug protection mechanism to protect other users. Please claim to a different wallet or reduce your holdings first.'
            }), 400
        
        # Return generic error for other cases
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/token/<int:token_id>/vesting/withdraw-team', methods=['POST'])
@csrf.exempt
def build_team_vesting_withdraw(token_id):
    """
    Build transaction to withdraw unlocked team tokens
    
    Request JSON:
    {
        "creator_address": "0x..."
    }
    
    Response:
    {
        "success": true,
        "tx_data": {
            "to": "0x...",
            "data": "0x...",
            "value": "0x0",
            "gas": "0x..."
        },
        "available_to_claim": 150000
    }
    """
    # Let 404s propagate correctly
    token = Token.query.get_or_404(token_id)
    
    # Check if still in cooldown
    if token.team_next_claim_available:
        now = datetime.utcnow()
        if now < token.team_next_claim_available:
            seconds_remaining = (token.team_next_claim_available - now).total_seconds()
            hours_remaining = int(seconds_remaining / 3600)
            minutes_remaining = int((seconds_remaining % 3600) / 60)
            return jsonify({
                'success': False,
                'error': f'Claim cooldown active. Next claim available in {hours_remaining}h {minutes_remaining}m',
                'next_claim_available': token.team_next_claim_available.isoformat(),
                'seconds_remaining': int(seconds_remaining)
            }), 429
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        creator_address = data.get('creator_address')
        
        if not creator_address:
            return jsonify({'success': False, 'error': 'creator_address is required'}), 400
        
        # Check if token has team vesting
        if not token.team_vesting_address:
            return jsonify({
                'success': False,
                'error': 'Token does not have team vesting contract'
            }), 400
        
        web3_service = get_web3_service()
        
        # Get vesting status to check available amount
        try:
            status = web3_service.get_team_vesting_status(token.team_vesting_address)
            available = status['available_to_claim']
        except Exception as e:
            logging.error(f"Failed to get team vesting status: {e}")
            available = 0
        
        # Build withdraw transaction
        unsigned_tx = web3_service.build_team_vesting_withdraw_tx(
            token.team_vesting_address,
            creator_address
        )
        
        # Format response
        tx_data = {
            'to': unsigned_tx['to'],
            'value': hex(unsigned_tx['value']),
            'data': unsigned_tx['data'],
            'gas': hex(unsigned_tx['gas'])
        }
        
        # SET COOLDOWN IMMEDIATELY (BEFORE returning tx_data)
        # This ensures cooldown is enforced even if client doesn't call set-cooldown
        # Random 12-24 hour cooldown prevents gaming
        base_cooldown = 12 * 3600  # 12 hours in seconds
        random_addition = random.randint(0, 12 * 3600)  # 0-12 hours random
        total_cooldown = base_cooldown + random_addition
        
        token.team_next_claim_available = datetime.utcnow() + timedelta(seconds=total_cooldown)
        db.session.commit()
        
        # Return tx_data WITH cooldown info for frontend display
        return jsonify({
            'success': True,
            'tx_data': tx_data,
            'available_to_claim': available,
            'estimated_gas': unsigned_tx['gas'],
            'next_claim_available': token.team_next_claim_available.isoformat(),
            'cooldown_hours': total_cooldown / 3600
        })
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Failed to build team vesting withdraw tx: {error_msg}")
        
        # Clean up error messages for user-friendly display
        if 'exceeds max wallet' in error_msg.lower():
            return jsonify({
                'success': False,
                'error': 'Token Limit Reached: Your wallet already holds the maximum allowed amount (10% of total supply). This is a rug protection mechanism to protect other users. Please claim to a different wallet or reduce your holdings first.'
            }), 400
        
        # Return generic error for other cases
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/token/<int:token_id>/vesting/cooldown-status')
def get_vesting_cooldown_status(token_id):
    """
    Get current cooldown status for all vesting types
    
    Frontend can use this to check if claims are available and show countdown timers.
    
    Response:
    {
        "marketing": {
            "on_cooldown": true,
            "next_available": "2025-10-17T10:30:00Z",
            "seconds_remaining": 43200
        },
        "team": {
            "on_cooldown": false,
            "next_available": null,
            "seconds_remaining": 0
        }
    }
    """
    try:
        token = Token.query.get_or_404(token_id)
        now = datetime.utcnow()
        
        result = {
            'marketing': {
                'on_cooldown': False,
                'next_available': None,
                'seconds_remaining': 0
            },
            'team': {
                'on_cooldown': False,
                'next_available': None,
                'seconds_remaining': 0
            }
        }
        
        # Marketing cooldown
        if token.marketing_next_claim_available and now < token.marketing_next_claim_available:
            result['marketing']['on_cooldown'] = True
            result['marketing']['next_available'] = token.marketing_next_claim_available.isoformat()
            result['marketing']['seconds_remaining'] = int((token.marketing_next_claim_available - now).total_seconds())
        
        # Team cooldown
        if token.team_next_claim_available and now < token.team_next_claim_available:
            result['team']['on_cooldown'] = True
            result['team']['next_available'] = token.team_next_claim_available.isoformat()
            result['team']['seconds_remaining'] = int((token.team_next_claim_available - now).total_seconds())
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error getting cooldown status for token {token_id}: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================
# Admin API Endpoints
# ========================================

@app.route('/api/admin/distribute-platform-fees', methods=['POST'])
@csrf.exempt
def api_distribute_platform_fees():
    """
    Distribute accumulated platform fees to treasury wallets (ADMIN ONLY)
    
    This endpoint allows treasury or admin to distribute platform fees from a pool.
    Platform fees are split:
    - 40% → Platform Development Wallet
    - 30% → Buyback Reserve Wallet
    - 15% → Kaspa Network Support Wallet
    - 15% → Community Rewards Wallet
    
    Request JSON (Step 1 - Get Unsigned TX):
    {
        "action": "build_tx",
        "admin_address": "0x...",
        "token_address": "0x..."
    }
    
    Response (Step 1):
    {
        "success": true,
        "unsigned_tx": {
            "from": "0x...",
            "to": "0x...",
            "data": "0x...",
            "value": "0x0",
            "gas": "0x...",
            "gasPrice": "0x...",
            "nonce": "0x...",
            "chainId": 167012
        },
        "claimable_amount": "1.234",
        "claimable_amount_wei": "1234000000000000000"
    }
    
    Request JSON (Step 2 - Relay Signed TX):
    {
        "action": "relay_tx",
        "signed_tx": "0x..."
    }
    
    Response (Step 2):
    {
        "success": true,
        "tx_hash": "0x...",
        "status": "pending"
    }
    
    Example curl (build_tx):
    curl -X POST http://localhost:5000/api/admin/distribute-platform-fees \
      -H "Content-Type: application/json" \
      -d '{"action": "build_tx", "admin_address": "0x5f837F62744D4d80Fc79C3A5346B4A228956914E", "token_address": "0x..."}'
    
    Example curl (relay_tx):
    curl -X POST http://localhost:5000/api/admin/distribute-platform-fees \
      -H "Content-Type: application/json" \
      -d '{"action": "relay_tx", "signed_tx": "0x..."}'
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
        
        action = data.get('action', '').strip()
        
        if action == 'build_tx':
            admin_address = data.get('admin_address', '').strip()
            token_address = data.get('token_address', '').strip()
            
            if not admin_address:
                return jsonify({'success': False, 'error': 'admin_address is required'}), 400
            
            if not token_address:
                return jsonify({'success': False, 'error': 'token_address is required'}), 400
            
            try:
                admin_address = Web3.to_checksum_address(admin_address)
                pool_address = Web3.to_checksum_address(token_address)
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid address format'}), 400
            
            token = Token.query.filter_by(contract_address=pool_address).first()
            if not token:
                return jsonify({'success': False, 'error': 'Token not found'}), 404
            
            if token.deployment_status != 'deployed':
                return jsonify({'success': False, 'error': 'Token not deployed yet'}), 400
            
            web3_service = get_web3_service()
            
            claimable_wei = web3_service.get_platform_claimable(pool_address)
            
            if claimable_wei == 0:
                return jsonify({
                    'success': False,
                    'error': 'No platform fees available to distribute'
                }), 400
            
            claimable_kas = float(Web3.from_wei(claimable_wei, 'ether'))
            
            unsigned_tx = web3_service.distribute_platform_fees_tx_data(
                admin_address,
                pool_address
            )
            
            unsigned_tx_formatted = {
                'from': unsigned_tx['from'],
                'to': unsigned_tx['to'],
                'data': unsigned_tx['data'],
                'value': hex(unsigned_tx['value']),
                'gas': hex(unsigned_tx['gas']),
                'gasPrice': hex(unsigned_tx['gasPrice']),
                'nonce': hex(unsigned_tx['nonce']),
                'chainId': 167012
            }
            
            logging.info(f"Built distribute platform fees tx for {admin_address} - Claimable: {claimable_kas} KAS")
            
            return jsonify({
                'success': True,
                'unsigned_tx': unsigned_tx_formatted,
                'claimable_amount': str(claimable_kas),
                'claimable_amount_wei': str(claimable_wei)
            })
        
        elif action == 'relay_tx':
            signed_tx = data.get('signed_tx', '').strip()
            
            if not signed_tx:
                return jsonify({'success': False, 'error': 'signed_tx is required'}), 400
            
            if not isinstance(signed_tx, str) or not signed_tx.startswith('0x'):
                return jsonify({'success': False, 'error': 'signed_tx must be a hex string starting with 0x'}), 400
            
            web3_service = get_web3_service()
            tx_hash = web3_service.relay_signed_transaction(signed_tx)
            
            # Add to monitoring queue
            tx_monitor = get_tx_monitor()
            tx_monitor.add_pending_transaction(
                tx_hash=tx_hash,
                tx_type='distribute_fees',
                user_address=data.get('admin_address'),
                token_id=None  # Get from context if available
            )
            
            logging.info(f"Relayed distribute platform fees tx: {tx_hash}")
            
            return jsonify({
                'success': True,
                'tx_hash': tx_hash,
                'status': 'pending'
            })
        
        else:
            return jsonify({'success': False, 'error': 'Invalid action. Must be "build_tx" or "relay_tx"'}), 400
    
    except ValueError as e:
        logging.debug(f"Validation error in distribute-platform-fees: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error in distribute-platform-fees: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to distribute platform fees'}), 500

# Real-time graduation trigger endpoint (called by frontend when market cap >= threshold)
@app.route('/api/token/<token_address>/trigger-graduation', methods=['POST'])
def trigger_graduation(token_address):
    """
    Real-time graduation trigger endpoint
    Called by frontend immediately when bonding curve hits 100% (market cap >= $50)
    Provides instant, seamless graduation like pump.fun without waiting for polling cycles
    
    CONCURRENCY SAFETY: Uses DB-level SELECT FOR UPDATE lock to prevent duplicate graduations
    when multiple Gunicorn workers handle simultaneous requests
    """
    try:
        from services.graduation_state_manager import GraduationStateManager
        from services.kas_oracle import oracle
        from sqlalchemy import select
        
        token_address_checksum = Web3.to_checksum_address(token_address)
        
        token = db.session.query(Token).filter_by(
            contract_address=token_address_checksum
        ).with_for_update().first()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404
        
        logging.info(f"🚀 Real-time graduation trigger for {token.symbol} ({token_address_checksum})")
        
        if token.is_graduated:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Token already graduated',
                'status': 'graduated',
                'already_triggered': True
            })
        
        if token.graduation_status in ['initiating', 'completing']:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Graduation already in progress (status: {token.graduation_status})',
                'status': token.graduation_status,
                'already_triggered': True
            })
        
        web3_service = get_web3_service()
        pool = web3_service.get_bonding_pool_contract(token_address_checksum)
        
        kas_reserve_wei = pool.functions.virtualKasReserve().call()
        market_cap_usd = oracle.get_market_cap_usd(kas_reserve_wei)
        
        graduation_threshold_usd = float(PlatformSettings.get_settings().graduation_threshold_usd)
        
        if market_cap_usd < graduation_threshold_usd:
            db.session.commit()
            return jsonify({
                'success': False,
                'error': f'Market cap ${market_cap_usd:.2f} below threshold ${graduation_threshold_usd:.2f}',
                'market_cap': market_cap_usd,
                'threshold': graduation_threshold_usd,
                'status': 'not_ready'
            }), 400
        
        logging.info(f"✅ {token.symbol} eligible for graduation - Market cap: ${market_cap_usd:.2f} >= ${graduation_threshold_usd:.2f}")
        
        oracle_wallet = web3_service.oracle_account
        
        result = GraduationStateManager.initiate_graduation(token, oracle_wallet)
        
        if result.get('success'):
            logging.info(f"✅ Graduation initiated for {token.symbol} - TX: {result.get('tx_hash')}")
            
            db.session.commit()
            db.session.refresh(token)
            
            return jsonify({
                'success': True,
                'message': 'Graduation initiated successfully',
                'tx_hash': result.get('tx_hash'),
                'status': token.graduation_status,
                'market_cap': market_cap_usd
            })
        else:
            error_msg = result.get('error', 'Unknown error during graduation initiation')
            logging.error(f"❌ Failed to initiate graduation for {token.symbol}: {error_msg}")
            
            db.session.rollback()
            
            return jsonify({
                'success': True,
                'message': 'Graduation already in progress',
                'status': 'initiating',
                'already_triggered': True
            })
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in trigger_graduation for {token_address}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Admin endpoint for testing graduation completion
@app.route('/api/admin/trigger-graduation-completion/<token_symbol>', methods=['POST'])
def trigger_graduation_completion(token_symbol):
    """
    Admin endpoint to manually trigger graduation completion for a specific token
    Useful for testing and debugging graduation flow
    """
    try:
        from services.graduation_completion_service import get_graduation_completion_service
        
        token = Token.query.filter_by(symbol=token_symbol).first()
        if not token:
            return jsonify({'success': False, 'error': f'Token {token_symbol} not found'}), 404
        
        logging.info(f"Manual graduation completion triggered for {token_symbol}")
        
        # Get the service and attempt completion
        service = get_graduation_completion_service(app=app)
        service._complete_single_graduation(token)
        
        # Refresh token from database
        db.session.refresh(token)
        
        return jsonify({
            'success': True,
            'message': f'Graduation completion attempted for {token_symbol}',
            'status': token.graduation_status,
            'is_graduated': token.is_graduated,
            'pool_address': token.liquidity_pool_address
        })
        
    except Exception as e:
        logging.error(f"Error triggering graduation completion: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Test page for graduation transfer
@app.route('/test/graduation-transfer')
def test_graduation_transfer():
    """Simple test page to send 0.001 KAS to GraduationController using connected wallet"""
    return render_template('app/test_graduation_transfer.html')

# Test page for completing KAOS graduation
@app.route('/test/complete-graduation')
def test_complete_graduation():
    """Test page to call completeGraduation() for KAOS token using connected wallet"""
    return render_template('app/test_complete_graduation.html')

# Test page for manual graduation completion via MetaMask
@app.route('/test/complete-graduation-manual')
def test_complete_graduation_manual():
    """Manual test page to call completeGraduation() via MetaMask"""
    return render_template('app/test_complete_graduation_manual.html')

# Admin KAS Recovery - Execute Recovery
@app.route('/api/admin/recover-kas', methods=['POST'])
def api_admin_recover_kas():
    """
    Execute KAS recovery from all GraduationControllers
    This endpoint calls emergencyWithdrawKAS() on each GC using the Treasury wallet
    """
    try:
        web3_service = get_web3_service()
        
        # Known GraduationControllers with KAS
        graduation_controllers = {
            'V6':  '0xBbfdF7341aaF104D259876972844EBF9795b9C4C',
            'V9':  '0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6',
            'V10': '0x7384F95729Ff5c2B2BFe4Cc101139a13A85a66e9',
            'V11': '0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0',
            'V12': '0xD7B75104f005DFC9dE004fdb97399444752d66D3',
        }
        
        # Simple ABI for emergencyWithdrawKAS()
        abi = [{
            "inputs": [],
            "name": "emergencyWithdrawKAS",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }]
        
        results = []
        total_recovered = 0
        
        for version, gc_addr in graduation_controllers.items():
            try:
                gc_checksum = Web3.to_checksum_address(gc_addr)
                
                # Check balance first
                balance_wei = web3_service.w3.eth.get_balance(gc_checksum)
                balance_kas = float(Web3.from_wei(balance_wei, 'ether'))
                
                if balance_kas <= 0:
                    logging.info(f"Skipping {version} - no balance")
                    continue
                
                logging.info(f"💰 Recovering {balance_kas} KAS from {version} ({gc_addr})")
                
                # Create contract instance
                contract = web3_service.w3.eth.contract(address=gc_checksum, abi=abi)
                
                # Build transaction
                tx = contract.functions.emergencyWithdrawKAS().build_transaction({
                    'from': web3_service.oracle_address,
                    'nonce': web3_service.w3.eth.get_transaction_count(web3_service.oracle_address),
                    'gas': 100000,
                    'gasPrice': web3_service.w3.eth.gas_price
                })
                
                # Sign transaction
                signed_tx = web3_service.w3.eth.account.sign_transaction(tx, web3_service.oracle_private_key)
                
                # Send transaction
                tx_hash = web3_service.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                tx_hash_hex = tx_hash.hex()
                
                logging.info(f"📤 Transaction sent: {tx_hash_hex}")
                
                # Wait for receipt
                receipt = web3_service.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                
                if receipt['status'] == 1:
                    logging.info(f"✅ {version} recovery successful! Block: {receipt['blockNumber']}")
                    results.append({
                        'version': version,
                        'address': gc_addr,
                        'recovered_kas': balance_kas,
                        'tx_hash': tx_hash_hex,
                        'success': True
                    })
                    total_recovered += balance_kas
                else:
                    logging.error(f"❌ {version} recovery failed - transaction reverted")
                    results.append({
                        'version': version,
                        'address': gc_addr,
                        'recovered_kas': 0,
                        'error': 'Transaction reverted',
                        'success': False
                    })
                
            except Exception as e:
                logging.error(f"Error recovering from {version}: {str(e)}")
                results.append({
                    'version': version,
                    'address': gc_addr,
                    'recovered_kas': 0,
                    'error': str(e),
                    'success': False
                })
        
        success_count = sum(1 for r in results if r.get('success', False))
        
        return jsonify({
            'success': True,
            'total_recovered_kas': total_recovered,
            'recovered_from': success_count,
            'total_attempts': len(results),
            'results': results
        })
        
    except Exception as e:
        logging.error(f"Error in recovery: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Admin KAS Recovery API
@app.route('/api/admin/recovery-info')
def api_admin_recovery_info():
    """
    Get information about locked KAS in failed graduations
    Returns list of GraduationControllers with locked KAS that can be recovered
    """
    try:
        web3_service = get_web3_service()
        
        # Known GraduationControllers
        graduation_controllers = {
            'V6':  '0xBbfdF7341aaF104D259876972844EBF9795b9C4C',
            'V9':  '0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6',
            'V10': '0x7384F95729Ff5c2B2BFe4Cc101139a13A85a66e9',
            'V11': '0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0',
            'V12': '0xD7B75104f005DFC9dE004fdb97399444752d66D3',
            'V13': '0xf04aB5deE799DDb217a03bF07fFf4dDf541dD9f1',
        }
        
        # Treasury wallet (owner of all GCs)
        treasury = '0xe281e4776FB5De20817D0bbC72B0C4b955565619'
        
        total_locked = 0
        recoverable = 0
        gc_list = []
        
        owner_selector = web3_service.w3.keccak(text='owner()')[:4].hex()
        
        for version, gc_addr in graduation_controllers.items():
            try:
                gc_checksum = Web3.to_checksum_address(gc_addr)
                
                # Get balance
                balance_wei = web3_service.w3.eth.get_balance(gc_checksum)
                balance_kas = float(Web3.from_wei(balance_wei, 'ether'))
                
                # Skip if no balance
                if balance_kas <= 0:
                    continue
                
                # Get owner
                result = web3_service.w3.eth.call({'to': gc_checksum, 'data': owner_selector})
                owner = Web3.to_checksum_address('0x' + result.hex()[-40:])
                
                total_locked += balance_kas
                
                gc_info = {
                    'version': version,
                    'address': gc_addr,
                    'balance': balance_kas,
                    'owner': owner,
                    'recoverable': owner.lower() == treasury.lower()
                }
                
                if gc_info['recoverable']:
                    recoverable += balance_kas
                    gc_list.append(gc_info)
                
            except Exception as e:
                logging.error(f"Error checking {version}: {e}")
        
        return jsonify({
            'success': True,
            'total_locked_kas': total_locked,
            'recoverable_kas': recoverable,
            'graduation_controllers': gc_list,
            'treasury_address': treasury
        })
        
    except Exception as e:
        logging.error(f"Error getting recovery info: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Initialize database when app starts
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
