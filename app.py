import os
from flask import Flask, render_template, jsonify

# Create Flask app with proper template configuration
app = Flask(__name__, template_folder='templates', static_folder='static')

# Production-ready configuration
app.secret_key = os.environ.get("SESSION_SECRET", "your-production-secret-key-here")

# Security configurations for production
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# Configure Jinja2 to use the same syntax as EJS templates
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/docs')
def docs():
    return render_template('docs.html')

@app.route('/pitch-deck')
def pitch_deck():
    return render_template('pitch-deck.html')

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)