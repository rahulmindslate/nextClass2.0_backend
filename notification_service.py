"""
Class Notification Service for nextClass App
Sends push notifications 10 minutes before each class starts.
"""

import firebase_admin
from firebase_admin import credentials, firestore, messaging, db
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import os
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
# Option 1: Use FIREBASE_CREDENTIALS env var (for Railway/cloud hosting - paste the full JSON)
# Option 2: Use serviceAccountKey.json file (for local development)

SERVICE_ACCOUNT_PATH = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH', 'serviceAccountKey.json')
DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL', 'https://nextclass2-9a51f-default-rtdb.firebaseio.com')

# Track sent notifications to avoid duplicates
sent_notifications = set()

def initialize_firebase():
    """Initialize Firebase Admin SDK. Supports both env var and file-based credentials."""
    try:
        if not firebase_admin._apps:
            # Try environment variable first (for Railway/cloud)
            firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS')
            if firebase_creds_json:
                cred_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(cred_dict)
                logger.info("🔑 Using Firebase credentials from environment variable")
            else:
                # Fall back to file (for local development)
                cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
                logger.info("🔑 Using Firebase credentials from file")
            
            firebase_admin.initialize_app(cred, {
                'databaseURL': DATABASE_URL
            })
            logger.info("✅ Firebase Admin SDK initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase: {e}")
        return False


def parse_time_to_minutes(time_str):
    """
    Parse time string (HH:MM) to minutes since midnight.
    Handles times like "02:15" which should be 14:15 (2:15 PM).
    College classes typically run from 8 AM to 6 PM.
    """
    try:
        parts = time_str.split(':')
        if len(parts) >= 2:
            hours = int(parts[0])
            minutes = int(parts[1])
            
            # If hour is less than 8, it's likely PM (afternoon)
            if hours < 8:
                hours += 12
            
            return hours * 60 + minutes
    except Exception:
        pass
    return 0


def get_current_time_minutes(timezone='Asia/Kolkata'):
    """Get current time in minutes since midnight for the specified timezone"""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    return now.hour * 60 + now.minute


def get_current_weekday(timezone='Asia/Kolkata'):
    """Get current weekday (1=Monday, 7=Sunday) for the specified timezone"""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    return now.weekday() + 1  # Python weekday is 0-6, we need 1-7


def get_all_users_with_tokens():
    """Get all users who have FCM tokens and selected courses"""
    try:
        firestore_db = firestore.client()
        users_ref = firestore_db.collection('users')
        
        # Get users with FCM tokens
        users = users_ref.where('fcmToken', '!=', '').stream()
        
        user_list = []
        for user in users:
            user_data = user.to_dict()
            if user_data.get('fcmToken') and user_data.get('selectedCourses'):
                # Skip users who disabled notifications
                if user_data.get('notificationsEnabled') == False:
                    continue
                user_list.append({
                    'uid': user.id,
                    'name': user_data.get('name', 'Student'),
                    'fcmToken': user_data.get('fcmToken'),
                    'college': user_data.get('college'),
                    'selectedCourses': user_data.get('selectedCourses', []),
                    'yearType': user_data.get('yearType'),
                    'year': user_data.get('year'),
                    'branch': user_data.get('branch'),
                    'notifyMinutesBefore': user_data.get('notifyMinutesBefore', 10),
                })
        
        logger.info(f"📋 Found {len(user_list)} users with FCM tokens")
        return user_list
    except Exception as e:
        logger.error(f"❌ Error fetching users: {e}")
        return []


def get_college_slots(college):
    """Get all slots for a specific college from Realtime Database"""
    try:
        ref = db.reference(f'colleges/{college}/slots')
        slots = ref.get()
        
        if slots:
            return slots
        return {}
    except Exception as e:
        logger.error(f"❌ Error fetching slots for {college}: {e}")
        return {}


def get_subject_info(college, year_type, year, branch):
    """Get subject information (faculty, full course name) from Realtime Database"""
    try:
        ref = db.reference(f'colleges/{college}/{year_type}/{year}/branches/{branch}/subjects')
        subjects = ref.get()
        
        if subjects:
            subject_info = {}
            for key, value in subjects.items():
                if isinstance(value, dict):
                    course_name = value.get('courseName', key)
                    subject_info[course_name] = {
                        'faculty': value.get('faculty', ''),
                        'fullCourseName': value.get('fullCourseName', ''),
                    }
            return subject_info
        return {}
    except Exception as e:
        logger.error(f"❌ Error fetching subjects: {e}")
        return {}


def send_notification(fcm_token, title, body, data=None):
    """Send a push notification to a specific device"""
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='@mipmap/ic_launcher',
                    color='#172C3D',
                    sound='default',
                    channel_id='high_importance_channel',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=body,
                        ),
                        sound='default',
                        badge=1,
                    ),
                ),
            ),
        )
        
        response = messaging.send(message)
        logger.info(f"✅ Notification sent successfully: {response}")
        return True
    except messaging.UnregisteredError:
        logger.warning(f"⚠️ Token unregistered, should remove from database")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to send notification: {e}")
        return False


def check_and_send_notifications(timezone='Asia/Kolkata'):
    """
    Check for upcoming classes and send notifications.
    Uses per-user notification timing preferences from Firestore.
    Supported values: 5, 10, 15 minutes before class.
    This function runs every minute.
    """
    logger.info("🔍 Checking for upcoming classes...")
    
    current_minutes = get_current_time_minutes(timezone)
    current_weekday = get_current_weekday(timezone)
    
    logger.info(f"📅 Current time: {current_minutes // 60}:{current_minutes % 60:02d} (weekday: {current_weekday})")
    
    # Get all users with FCM tokens (already filters out disabled users)
    users = get_all_users_with_tokens()
    
    if not users:
        logger.info("📭 No users with FCM tokens found")
        return
    
    notifications_sent = 0
    
    for user in users:
        college = user.get('college')
        selected_courses = user.get('selectedCourses', [])
        fcm_token = user.get('fcmToken')
        user_name = user.get('name', 'Student')
        notification_minutes_before = user.get('notifyMinutesBefore', 10)
        
        # Ensure valid timing value (1-60 minutes)
        try:
            notification_minutes_before = int(notification_minutes_before)
        except (ValueError, TypeError):
            notification_minutes_before = 10
        if notification_minutes_before < 1 or notification_minutes_before > 60:
            notification_minutes_before = 10
        
        target_start_time = current_minutes + notification_minutes_before
        
        if not college or not selected_courses or not fcm_token:
            continue
        
        # Get slots for this college
        slots = get_college_slots(college)
        
        if not slots:
            continue
        
        # Get subject info for better notification content
        subject_info = get_subject_info(
            college,
            user.get('yearType'),
            user.get('year'),
            user.get('branch')
        )
        
        # Check each slot
        for slot_key, slot in slots.items():
            if not isinstance(slot, dict):
                continue
            
            # Extract course name from eventName
            event_name = slot.get('eventName', '')
            course_name = event_name.split(' - ')[0].split(' (')[0].strip()
            
            # Check if user has this course selected
            if course_name not in selected_courses:
                continue
            
            # Check if this class is on today
            recurrence_days = slot.get('recurrenceDays', [])
            if isinstance(recurrence_days, dict):
                recurrence_days = list(recurrence_days.values())
            
            if current_weekday not in recurrence_days:
                continue
            
            # Check if class starts in ~10 minutes
            start_time = slot.get('startTime', '')
            start_minutes = parse_time_to_minutes(start_time)
            
            # ±1 minute tolerance
            if abs(start_minutes - target_start_time) <= 1:
                # Create unique notification ID to avoid duplicates
                notification_id = f"{user['uid']}_{slot_key}_{current_weekday}_{start_time}"
                
                if notification_id in sent_notifications:
                    logger.info(f"⏭️ Notification already sent: {notification_id}")
                    continue
                
                # Get full course name and faculty
                course_info = subject_info.get(course_name, {})
                full_course_name = course_info.get('fullCourseName', course_name)
                faculty = course_info.get('faculty', '')
                classroom = slot.get('roomNumber', '')
                
                # Build notification content
                title = f"📚 {course_name} in {notification_minutes_before} minutes!"
                body_parts = [f"{full_course_name}" if full_course_name != course_name else ""]
                if classroom:
                    body_parts.append(f"Room: {classroom}")
                if faculty:
                    body_parts.append(f"Prof: {faculty}")
                body_parts.append(f"Starts at {start_time}")
                
                body = " • ".join([p for p in body_parts if p])
                
                # Send notification
                if send_notification(
                    fcm_token,
                    title,
                    body,
                    data={
                        'type': 'class_reminder',
                        'course': course_name,
                        'startTime': start_time,
                        'classroom': classroom,
                        'deep_link': 'nextclass://home',
                    }
                ):
                    sent_notifications.add(notification_id)
                    notifications_sent += 1
                    logger.info(f"📤 Sent notification to {user_name} for {course_name}")
    
    logger.info(f"✅ Sent {notifications_sent} notifications this cycle")
    
    # Clear old notification IDs (older than 24 hours worth)
    # This is a simple cleanup - in production, use Redis with TTL
    if len(sent_notifications) > 10000:
        sent_notifications.clear()
        logger.info("🧹 Cleared sent notifications cache")


def start_scheduler():
    """Start the background scheduler to check for notifications every minute"""
    scheduler = BackgroundScheduler()
    
    # Run every minute
    scheduler.add_job(
        check_and_send_notifications,
        'interval',
        minutes=1,
        id='class_notification_job',
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("🚀 Notification scheduler started - checking every minute")
    return scheduler


# For running as standalone script
if __name__ == '__main__':
    if initialize_firebase():
        logger.info("🔄 Running notification check once...")
        check_and_send_notifications()
        
        # Uncomment below to run as a continuous service
        # scheduler = start_scheduler()
        # try:
        #     while True:
        #         import time
        #         time.sleep(60)
        # except KeyboardInterrupt:
        #     scheduler.shutdown()
        #     logger.info("👋 Scheduler stopped")
