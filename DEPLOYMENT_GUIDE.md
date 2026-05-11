# 🚀 Voxylis - Deployment Guide

Production deployment guide for Voxylis.

---

## 📋 Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Documentation complete
- [ ] API keys configured
- [ ] Database migrations done
- [ ] Environment variables set
- [ ] SSL certificates ready
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Support documentation ready

---

## 🖥️ Server Requirements

### Minimum
- 2 CPU cores
- 4GB RAM
- 20GB disk space
- Ubuntu 18.04 LTS or later

### Recommended
- 4 CPU cores
- 8GB RAM
- 50GB disk space
- Ubuntu 20.04 LTS or later

---

## 🔧 Installation

### 1. Install Dependencies

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and pip
sudo apt-get install -y python3 python3-pip python3-venv

# Install system dependencies
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    portaudio19-dev \
    libportaudio2

# Install Nginx (web server)
sudo apt-get install -y nginx

# Install Supervisor (process manager)
sudo apt-get install -y supervisor
```

### 2. Clone Repository

```bash
# Create app directory
sudo mkdir -p /opt/voxylis
cd /opt/voxylis

# Clone repository
sudo git clone https://github.com/voxylis/voxylis.git .

# Set permissions
sudo chown -R $USER:$USER /opt/voxylis
```

### 3. Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env

# Set permissions
chmod 600 .env
```

### 5. Create Directories

```bash
# Create required directories
mkdir -p logs
mkdir -p config
mkdir -p data

# Set permissions
chmod 755 logs config data
```

---

## 🌐 Nginx Configuration

### 1. Create Nginx Config

```bash
sudo nano /etc/nginx/sites-available/voxylis
```

### 2. Add Configuration

```nginx
upstream voxylis {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logging
    access_log /var/log/nginx/voxylis_access.log;
    error_log /var/log/nginx/voxylis_error.log;

    # Proxy settings
    location / {
        proxy_pass http://voxylis;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Static files
    location /static/ {
        alias /opt/voxylis/web/static/;
        expires 30d;
    }

    # API endpoints
    location /api/ {
        proxy_pass http://voxylis;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 3. Enable Site

```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/voxylis /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

---

## 🔐 SSL Certificates

### Using Let's Encrypt

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --nginx -d your-domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

---

## 👁️ Process Management with Supervisor

### 1. Create Supervisor Config

```bash
sudo nano /etc/supervisor/conf.d/voxylis.conf
```

### 2. Add Configuration

```ini
[program:voxylis]
directory=/opt/voxylis
command=/opt/voxylis/venv/bin/python start_voxylis.py
user=voxylis
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/opt/voxylis/logs/supervisor.log
environment=PATH="/opt/voxylis/venv/bin",FLASK_ENV="production"
```

### 3. Start Service

```bash
# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Start Voxylis
sudo supervisorctl start voxylis

# Check status
sudo supervisorctl status voxylis
```

---

## 📊 Monitoring

### 1. Install Monitoring Tools

```bash
# Install htop
sudo apt-get install -y htop

# Install Prometheus (optional)
sudo apt-get install -y prometheus

# Install Grafana (optional)
sudo apt-get install -y grafana-server
```

### 2. Monitor Application

```bash
# Check process status
sudo supervisorctl status voxylis

# View logs
tail -f /opt/voxylis/logs/supervisor.log

# Monitor resources
htop
```

### 3. Set Up Alerts

```bash
# Create alert script
nano /opt/voxylis/scripts/check_health.sh

# Add to crontab
crontab -e
# Add: */5 * * * * /opt/voxylis/scripts/check_health.sh
```

---

## 🔄 Backup Strategy

### 1. Automated Backups

```bash
# Create backup script
sudo nano /opt/voxylis/scripts/backup.sh

#!/bin/bash
BACKUP_DIR="/backups/voxylis"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
tar -czf $BACKUP_DIR/voxylis_$DATE.tar.gz \
    /opt/voxylis/config \
    /opt/voxylis/logs \
    /opt/voxylis/data

# Keep only last 30 days
find $BACKUP_DIR -name "voxylis_*.tar.gz" -mtime +30 -delete
```

### 2. Schedule Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/voxylis/scripts/backup.sh
```

### 3. Remote Backups

```bash
# Backup to S3
aws s3 sync /backups/voxylis s3://your-bucket/voxylis-backups/

# Or use rsync
rsync -avz /backups/voxylis/ backup-server:/backups/voxylis/
```

---

## 🚀 Deployment

### 1. Deploy Application

```bash
# Pull latest code
cd /opt/voxylis
git pull origin main

# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations (if applicable)
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput
```

### 2. Restart Services

```bash
# Restart Voxylis
sudo supervisorctl restart voxylis

# Restart Nginx
sudo systemctl restart nginx

# Check status
sudo supervisorctl status voxylis
```

### 3. Verify Deployment

```bash
# Check health endpoint
curl https://your-domain.com/api/health

# Check logs
tail -f /opt/voxylis/logs/supervisor.log

# Monitor resources
htop
```

---

## 🔍 Health Checks

### 1. Application Health

```bash
# Check if app is running
curl http://localhost:5000/api/health

# Expected response:
# {"status": "healthy", "version": "2.1.0"}
```

### 2. Database Health

```bash
# Check database connection
python -c "from app import db; db.session.execute('SELECT 1')"
```

### 3. API Health

```bash
# Test API endpoints
curl http://localhost:5000/api/features
curl http://localhost:5000/api/pricing
curl http://localhost:5000/api/settings
```

---

## 📈 Scaling

### 1. Load Balancing

```bash
# Install HAProxy
sudo apt-get install -y haproxy

# Configure HAProxy
sudo nano /etc/haproxy/haproxy.cfg

# Add backend servers
backend voxylis_backend
    balance roundrobin
    server voxylis1 127.0.0.1:5000
    server voxylis2 127.0.0.1:5001
    server voxylis3 127.0.0.1:5002
```

### 2. Multiple Instances

```bash
# Run multiple instances
for i in {1..3}; do
    PORT=$((5000 + i - 1))
    FLASK_ENV=production python -m gunicorn \
        --bind 127.0.0.1:$PORT \
        --workers 4 \
        web.app:app &
done
```

### 3. Database Optimization

```bash
# Create indexes
python manage.py shell
>>> from app import db
>>> db.create_all()
>>> # Add indexes as needed
```

---

## 🔐 Security

### 1. Firewall Configuration

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

### 2. Security Headers

```nginx
# Add to Nginx config
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self'" always;
```

### 3. API Security

```python
# In Flask app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
```

---

## 📝 Logging

### 1. Configure Logging

```python
# In app.py
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/voxylis.log',
    maxBytes=10485760,  # 10MB
    backupCount=10
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s'
))
app.logger.addHandler(handler)
```

### 2. View Logs

```bash
# Real-time logs
tail -f /opt/voxylis/logs/voxylis.log

# Search logs
grep "ERROR" /opt/voxylis/logs/voxylis.log

# Analyze logs
cat /opt/voxylis/logs/voxylis.log | grep "ERROR" | wc -l
```

---

## 🔄 Updates

### 1. Update Application

```bash
# Pull latest code
cd /opt/voxylis
git pull origin main

# Install new dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart application
sudo supervisorctl restart voxylis
```

### 2. Database Migrations

```bash
# Run migrations
python manage.py migrate

# Rollback if needed
python manage.py migrate --rollback
```

---

## 🆘 Troubleshooting

### Issue: Application won't start
```bash
# Check logs
tail -f /opt/voxylis/logs/supervisor.log

# Check Python errors
python start_voxylis.py

# Check port availability
netstat -tlnp | grep 5000
```

### Issue: High CPU usage
```bash
# Check processes
top

# Check for memory leaks
ps aux | grep python

# Restart application
sudo supervisorctl restart voxylis
```

### Issue: Database connection error
```bash
# Check database
python manage.py shell
>>> from app import db
>>> db.session.execute('SELECT 1')

# Recreate database
python manage.py db upgrade
```

---

## 📞 Support

For deployment issues:
- Email: deploy@voxylis.com
- Discord: discord.gg/voxylis
- GitHub: github.com/voxylis/voxylis

---

**Happy deploying! 🚀**

