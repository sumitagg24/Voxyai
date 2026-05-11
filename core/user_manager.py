"""
Voxylis - User Manager
Handles user authentication and storage
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path

class UserManager:
    """Manages user authentication and storage"""
    
    def __init__(self):
        self.users_file = Path('config/users.json')
        self.sessions_file = Path('config/sessions.json')
        self.ensure_files_exist()
    
    def ensure_files_exist(self):
        """Ensure user and session files exist"""
        os.makedirs('config', exist_ok=True)
        
        if not self.users_file.exists():
            self.users_file.write_text(json.dumps({}, indent=2))
        
        if not self.sessions_file.exists():
            self.sessions_file.write_text(json.dumps({}, indent=2))
    
    def hash_password(self, password):
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def load_users(self):
        """Load users from file"""
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_users(self, users):
        """Save users to file"""
        with open(self.users_file, 'w') as f:
            json.dump(users, f, indent=2)
    
    def load_sessions(self):
        """Load sessions from file"""
        try:
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_sessions(self, sessions):
        """Save sessions to file"""
        with open(self.sessions_file, 'w') as f:
            json.dump(sessions, f, indent=2)
    
    def signup(self, name, email_or_phone, password):
        """Create new user account"""
        users = self.load_users()
        
        # Check if user already exists
        if email_or_phone in users:
            return {'success': False, 'error': 'User already exists'}
        
        # Validate inputs
        if not name or len(name.strip()) < 2:
            return {'success': False, 'error': 'Name must be at least 2 characters'}
        
        if not password or len(password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters'}
        
        # Create user
        user_data = {
            'name': name,
            'password': self.hash_password(password),
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'stats': {
                'transcriptions': 0,
                'total_time': 0,
                'languages': []
            }
        }
        
        users[email_or_phone] = user_data
        self.save_users(users)
        
        return {'success': True, 'user': email_or_phone, 'name': name}
    
    def login(self, email_or_phone, password):
        """Authenticate user"""
        users = self.load_users()
        
        # Check if user exists
        if email_or_phone not in users:
            return {'success': False, 'error': 'User not found'}
        
        user = users[email_or_phone]
        
        # Verify password
        if user['password'] != self.hash_password(password):
            return {'success': False, 'error': 'Invalid password'}
        
        # Update last login
        user['last_login'] = datetime.now().isoformat()
        self.save_users(users)
        
        # Create session
        session_id = hashlib.sha256(f"{email_or_phone}{datetime.now().isoformat()}".encode()).hexdigest()
        sessions = self.load_sessions()
        sessions[session_id] = {
            'user': email_or_phone,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now().timestamp() + 86400 * 30)  # 30 days
        }
        self.save_sessions(sessions)
        
        return {
            'success': True,
            'user': email_or_phone,
            'name': user['name'],
            'session_id': session_id
        }
    
    def verify_session(self, session_id):
        """Verify if session is valid"""
        sessions = self.load_sessions()
        
        if session_id not in sessions:
            return {'valid': False}
        
        session = sessions[session_id]
        
        # Check if session expired
        if datetime.now().timestamp() > session['expires_at']:
            del sessions[session_id]
            self.save_sessions(sessions)
            return {'valid': False}
        
        users = self.load_users()
        user = users.get(session['user'], {})
        
        return {
            'valid': True,
            'user': session['user'],
            'name': user.get('name', 'User')
        }
    
    def logout(self, session_id):
        """Logout user"""
        sessions = self.load_sessions()
        if session_id in sessions:
            del sessions[session_id]
            self.save_sessions(sessions)
        return {'success': True}
    
    def get_user_stats(self, email_or_phone):
        """Get user statistics"""
        users = self.load_users()
        
        if email_or_phone not in users:
            return None
        
        return users[email_or_phone].get('stats', {})
    
    def update_user_stats(self, email_or_phone, stats):
        """Update user statistics"""
        users = self.load_users()
        
        if email_or_phone in users:
            users[email_or_phone]['stats'] = stats
            self.save_users(users)
            return True
        
        return False

# Global user manager instance
user_manager = UserManager()
