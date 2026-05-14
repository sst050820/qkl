import os

# 项目根目录路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 数据目录，用于存储数据库和区块链数据
DATA_DIR = os.path.join(BASE_DIR, "data")

# 上传文件目录，用于存储用户上传的图片
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

# SQLite 数据库文件路径
DATABASE_PATH = os.path.join(DATA_DIR, "app.db")

# 区块链数据文件路径，存储 JSON 格式的区块链
CHAIN_PATH = os.path.join(DATA_DIR, "chain_data.json")

# Flask 应用密钥，用于会话管理和安全
SECRET_KEY = "change-this-secret-key"

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# 工作量证明难度，哈希前缀需要多少个 0
POW_DIFFICULTY = 3
