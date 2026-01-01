import sys, os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Activate your virtualenv
activate_this = '/home/cqyjdomh/virtualenv/retanoenv/3.11/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Import Django WSGI application from your existing wsgi.py
from Retano.wsgi import application
