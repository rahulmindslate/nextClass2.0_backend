# Class Notification Service Setup Guide

This guide explains how to set up the backend notification service that sends push notifications 10 minutes before each class.

## Overview

The notification service:
- Runs every minute to check for upcoming classes
- Sends FCM push notifications 10 minutes before each class starts
- Filters notifications based on user's selected courses
- Supports both Android and iOS devices

## Prerequisites

1. **Firebase Admin SDK Service Account Key**
2. **Python 3.8+**
3. **Firebase Cloud Messaging enabled** in your Firebase project

## Setup Steps

### Step 1: Get Firebase Service Account Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (`nextclass2-9a51f`)
3. Go to **Project Settings** (gear icon) → **Service Accounts**
4. Click **"Generate new private key"**
5. Save the downloaded JSON file as `serviceAccountKey.json` in the `backend/` folder

> ⚠️ **IMPORTANT**: Never commit `serviceAccountKey.json` to version control!

### Step 2: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Create a `.env` file in the `backend/` folder:

```env
# Email Configuration (existing)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_PATH=serviceAccountKey.json
FIREBASE_DATABASE_URL=https://nextclass2-9a51f-default-rtdb.firebaseio.com

# Server Configuration
PORT=5000
DEBUG=False
```

### Step 4: Update .gitignore

Add these lines to your `.gitignore`:

```gitignore
# Firebase Service Account (NEVER commit this!)
backend/serviceAccountKey.json
backend/*.json
!backend/package.json

# Environment files
backend/.env
```

### Step 5: Run the Server

```bash
cd backend
python app.py
```

The notification scheduler will auto-start when the server starts.

## API Endpoints

### Notification Service

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/notifications/status` | GET | Check notification service status |
| `/api/notifications/start` | POST | Start the notification scheduler |
| `/api/notifications/stop` | POST | Stop the notification scheduler |
| `/api/notifications/trigger` | POST | Manually trigger a notification check |

### Test the Service

```bash
# Check status
curl http://localhost:5000/api/notifications/status

# Manually trigger notification check
curl -X POST http://localhost:5000/api/notifications/trigger
```

## How It Works

### 1. User Registration (Flutter App)

When users log in or sign up, their FCM token is saved to Firestore:

```dart
// In firebase_api.dart
await FirebaseFirestore.instance
    .collection('users')
    .doc(user.uid)
    .update({
  'fcmToken': token,
  'fcmTokenUpdatedAt': FieldValue.serverTimestamp(),
});
```

### 2. Firestore User Document Structure

```json
{
  "uid": "user-uid",
  "name": "Student Name",
  "email": "student@example.com",
  "college": "CollegeName",
  "yearType": "UG",
  "year": "1st Year",
  "branch": "Computer Science",
  "selectedCourses": ["CS101", "MATH201", "PHY101"],
  "fcmToken": "fcm-device-token",
  "fcmTokenUpdatedAt": "2024-01-15T10:30:00Z"
}
```

### 3. Backend Notification Flow

Every minute, the backend:

1. **Gets current time** and weekday (IST timezone)
2. **Calculates target time** (current time + 10 minutes)
3. **Fetches all users** with FCM tokens from Firestore
4. For each user:
   - Gets their college's class slots from Realtime Database
   - Filters slots by user's selected courses
   - Checks if any class starts in ~10 minutes
   - Sends FCM notification if match found

### 4. Notification Content

```
📚 CS101 in 10 minutes!
Computer Science 101 • Room: A-201 • Prof: Dr. Smith • Starts at 10:00
```

## Production Deployment

### Option A: Run as Standalone Service

```bash
# Using gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app

# Or using a process manager like PM2
pm2 start "python app.py" --name nextclass-backend
```

### Option B: Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
```

### Option C: Cloud Functions (Serverless)

For a serverless approach, you can deploy the notification logic as a Firebase Cloud Function that runs on a schedule.

## Timezone Configuration

The service defaults to `Asia/Kolkata` (IST) timezone. To change:

```python
# In notification_service.py
check_and_send_notifications(timezone='America/New_York')
```

## Troubleshooting

### Notifications Not Sending

1. **Check Firebase initialization**:
   ```bash
   curl http://localhost:5000/api/notifications/status
   ```
   Should show `firebase_initialized: true`

2. **Check service account key**:
   - Verify `serviceAccountKey.json` exists and is valid
   - Ensure it has correct permissions

3. **Check user FCM tokens**:
   - Verify users have `fcmToken` field in Firestore
   - Tokens expire if users uninstall the app

4. **Check logs**:
   ```bash
   python notification_service.py
   ```
   This runs a single check and shows detailed logs

### Common Errors

| Error | Solution |
|-------|----------|
| `Firebase not initialized` | Check `serviceAccountKey.json` path and content |
| `Token unregistered` | User's FCM token is invalid (app uninstalled) |
| `No users with FCM tokens` | Users haven't logged in since FCM token saving was added |

## Security Considerations

1. **Never commit** `serviceAccountKey.json` to version control
2. **Use environment variables** for sensitive configuration
3. **Implement rate limiting** on API endpoints
4. **Use HTTPS** in production
5. **Validate FCM tokens** periodically and remove invalid ones

## Contributing

To modify the notification timing:

```python
# In notification_service.py
# Change 10 to desired minutes before class
check_and_send_notifications(notification_minutes_before=10)
```

To add custom notification conditions, modify the `check_and_send_notifications()` function.
