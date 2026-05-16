import os


def _expand_path(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def _env_path(name: str, default: str) -> str:
    return _expand_path(os.environ[name]) if name in os.environ else _expand_path(default)


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

# Hyperledger Fabric 配置
FABRIC_ENABLED = True  # 是否启用 Fabric 功能
FABRIC_NETWORK_DIR = _env_path(
    "FABRIC_NETWORK_DIR",
    "~/HyperledgerFabric/fabric-samples/test-network",
)
FABRIC_BIN_DIR = _env_path(
    "FABRIC_BIN_DIR",
    "~/HyperledgerFabric/fabric-samples/bin",
)
FABRIC_CFG_PATH = _env_path(
    "FABRIC_CFG_PATH",
    "~/HyperledgerFabric/fabric-samples/config",
)
FABRIC_PEER_BIN_PATH = _expand_path(
    os.environ.get(
        "FABRIC_PEER_BIN_PATH",
        os.path.join(FABRIC_BIN_DIR, "peer"),
    )
)


def _fabric_msp_path(org: str = "org1.example.com") -> str:
    return os.path.join(
        FABRIC_NETWORK_DIR,
        "organizations",
        "peerOrganizations",
        org,
        "users",
        f"Admin@{org}",
        "msp",
    )
FABRIC_CHANNEL = os.environ.get("FABRIC_CHANNEL", "mychannel")
FABRIC_CHAINCODE_NAME = os.environ.get(
    "FABRIC_CHAINCODE_NAME",
    os.environ.get("FABRIC_CHAINCODE", "donation"),
)
FABRIC_CHAINCODE = FABRIC_CHAINCODE_NAME
FABRIC_LOCALMSPID = os.environ.get("FABRIC_LOCALMSPID", "Org1MSP")
FABRIC_MSPCONFIGPATH = _expand_path(
    os.environ.get(
        "FABRIC_MSPCONFIGPATH",
        _fabric_msp_path("org1.example.com"),
    )
)
FABRIC_PEER_ADDRESS = os.environ.get("FABRIC_PEER_ADDRESS", "localhost:7051")
FABRIC_TLS_ENABLED = os.environ.get("FABRIC_TLS_ENABLED", "true")
FABRIC_TLS_ROOTCERT_FILE = _expand_path(
    os.environ.get(
        "FABRIC_TLS_ROOTCERT_FILE",
        os.path.join(
            FABRIC_NETWORK_DIR,
            "organizations/peerOrganizations/org1.example.com/peers"
            "/peer0.org1.example.com/tls/ca.crt",
        ),
    )
)

# Orderer 节点配置
ORDERER_ADDRESS = os.environ.get("ORDERER_ADDRESS", "localhost:7050")
ORDERER_HOSTNAME_OVERRIDE = os.environ.get(
    "ORDERER_HOSTNAME_OVERRIDE",
    "orderer.example.com",
)
ORDERER_TLS_CA = _expand_path(
    os.environ.get(
        "ORDERER_TLS_CA",
        os.path.join(
            FABRIC_NETWORK_DIR,
            "organizations/ordererOrganizations/example.com/orderers"
            "/orderer.example.com/tls/ca.crt",
        ),
    )
)

# Org1 Peer 配置
ORG1_PEER_ADDRESS = os.environ.get("ORG1_PEER_ADDRESS", "localhost:7051")
ORG1_MSP_ID = os.environ.get("ORG1_MSP_ID", "Org1MSP")
ORG1_TLS_ROOTCERT = _expand_path(
    os.environ.get(
        "ORG1_TLS_ROOTCERT",
        os.path.join(
            FABRIC_NETWORK_DIR,
            "organizations/peerOrganizations/org1.example.com/peers"
            "/peer0.org1.example.com/tls/ca.crt",
        ),
    )
)
ORG1_MSP_CONFIG = _expand_path(
    os.environ.get(
        "ORG1_MSP_CONFIG",
        _fabric_msp_path("org1.example.com"),
    )
)

# Org2 Peer 配置（可选多背书环境）
ORG2_PEER_ADDRESS = os.environ.get("ORG2_PEER_ADDRESS", "localhost:9051")
ORG2_MSP_ID = os.environ.get("ORG2_MSP_ID", "Org2MSP")
ORG2_TLS_ROOTCERT = _expand_path(
    os.environ.get(
        "ORG2_TLS_ROOTCERT",
        os.path.join(
            FABRIC_NETWORK_DIR,
            "organizations/peerOrganizations/org2.example.com/peers"
            "/peer0.org2.example.com/tls/ca.crt",
        ),
    )
)
ORG2_MSP_CONFIG = _expand_path(
    os.environ.get(
        "ORG2_MSP_CONFIG",
        _fabric_msp_path("org2.example.com"),
    )
)
