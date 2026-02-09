"""
Hostinger Passenger WSGI entry point
This file is required for Hostinger shared hosting Python apps
"""
import sys
import os

# Add your app directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import your Flask app
from app import app as application

# Passenger requires 'application' variable
if __name__ == '__main__':
    application.run()
