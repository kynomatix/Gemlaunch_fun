import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
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

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('app_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('app_dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('app_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        if password and len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('auth/register.html')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            return render_template('auth/register.html')
        
        # Create new user
        user = User()
        user.username = username
        user.email = email
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# App routes
@app.route('/app')
@login_required
def app_dashboard():
    """Main app dashboard"""
    # Get user's tokens and holdings
    created_tokens = Token.query.filter_by(creator_id=current_user.id).order_by(Token.created_at.desc()).all()
    holdings = Holding.query.filter_by(user_id=current_user.id).filter(Holding.token_amount > 0).all()
    
    return render_template('app/dashboard.html', 
                         created_tokens=created_tokens, 
                         holdings=holdings,
                         user=current_user)

@app.route('/app/create')
@login_required
def create_token():
    """Token creation page"""
    return render_template('app/create_token.html')

@app.route('/app/tokens')
def token_marketplace():
    """Token marketplace - public page"""
    tokens = Token.query.filter_by(deployment_status='deployed').order_by(Token.created_at.desc()).all()
    return render_template('app/marketplace.html', tokens=tokens)

@app.route('/app/token/<int:token_id>')
def token_detail(token_id):
    """Individual token detail page"""
    token = Token.query.get_or_404(token_id)
    
    # Get recent trades
    recent_trades = Trade.query.filter_by(token_id=token_id, tx_status='confirmed').order_by(Trade.confirmed_at.desc()).limit(10).all()
    
    # Get user's holding if logged in
    user_holding = None
    if current_user.is_authenticated:
        user_holding = Holding.query.filter_by(user_id=current_user.id, token_id=token_id).first()
    
    return render_template('app/token_detail.html', 
                         token=token, 
                         recent_trades=recent_trades,
                         user_holding=user_holding)

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
