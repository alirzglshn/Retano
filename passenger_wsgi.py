import sys, os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Activate virtualenv FIRST
activate_this = '/home/cqyjdomh/virtualenv/Retano/3.12/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Retano.settings")

# Import Django WSGI application
from Retano.wsgi import application
