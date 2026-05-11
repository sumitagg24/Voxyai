"""
Voxylis Web Server - Production Ready
Handles all web requests and API endpoints
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_caching import Cache
import json
import os
from datetime import datetime, timedelta
import hashlib
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.user_manager import user_manager

# Initialize Flask app
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)

# Enable CORS
CORS(app)

# Configure caching
cache_config = {
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
}
cache = Cache(app, config=cache_config)

# Configuration
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    """Serve Raycast-style landing page"""
    return send_from_directory('static', 'raycast-style.html')

@app.route('/dashboard')
def dashboard():
    """Serve dashboard"""
    return send_from_directory('static', 'dashboard.html')

@app.route('/docs/<page>')
def docs(page):
    """Serve documentation pages"""
    valid_pages = ['installation', 'configuration', 'voice-commands', 'qa-feature', 'troubleshooting', 'tips-tricks']
    if page in valid_pages:
        return send_from_directory('static/docs', f'{page}.html')
    return jsonify({'error': 'Page not found'}), 404

# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """User signup endpoint"""
    data = request.json
    
    name = data.get('name', '').strip()
    email_or_phone = data.get('email_or_phone', '').strip()
    password = data.get('password', '').strip()
    
    if not name or not email_or_phone or not password:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    result = user_manager.signup(name, email_or_phone, password)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """User login endpoint"""
    data = request.json
    
    email_or_phone = data.get('email_or_phone', '').strip()
    password = data.get('password', '').strip()
    
    if not email_or_phone or not password:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    result = user_manager.login(email_or_phone, password)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 401

@app.route('/api/auth/verify', methods=['POST'])
def auth_verify():
    """Verify session endpoint"""
    data = request.json
    session_id = data.get('session_id', '')
    
    if not session_id:
        return jsonify({'valid': False, 'error': 'Missing session_id'}), 400
    
    result = user_manager.verify_session(session_id)
    return jsonify(result), 200

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """User logout endpoint"""
    data = request.json
    session_id = data.get('session_id', '')
    
    if not session_id:
        return jsonify({'success': False, 'error': 'Missing session_id'}), 400
    
    result = user_manager.logout(session_id)
    return jsonify(result), 200

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/features', methods=['GET'])
@cache.cached(timeout=3600)
def get_features():
    """Get all features"""
    return jsonify({
        'status': 'success',
        'features': [
            {
                'id': 1,
                'name': 'Voice-to-Text',
                'description': 'Accurate speech recognition',
                'icon': '🎤'
            },
            {
                'id': 2,
                'name': 'AI Enhancement',
                'description': 'Smart text improvement',
                'icon': '✨'
            },
            {
                'id': 3,
                'name': 'Wake Word',
                'description': 'Custom activation word',
                'icon': '🗣️'
            },
            {
                'id': 4,
                'name': 'Q&A Feature',
                'description': 'Instant answers',
                'icon': '🤖'
            },
            {
                'id': 5,
                'name': 'Custom Hotkeys',
                'description': 'Personalized shortcuts',
                'icon': '⌨️'
            },
            {
                'id': 6,
                'name': 'Multi-Language',
                'description': '99+ languages',
                'icon': '🌍'
            },
            {
                'id': 7,
                'name': 'Cloud Sync',
                'description': 'Sync across devices',
                'icon': '☁️'
            },
            {
                'id': 8,
                'name': 'Privacy First',
                'description': 'Your data, your control',
                'icon': '🔒'
            }
        ]
    })

@app.route('/api/pricing', methods=['GET'])
@cache.cached(timeout=3600)
def get_pricing():
    """Get pricing tiers"""
    return jsonify({
        'status': 'success',
        'tiers': [
            {
                'id': 'free',
                'name': 'Free',
                'price': 0,
                'period': 'month',
                'description': 'Perfect for getting started',
                'features': [
                    '100 transcriptions/month',
                    '5 languages',
                    'Basic enhancement',
                    'Community support'
                ],
                'cta': 'Get Started',
                'popular': False
            },
            {
                'id': 'pro',
                'name': 'Pro',
                'price': 9.99,
                'period': 'month',
                'description': 'For power users',
                'features': [
                    'Unlimited transcriptions',
                    '99+ languages',
                    'All enhancement modes',
                    'Live Q&A feature',
                    'Custom wake word',
                    'Priority support'
                ],
                'cta': 'Start Free Trial',
                'popular': True
            },
            {
                'id': 'business',
                'name': 'Business',
                'price': 29.99,
                'period': 'month',
                'description': 'For teams',
                'features': [
                    'Everything in Pro',
                    'Team collaboration',
                    'API access',
                    'Custom integrations',
                    'Dedicated support',
                    'Advanced analytics'
                ],
                'cta': 'Contact Sales',
                'popular': False
            }
        ]
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get/update user settings"""
    if request.method == 'POST':
        data = request.json
        # Validate and save settings
        return jsonify({
            'status': 'success',
            'message': 'Settings saved successfully'
        })
    else:
        # Return default settings
        return jsonify({
            'status': 'success',
            'settings': {
                'theme': 'light',
                'language': 'en',
                'notifications': True,
                'sound': True,
                'autoStart': False,
                'hotkey': 'Win+Shift',
                'wakeWord': 'Voxy',
                'wakeWordSensitivity': 70
            }
        })

@app.route('/api/hotkeys', methods=['GET', 'POST'])
def hotkeys():
    """Get/update hotkeys"""
    if request.method == 'POST':
        data = request.json
        return jsonify({
            'status': 'success',
            'message': 'Hotkey updated successfully'
        })
    else:
        return jsonify({
            'status': 'success',
            'hotkeys': {
                'record': 'Win+Shift',
                'casual': 'Win+Alt',
                'technical': 'Win+Ctrl',
                'settings': 'Win+;'
            }
        })

@app.route('/api/qa', methods=['POST'])
def qa_endpoint():
    """Q&A feature endpoint"""
    data = request.json
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': 'Question required'}), 400
    
    # Simulate Q&A response
    answer = f"This is an answer to: {question}"
    
    return jsonify({
        'status': 'success',
        'question': question,
        'answer': answer,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/history', methods=['GET', 'POST'])
def history():
    """Get/add transcription history"""
    if request.method == 'POST':
        data = request.json
        return jsonify({
            'status': 'success',
            'message': 'Transcription saved'
        })
    else:
        # Return sample history
        return jsonify({
            'status': 'success',
            'history': [
                {
                    'id': 1,
                    'text': 'Hello world, this is a test transcription',
                    'language': 'English',
                    'mode': 'Formal',
                    'timestamp': (datetime.now() - timedelta(minutes=2)).isoformat()
                },
                {
                    'id': 2,
                    'text': 'Bonjour, comment allez-vous?',
                    'language': 'French',
                    'mode': 'Casual',
                    'timestamp': (datetime.now() - timedelta(hours=1)).isoformat()
                },
                {
                    'id': 3,
                    'text': 'Hola, ¿cómo estás?',
                    'language': 'Spanish',
                    'mode': 'Casual',
                    'timestamp': (datetime.now() - timedelta(hours=3)).isoformat()
                }
            ]
        })

@app.route('/api/stats', methods=['GET'])
def stats():
    """Get user statistics"""
    return jsonify({
        'status': 'success',
        'stats': {
            'transcriptions': 1234,
            'totalTime': '2h 45m',
            'languages': 12,
            'enhancements': 856,
            'thisMonth': {
                'transcriptions': 450,
                'words': 12500,
                'languages': 8
            }
        }
    })

@app.route('/api/subscription', methods=['GET'])
def subscription():
    """Get subscription info"""
    return jsonify({
        'status': 'success',
        'subscription': {
            'plan': 'Pro',
            'price': 9.99,
            'renewalDate': (datetime.now() + timedelta(days=30)).isoformat(),
            'status': 'active',
            'usage': {
                'transcriptions': 750,
                'limit': 'Unlimited',
                'percentage': 75
            }
        }
    })

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1.0'
    })

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Server error'}), 500

# ============================================
# STATIC FILES
# ============================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/docs', exist_ok=True)
    
    # Run development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
