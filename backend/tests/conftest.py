"""
Shared pytest configuration for MaintX backend tests.
"""
import sys
import os

# Ensure the backend directory is on the Python path so that `app.*` imports work.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
