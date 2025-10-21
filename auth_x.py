"""
X (Twitter) OAuth 2.0 verification for user profiles
Allows users to verify their X accounts to prove ownership of their handle
"""
import os
import secrets
from datetime import datetime, timezone
from flask import Blueprint, request, redirect, url_for, session, flash, jsonify
from authlib.integrations.flask_client import OAuth
from models import db, User, UserProfile
from functools import wraps

# Create Blueprint
auth_x_bp = Blueprint('auth_x', __name__, url_prefix='/auth/twitter')

# Initialize OAuth
oauth = OAuth()

def init_oauth(app):
    """Initialize OAuth client with app"""
    oauth.init_app(app)
    
    # Register X (Twitter) OAuth 2.0 client
    oauth.register(
        name='twitter',
        client_id=os.environ.get('TWITTER_CLIENT_ID'),
        client_secret=os.environ.get('TWITTER_CLIENT_SECRET'),
        authorize_url='https://twitter.com/i/oauth2/authorize',
        authorize_params={
            'code_challenge_method': 'S256',
        },
        access_token_url='https://api.twitter.com/2/oauth2/token',
        access_token_params=None,
        client_kwargs={
            'scope': 'tweet.read users.read',
            'token_endpoint_auth_method': 'client_secret_post',
        },
        server_metadata_url='https://api.twitter.com/.well-known/oauth-authorization-server',
    )
    
    return oauth.twitter

def login_required(f):
    """Decorator to ensure user is logged in via wallet"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please connect your wallet first', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@auth_x_bp.route('/connect')
@login_required
def connect():
    """Initiate X OAuth 2.0 flow"""
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Store user_id in session for callback
    session['oauth_user_id'] = session.get('user_id')
    
    # Generate PKCE code challenge
    redirect_uri = url_for('auth_x.callback', _external=True, _scheme='https')
    
    return oauth.twitter.authorize_redirect(
        redirect_uri,
        state=state,
        code_challenge_method='S256'
    )

@auth_x_bp.route('/callback')
def callback():
    """Handle OAuth callback from X"""
    
    # Verify state to prevent CSRF
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('profile'))
    
    # Clear state from session
    session.pop('oauth_state', None)
    
    # Get user_id from session
    user_id = session.get('oauth_user_id')
    if not user_id:
        flash('Session expired. Please try again.', 'error')
        return redirect(url_for('profile'))
    
    try:
        # Exchange code for access token
        token = oauth.twitter.authorize_access_token()
        
        # Get user info from X API
        resp = oauth.twitter.get(
            'https://api.twitter.com/2/users/me',
            token=token
        )
        user_info = resp.json()
        
        if 'data' not in user_info:
            flash('Failed to get X user information. Please try again.', 'error')
            return redirect(url_for('profile'))
        
        x_user_data = user_info['data']
        x_user_id = x_user_data['id']
        x_username = x_user_data['username']
        
        # Check if this X account is already verified by another user
        existing_profile = UserProfile.query.filter_by(
            twitter_user_id=x_user_id,
            is_twitter_verified=True
        ).first()
        
        if existing_profile and existing_profile.user_id != user_id:
            flash(f'This X account (@{x_username}) is already verified by another wallet address.', 'error')
            return redirect(url_for('profile'))
        
        # Get current user
        user = User.query.get(user_id)
        if not user:
            flash('User not found. Please connect your wallet again.', 'error')
            return redirect(url_for('home'))
        
        # Get or create UserProfile
        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)
        
        # Update profile with verified X data
        profile.twitter_handle = x_username
        profile.twitter_user_id = x_user_id
        profile.is_twitter_verified = True
        profile.twitter_verified_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        flash(f'Successfully verified X account @{x_username}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'X verification failed: {str(e)}', 'error')
    
    return redirect(url_for('profile'))

@auth_x_bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect():
    """Remove X verification from user profile"""
    
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.is_twitter_verified:
        return jsonify({'success': False, 'error': 'X account not verified'}), 400
    
    # Clear X verification data
    x_handle = profile.twitter_handle
    profile.twitter_handle = None
    profile.twitter_user_id = None
    profile.is_twitter_verified = False
    profile.twitter_verified_at = None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'X account @{x_handle} disconnected successfully'
    })

@auth_x_bp.route('/status')
@login_required
def status():
    """Get current X verification status for logged-in user"""
    
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'verified': False})
    
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    
    if not profile or not profile.is_twitter_verified:
        return jsonify({'verified': False})
    
    return jsonify({
        'verified': True,
        'username': profile.twitter_handle,
        'verified_at': profile.twitter_verified_at.isoformat() if profile.twitter_verified_at else None
    })
