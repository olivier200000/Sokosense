"""
Start-up file for GoDaddy (cPanel "Setup Python App").
GoDaddy runs this file to start the website. Do not rename it.

In Setup Python App use:
    Application startup file:  passenger_wsgi.py
    Application entry point:   application
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app as application  # noqa: E402
