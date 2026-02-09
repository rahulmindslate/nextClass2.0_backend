from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# In-memory OTP storage (use Redis in production)
otp_storage = {}

# Email configuration - Update these with your email credentials
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER', '')  # Your email
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')  # App password for Gmail
EMAIL_FROM = os.getenv('EMAIL_FROM', 'nextClass <noreply@nextclass.app>')

# OTP Configuration
OTP_LENGTH = 4
OTP_EXPIRY_MINUTES = 10
MAX_ATTEMPTS = 3


def generate_otp():
    """Generate a random 4-digit OTP"""
    return ''.join(random.choices(string.digits, k=OTP_LENGTH))


def send_email(to_email, otp):
    """Send OTP email to user"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Your nextClass verification code: {otp}'
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email

        # Plain text version
        text = f"""
Hi there!

Your verification code for nextClass is: {otp}

This code will expire in {OTP_EXPIRY_MINUTES} minutes.

If you didn't request this code, please ignore this email.

- nextClass Team
"""

        # HTML version
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ color: #172C3D; font-size: 28px; margin: 0; }}
        .otp-box {{ background: linear-gradient(135deg, #284E6D, #172C3D); color: white; font-size: 32px; font-weight: bold; letter-spacing: 8px; padding: 20px 40px; border-radius: 12px; text-align: center; margin: 30px 0; }}
        .message {{ color: #666; font-size: 14px; line-height: 1.6; text-align: center; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; color: #999; font-size: 12px; }}
        .expiry {{ color: #e74c3c; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h1>nextClass</h1>
        </div>
        <p class="message">Hi there! 👋</p>
        <p class="message">Use the following code to verify your email:</p>
        <div class="otp-box">{otp}</div>
        <p class="message expiry">This code expires in {OTP_EXPIRY_MINUTES} minutes.</p>
        <p class="message">If you didn't request this code, you can safely ignore this email.</p>
        <div class="footer">
            <p>© 2024 nextClass. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())

        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    """Send OTP to user's email"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()

        if not email or '@' not in email:
            return jsonify({
                'success': False,
                'message': 'Invalid email address'
            }), 400

        # Generate OTP
        otp = generate_otp()
        
        # Store OTP with expiry and attempt count
        otp_storage[email] = {
            'otp': otp,
            'created_at': datetime.now(),
            'attempts': 0
        }

        # Send email
        if send_email(email, otp):
            return jsonify({
                'success': True,
                'message': 'OTP sent successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send email. Please try again.'
            }), 500

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error. Please try again.'
        }), 500


@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP entered by user"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        otp = data.get('otp', '').strip()

        if not email or not otp:
            return jsonify({
                'success': False,
                'message': 'Email and OTP are required'
            }), 400

        # Check if OTP exists for this email
        if email not in otp_storage:
            return jsonify({
                'success': False,
                'message': 'No OTP found. Please request a new one.'
            }), 400

        stored = otp_storage[email]

        # Check if OTP is expired
        expiry_time = stored['created_at'] + timedelta(minutes=OTP_EXPIRY_MINUTES)
        if datetime.now() > expiry_time:
            del otp_storage[email]
            return jsonify({
                'success': False,
                'message': 'OTP has expired. Please request a new one.'
            }), 400

        # Check attempt count
        if stored['attempts'] >= MAX_ATTEMPTS:
            del otp_storage[email]
            return jsonify({
                'success': False,
                'message': 'Too many failed attempts. Please request a new OTP.'
            }), 400

        # Verify OTP
        if stored['otp'] == otp:
            # OTP is correct - remove from storage
            del otp_storage[email]
            return jsonify({
                'success': True,
                'message': 'OTP verified successfully'
            })
        else:
            # Wrong OTP - increment attempt count
            otp_storage[email]['attempts'] += 1
            remaining = MAX_ATTEMPTS - otp_storage[email]['attempts']
            return jsonify({
                'success': False,
                'message': f'Invalid OTP. {remaining} attempts remaining.'
            }), 400

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error. Please try again.'
        }), 500


@app.route('/api/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP to user's email"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()

        if not email or '@' not in email:
            return jsonify({
                'success': False,
                'message': 'Invalid email address'
            }), 400

        # Generate new OTP
        otp = generate_otp()
        
        # Update storage
        otp_storage[email] = {
            'otp': otp,
            'created_at': datetime.now(),
            'attempts': 0
        }

        # Send email
        if send_email(email, otp):
            return jsonify({
                'success': True,
                'message': 'New OTP sent successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send email. Please try again.'
            }), 500

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error. Please try again.'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'nextClass OTP Service'})


# ==================== NOTIFICATION SERVICE ====================
# Import notification service
try:
    from notification_service import (
        initialize_firebase,
        start_scheduler,
        check_and_send_notifications
    )
    
    # Initialize Firebase for notifications
    firebase_initialized = initialize_firebase()
    notification_scheduler = None
    
    if firebase_initialized:
        print("✅ Firebase initialized for notifications")
        # Auto-start scheduler (works with gunicorn on Railway too)
        try:
            notification_scheduler = start_scheduler()
            print("🚀 Notification scheduler auto-started")
        except Exception as e:
            print(f"⚠️ Failed to auto-start scheduler: {e}")
except ImportError as e:
    print(f"⚠️ Notification service not available: {e}")
    firebase_initialized = False
    notification_scheduler = None


@app.route('/api/notifications/start', methods=['POST'])
def start_notifications():
    """Start the notification scheduler"""
    global notification_scheduler
    
    if not firebase_initialized:
        return jsonify({
            'success': False,
            'message': 'Firebase not initialized. Check service account key.'
        }), 500
    
    try:
        if notification_scheduler is None:
            notification_scheduler = start_scheduler()
            return jsonify({
                'success': True,
                'message': 'Notification scheduler started'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Notification scheduler already running'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start scheduler: {e}'
        }), 500


@app.route('/api/notifications/stop', methods=['POST'])
def stop_notifications():
    """Stop the notification scheduler"""
    global notification_scheduler
    
    try:
        if notification_scheduler:
            notification_scheduler.shutdown()
            notification_scheduler = None
            return jsonify({
                'success': True,
                'message': 'Notification scheduler stopped'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Notification scheduler was not running'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to stop scheduler: {e}'
        }), 500


@app.route('/api/notifications/trigger', methods=['POST'])
def trigger_notification_check():
    """Manually trigger a notification check (for testing)"""
    if not firebase_initialized:
        return jsonify({
            'success': False,
            'message': 'Firebase not initialized. Check service account key.'
        }), 500
    
    try:
        check_and_send_notifications()
        return jsonify({
            'success': True,
            'message': 'Notification check triggered'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to check notifications: {e}'
        }), 500


@app.route('/api/notifications/status', methods=['GET'])
def notification_status():
    """Get notification service status"""
    return jsonify({
        'firebase_initialized': firebase_initialized,
        'scheduler_running': notification_scheduler is not None,
        'service': 'nextClass Notification Service'
    })


@app.route('/api/notifications/preferences', methods=['GET'])
def get_notification_preferences():
    """Get notification preferences for a user (by uid query param)"""
    uid = request.args.get('uid', '').strip()
    if not uid:
        return jsonify({
            'success': False,
            'message': 'User ID is required'
        }), 400

    try:
        if not firebase_initialized:
            return jsonify({
                'success': False,
                'message': 'Firebase not initialized'
            }), 500

        from firebase_admin import firestore as admin_firestore
        db = admin_firestore.client()
        user_doc = db.collection('users').document(uid).get()

        if user_doc.exists:
            data = user_doc.to_dict()
            return jsonify({
                'success': True,
                'preferences': {
                    'notificationsEnabled': data.get('notificationsEnabled', False),
                    'notifyMinutesBefore': data.get('notifyMinutesBefore', 10),
                }
            })
        else:
            return jsonify({
                'success': True,
                'preferences': {
                    'notificationsEnabled': False,
                    'notifyMinutesBefore': 10,
                }
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching preferences: {e}'
        }), 500


@app.route('/api/notifications/preferences', methods=['POST'])
def update_notification_preferences():
    """Update notification preferences for a user"""
    try:
        data = request.get_json()
        uid = data.get('uid', '').strip()
        notify_minutes_before = data.get('notifyMinutesBefore', 10)
        notifications_enabled = data.get('notificationsEnabled', False)

        if not uid:
            return jsonify({
                'success': False,
                'message': 'User ID is required'
            }), 400

        # Validate timing value (1-60 minutes)
        try:
            notify_minutes_before = int(notify_minutes_before)
        except (ValueError, TypeError):
            notify_minutes_before = 10

        if notify_minutes_before < 1 or notify_minutes_before > 60:
            return jsonify({
                'success': False,
                'message': 'notifyMinutesBefore must be between 1 and 60'
            }), 400

        if not firebase_initialized:
            return jsonify({
                'success': False,
                'message': 'Firebase not initialized'
            }), 500

        from firebase_admin import firestore as admin_firestore
        db = admin_firestore.client()
        db.collection('users').document(uid).set({
            'notificationsEnabled': notifications_enabled,
            'notifyMinutesBefore': notify_minutes_before,
        }, merge=True)

        return jsonify({
            'success': True,
            'message': 'Preferences updated successfully',
            'preferences': {
                'notificationsEnabled': notifications_enabled,
                'notifyMinutesBefore': notify_minutes_before,
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error updating preferences: {e}'
        }), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    
    # Auto-start notification scheduler if Firebase is initialized
    if firebase_initialized:
        try:
            notification_scheduler = start_scheduler()
            print("🚀 Notification scheduler auto-started")
        except Exception as e:
            print(f"⚠️ Failed to auto-start notification scheduler: {e}")
    
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False') == 'True')
