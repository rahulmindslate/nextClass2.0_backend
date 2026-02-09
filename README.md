# nextClass Backend

A Flask server for handling OTP-based email authentication and class notification services.

## Features

### OTP Service
- 4-digit OTP generation
- Beautiful HTML email templates
- OTP expiry (10 minutes)
- Maximum 3 attempts per OTP
- Resend OTP functionality

### Notification Service 🔔 (NEW)
- Automatic push notifications 10 minutes before classes
- Firebase Cloud Messaging (FCM) integration
- User-specific notifications based on selected courses
- Runs continuously in the background

> 📖 See [NOTIFICATION_SETUP.md](./NOTIFICATION_SETUP.md) for detailed setup instructions.

## API Endpoints

### OTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/send-otp` | POST | Send OTP to email |
| `/api/verify-otp` | POST | Verify entered OTP |
| `/api/resend-otp` | POST | Resend new OTP |
| `/health` | GET | Health check |

### Notification Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/notifications/status` | GET | Check notification service status |
| `/api/notifications/start` | POST | Start notification scheduler |
| `/api/notifications/stop` | POST | Stop notification scheduler |
| `/api/notifications/trigger` | POST | Manually trigger notification check |

## Request/Response Examples

### Send OTP
```json
// POST /api/send-otp
// Request
{ "email": "user@example.com" }

// Response
{ "success": true, "message": "OTP sent successfully" }
```

### Verify OTP
```json
// POST /api/verify-otp
// Request
{ "email": "user@example.com", "otp": "1234" }

// Response (success)
{ "success": true, "message": "OTP verified successfully" }

// Response (failure)
{ "success": false, "message": "Invalid OTP. 2 attempts remaining." }
```

## Local Development

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

4. Update `.env` with your email credentials:
   - For Gmail, create an App Password:
     - Go to Google Account > Security > 2-Step Verification
     - Scroll down to "App passwords"
     - Generate a new password for "Mail"

5. Run the server:
   ```bash
   python app.py
   ```

## Deploy to Hostinger (Shared Hosting)

If you have Hostinger Premium/Business/Cloud shared hosting:

1. **Login to hPanel** at [hpanel.hostinger.com](https://hpanel.hostinger.com)

2. **Go to**: Advanced → Python (or Website → Python)

3. **Create Python Application**:
   - Python version: `3.10` or higher
   - Application root: `/domains/mindslate.in/public_html/api` (or subdomain folder)
   - Application URL: `api.mindslate.in` (if using subdomain) or `mindslate.in/api`
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`

4. **Upload files** via File Manager or FTP:
   - Upload all files from `backend/` folder to the application root
   - Make sure to upload: `app.py`, `passenger_wsgi.py`, `requirements.txt`

5. **Create `.env` file** in the same directory with your email credentials:
   ```
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USER=your-email@gmail.com
   EMAIL_PASSWORD=your-app-password
   EMAIL_FROM=nextClass <your-email@gmail.com>
   ```

6. **Install dependencies**: In hPanel Python section, click "Run pip install" or use the terminal:
   ```bash
   pip install -r requirements.txt
   ```

7. **Restart the application** from hPanel

8. **Your API will be at**: `https://api.mindslate.in` or `https://mindslate.in/api`

### Setting up API Subdomain (Recommended)

1. Go to hPanel → Domains → Subdomains
2. Create subdomain: `api.mindslate.in`
3. Point it to your Python app folder
4. Your API endpoints will be:
   - `https://api.mindslate.in/api/send-otp`
   - `https://api.mindslate.in/api/verify-otp`

---

## Deploy to Render (Free)

1. Push code to GitHub

2. Go to [render.com](https://render.com) and create new "Web Service"

3. Connect your GitHub repository

4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

5. Add Environment Variables:
   - `EMAIL_HOST` = smtp.gmail.com
   - `EMAIL_PORT` = 587
   - `EMAIL_USER` = your-email@gmail.com
   - `EMAIL_PASSWORD` = your-app-password
   - `EMAIL_FROM` = nextClass <your-email@gmail.com>

6. Deploy! Your URL will be: `https://your-app.onrender.com`

## Deploy to Railway (Free)

1. Push code to GitHub

2. Go to [railway.app](https://railway.app) and create new project

3. Deploy from GitHub repo

4. Add environment variables in Railway dashboard

5. Railway will auto-detect Flask and deploy

## Production Recommendations

For production, consider:

1. **Use Redis** for OTP storage instead of in-memory dict
2. **Add rate limiting** to prevent spam
3. **Use a transactional email service** like SendGrid, Mailgun, or AWS SES
4. **Add logging** for monitoring
5. **Use HTTPS** (handled automatically by Render/Railway)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| OTP_LENGTH | 4 | Number of digits in OTP |
| OTP_EXPIRY_MINUTES | 10 | OTP validity period |
| MAX_ATTEMPTS | 3 | Maximum verification attempts |
