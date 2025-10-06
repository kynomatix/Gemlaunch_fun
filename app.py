import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
from sqlalchemy.orm import joinedload, selectinload
from models import db, User, Token, Trade, Holding, Achievement, UserAchievement, UserProfile, ConnectedWallet, Referral, Activity, LinkedWallet, WalletVerificationChallenge, TransferRequest
from models_extended import ChatMessage, Poll, PollOption, PollVote, MessageReaction, TokenSettings, TokenLeaderboard
from services import TokenService
from services.achievement_service import evaluate_user_achievements

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
        
        # Clear all existing session data before creating new session
        session.clear()
        
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

# Multi-wallet linking API
@app.route('/api/wallet/request-link', methods=['POST'])
def request_wallet_link():
    """Request to link a secondary wallet to user account"""
    import re
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    wallet_label = data.get('wallet_label', '')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    wallet_address = wallet_address.strip()
    
    if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
        return jsonify({'error': 'Invalid wallet address format. Must be 0x followed by 40 hexadecimal characters.'}), 400
    
    wallet_address_lower = wallet_address.lower()
    
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
    import re
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User authentication required'}), 401
    
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    wallet_address = wallet_address.strip()
    
    if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
        return jsonify({'error': 'Invalid wallet address format. Must be 0x followed by 40 hexadecimal characters.'}), 400
    
    wallet_address_lower = wallet_address.lower()
    
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
        return redirect(url_for('app_marketplace'))
    
    # Backfill cached stats if needed
    if not user.total_trades_count or user.total_trades_count == 0:
        user.total_trades_count = Trade.query.filter_by(user_id=user.id, tx_status='confirmed').count()
    if not user.total_graduated_tokens or user.total_graduated_tokens == 0:
        user.total_graduated_tokens = Token.query.filter_by(creator_id=user.id, is_graduated=True).count()
    if not user.total_tokens_created or user.total_tokens_created == 0:
        user.total_tokens_created = Token.query.filter_by(creator_id=user.id).count()
    if not user.total_trading_volume or user.total_trading_volume == 0:
        total_volume = db.session.query(db.func.sum(Trade.kas_amount)).filter(
            Trade.user_id == user.id,
            Trade.tx_status == 'confirmed'
        ).scalar()
        user.total_trading_volume = total_volume or 0
    if not user.total_messages_sent or user.total_messages_sent == 0:
        try:
            user.total_messages_sent = ChatMessage.query.filter_by(user_id=user.id).count()
        except Exception as e:
            logging.warning(f"Could not backfill total_messages_sent: {e}")
            user.total_messages_sent = 0
    # Save the backfill
    db.session.commit()
    
    # Evaluate and award achievements
    achievement_progress = evaluate_user_achievements(user.id)
    
    # Get user's created tokens and holdings with eager loading
    created_tokens = Token.query.filter_by(creator_id=user.id).all()
    holdings = Holding.query.options(
        joinedload(Holding.token)
    ).filter_by(user_id=user.id).all()
    
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
                         referral=referral)

@app.route('/app/create', methods=['GET', 'POST'])
def create_token():
    """Token creation page and form handler"""
    user = get_current_user()
    if not user:
        return redirect(url_for('app_marketplace'))
    
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
    
    # Show all tokens with eager loading of creator information
    tokens = Token.query.options(
        joinedload(Token.creator)
    ).order_by(Token.created_at.desc()).all()
    
    # Add is_pro flag to each token for the template
    for token in tokens:
        token.is_pro = TokenService.is_pro_token(token)
    
    return render_template('app/marketplace.html', tokens=tokens, user=user, now=datetime.now(timezone.utc))

@app.route('/app/token/<contract_address>')
def token_detail(contract_address):
    """Individual token detail page"""
    token = Token.query.options(
        joinedload(Token.creator),
        joinedload(Token.settings)  # Load token settings
    ).filter_by(contract_address=contract_address).first_or_404()
    
    # Get recent trades with eager loading of user information
    recent_trades = Trade.query.options(
        joinedload(Trade.user)
    ).filter_by(token_id=token.id, tx_status='confirmed').order_by(Trade.confirmed_at.desc()).limit(10).all()
    
    # Get user's holding if connected
    user_holding = None
    user = get_current_user()
    if user:
        user_holding = Holding.query.filter_by(user_id=user.id, token_id=token.id).first()
    
    # Check if current user is the token owner
    is_owner = False
    if user and token.creator:
        is_owner = user.wallet_address.lower() == token.creator.wallet_address.lower()
    
    # Use TokenService to determine if token is pro
    is_pro_token = TokenService.is_pro_token(token)
    
    # Ensure token has settings using service
    token.settings = TokenService.ensure_token_settings(token)
    
    return render_template('app/token_detail.html', 
                         token=token, 
                         recent_trades=recent_trades,
                         user_holding=user_holding,
                         user=user,
                         is_owner=is_owner,
                         is_pro_token=is_pro_token)

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
        
        # Increment achievement counter
        user.total_messages_sent = (user.total_messages_sent or 0) + 1
        db.session.commit()
        
        # If this is a reply, load the reply_to information
        response_msg = {
            'id': message.id,
            'user': (user.profile.username if user.profile and user.profile.username else user.display_name) or user.wallet_address[-6:],
            'wallet': user.wallet_address,
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
@require_wallet_connection
def token_polls(contract_address):
    """Get or create polls for a token"""
    from datetime import datetime, timedelta, timezone
    
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    user = get_current_user()
    
    if request.method == 'GET':
        # Get active polls with creator profile
        polls = Poll.query.options(
            joinedload(Poll.creator).joinedload(User.profile)
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
    
    return jsonify({'success': True, 'new_vote_count': option.vote_count})

@app.route('/api/token/<contract_address>/holdings', methods=['GET'])
def get_token_holdings(contract_address):
    """Get user's token holdings for verification"""
    wallet_address = request.headers.get('X-Wallet-Address')
    
    if not wallet_address:
        return jsonify({'error': 'Wallet address required'}), 400
    
    # Get token
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Get user by wallet
    user = User.query.filter_by(wallet_address=wallet_address.lower()).first()
    
    if not user:
        return jsonify({'balance': 0, 'isHolder': False})
    
    # Get user's holding for this token
    holding = Holding.query.filter_by(user_id=user.id, token_id=token.id).first()
    
    if not holding:
        return jsonify({'balance': 0, 'isHolder': False})
    
    # Return actual token balance
    balance = float(holding.token_amount) if holding.token_amount else 0
    
    return jsonify({
        'balance': balance,
        'isHolder': balance > 0,
        'wallet': wallet_address
    })

@app.route('/api/token/<contract_address>/spotlight', methods=['GET', 'POST'])
@require_wallet_connection
def token_spotlight(contract_address):
    """Get or create spotlight messages - TOKEN GATED, not token cost!"""
    from datetime import datetime, timedelta, timezone
    
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    user = get_current_user()
    
    if request.method == 'GET':
        # Get active spotlight messages (only those less than 1 hour old)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        spotlights = ChatMessage.query.options(
            joinedload(ChatMessage.user).joinedload(User.profile)
        ).filter(
            ChatMessage.token_id == token.id,
            ChatMessage.is_pinned == True,
            ChatMessage.is_deleted == False,
            ChatMessage.created_at >= one_hour_ago  # Only show spotlights less than 1 hour old
        ).order_by(ChatMessage.created_at.desc()).limit(5).all()
        
        spotlight_list = []
        for msg in spotlights:
            # Calculate when this message expires (1 hour after creation)
            expires_at = msg.created_at + timedelta(hours=1)
            # Convert to Unix timestamp in milliseconds for JavaScript
            expires_at_ms = int(expires_at.timestamp() * 1000)
            spotlight_list.append({
                'id': msg.id,
                'user': (msg.user.profile.username if msg.user.profile and msg.user.profile.username else msg.user.display_name) or msg.user.wallet_address[-6:],
                'message': msg.content,
                'created_at': msg.created_at.isoformat(),
                'expires_at_ms': expires_at_ms  # Send as milliseconds timestamp
            })
        
        return jsonify({'spotlights': spotlight_list})
    
    elif request.method == 'POST':
        data = request.get_json()
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get token settings for minimum tokens required
        settings = TokenSettings.query.filter_by(token_id=token.id).first()
        min_tokens_for_spotlight = 500  # Default
        if settings:
            min_tokens_for_spotlight = settings.min_tokens_for_spotlight or 500
        
        # VERIFY USER ACTUALLY HOLDS ENOUGH TOKENS (TOKEN GATE!)
        holding = Holding.query.filter_by(user_id=user.id, token_id=token.id).first()
        
        if not holding:
            return jsonify({'error': f'You need to hold at least {min_tokens_for_spotlight} {token.symbol} tokens to create spotlight messages'}), 403
        
        user_balance = float(holding.token_amount) if holding.token_amount else 0
        
        if user_balance < min_tokens_for_spotlight:
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

@app.route('/api/token/<contract_address>/airdrop/create', methods=['POST'])
@require_wallet_connection
def create_airdrop(contract_address):
    """Create an airdrop campaign for a PRO token"""
    from datetime import datetime, timezone
    
    user = get_current_user()
    token = Token.query.filter_by(contract_address=contract_address).first_or_404()
    
    # Verify user is the token creator
    if not token.creator or user.wallet_address.lower() != token.creator.wallet_address.lower():
        return jsonify({'error': 'Only the token creator can create airdrops'}), 403
    
    # Get request data
    data = request.get_json()
    airdrop_type = data.get('type')
    total_amount = int(data.get('amount', 0))
    parameters = data.get('parameters', {})
    
    # Validate airdrop type
    valid_types = ['random_raffle', 'top_contributors', 'active_chatters', 'token_holders', 'early_supporters']
    if airdrop_type not in valid_types:
        return jsonify({'error': 'Invalid airdrop type'}), 400
    
    # Validate amount
    if total_amount <= 0:
        return jsonify({'error': 'Invalid airdrop amount'}), 400
    
    # Calculate available airdrop amount
    total_airdrop_allocation = float(token.reserved_tokens or 0) * (float(token.airdrops_allocation) / 100.0)
    created_at = token.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_since_creation = (datetime.now(timezone.utc) - created_at).days
    unlocked_percentage = min(days_since_creation * 5, 100)
    unlocked_amount = total_airdrop_allocation * (unlocked_percentage / 100.0)
    already_airdropped = float(token.total_airdropped or 0)
    available_amount = max(unlocked_amount - already_airdropped, 0)
    
    # Check if amount is available
    if total_amount > available_amount:
        return jsonify({
            'error': f'Insufficient airdrop allocation. Available: {int(available_amount)} {token.symbol}'
        }), 400
    
    # Create airdrop record
    airdrop = Airdrop(
        token_id=token.id,
        creator_id=user.id,
        airdrop_type=airdrop_type,
        total_amount=total_amount,
        parameters=parameters,
        status='pending'  # Will be processed by smart contract
    )
    
    db.session.add(airdrop)
    
    # Update total_airdropped on token (reserve the amount)
    token.total_airdropped = (token.total_airdropped or 0) + total_amount
    
    try:
        db.session.commit()
        
        return jsonify({
            'success': True,
            'airdrop_id': airdrop.id,
            'message': f'Airdrop created successfully! {total_amount} {token.symbol} reserved for distribution.',
            'status': 'pending'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create airdrop: {str(e)}'}), 500

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
            elif profile.profile_picture_url:
                # Fall back to legacy base64 URL
                avatar_url = profile.profile_picture_url
        
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
        return redirect(url_for('app_marketplace'))
    
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
                        'twitter': 'https://x.com/lasereyeskaspa'
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
                    token.trade_count = 42  # Mock trades
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

# Initialize database when app starts
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
