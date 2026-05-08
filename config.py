import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
DATABASE_PATH = os.path.join(DATA_DIR, "app.db")
CHAIN_PATH = os.path.join(DATA_DIR, "chain_data.json")
SECRET_KEY = "change-this-secret-key"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
POW_DIFFICULTY = 3
