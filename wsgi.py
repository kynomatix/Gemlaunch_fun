#!/usr/bin/env python
"""
WSGI entry point for production deployment
"""
import os
from app import app

# Set production configurations
app.config['ENV'] = 'production'
app.config['DEBUG'] = False

if __name__ == "__main__":
    # For production, use gunicorn instead of the development server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)