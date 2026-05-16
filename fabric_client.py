import json
import logging
import os
import subprocess
import time
from typing import Any

from config import (
    FABRIC_BIN_DIR,
    FABRIC_CHANNEL,
    FABRIC_CHAINCODE_NAME,
    FABRIC_CFG_PATH,
    FABRIC_ENABLED,
    FABRIC_LOCALMSPID,
    FABRIC_PEER_BIN_PATH,
    FABRIC_MSPCONFIGPATH,
    FABRIC_NETWORK_DIR,
    FABRIC_PEER_ADDRESS,
    FABRIC_TLS_ENABLED,
    FABRIC_TLS_ROOTCERT_FILE,
    FABRIC_CHAINCODE,
    ORDERER_ADDRESS,
    ORDERER_HOSTNAME_OVERRIDE,
    ORDERER_TLS_CA,
    ORG1_MSP_CONFIG,
    ORG1_MSP_ID,
    ORG1_PEER_ADDRESS,
    ORG1_TLS_ROOTCERT,
    ORG2_PEER_ADDRESS,
    ORG2_TLS_ROOTCERT,
)

log = logging.getLogger(__name__)

# peer 命令完整路径
PEER_BIN = os.path.abspath(os.path.expanduser(FABRIC_PEER_BIN_PATH)) if FABRIC_PEER_BIN_PATH else os.path.join(FABRIC_BIN_DIR, "peer")


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _build_env() -> dict:
    """构造 peer CLI 运行所需的环境变量。"""
    env = os.environ.copy()
    env["PATH"] = f"{FABRIC_BIN_DIR}:{env.get('PATH', '')}"
    env["FABRIC_CFG_PATH"] = FABRIC_CFG_PATH
    if FABRIC_LOCALMSPID:
        env["CORE_PEER_LOCALMSPID"] = FABRIC_LOCALMSPID
    if FABRIC_PEER_ADDRESS:
        env["CORE_PEER_ADDRESS"] = FABRIC_PEER_ADDRESS
    peer_msp_path = FABRIC_MSPCONFIGPATH or ORG1_MSP_CONFIG
    if peer_msp_path:
        env["CORE_PEER_MSPCONFIGPATH"] = peer_msp_path
    if FABRIC_TLS_ROOTCERT_FILE:
        env["CORE_PEER_TLS_ROOTCERT_FILE"] = FABRIC_TLS_ROOTCERT_FILE
    env["CORE_PEER_TLS_ENABLED"] = "true" if _bool_value(FABRIC_TLS_ENABLED) else "false"
    return env


def _run(cmd: list[str], timeout: int = 60) -> tuple[bool, str]:
    """执行 peer 命令，返回是否成功和命令输出。"""
    env = _build_env()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=FABRIC_NETWORK_DIR,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        log.error(
            "[Fabric] command failed: %s\nSTDERR: %s",
            " ".join(cmd),
            result.stderr.strip(),
        )
        return False, result.stderr.strip() or result.stdout.strip()
    except subprocess.TimeoutExpired:
        log.error("[Fabric] command timeout: %s", " ".join(cmd))
        return False, "timeout"
    except FileNotFoundError:
        log.error("[Fabric] peer binary not found: %s", PEER_BIN)
        return False, "peer binary not found"


def query_chaincode(function: str, args: list[str]) -> tuple[bool, Any]:
    payload = json.dumps({"Args": [function] + args}, ensure_ascii=False)
    cmd = [
        PEER_BIN,
        "chaincode",
        "query",
        "-C",
        FABRIC_CHANNEL,
        "-n",
        FABRIC_CHAINCODE_NAME or FABRIC_CHAINCODE,
        "-c",
        payload,
    ]
    ok, output = _run(cmd)
    if not ok:
        return False, output
    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return True, output


def invoke_chaincode(function: str, args: list[str]) -> tuple[bool, str]:
    payload = json.dumps({"function": function, "Args": args}, ensure_ascii=False)
    cmd = [
        PEER_BIN,
        "chaincode",
        "invoke",
        "-o",
        ORDERER_ADDRESS,
        "--ordererTLSHostnameOverride",
        ORDERER_HOSTNAME_OVERRIDE,
        "--tls",
        "--cafile",
        ORDERER_TLS_CA,
        "-C",
        FABRIC_CHANNEL,
        "-n",
        FABRIC_CHAINCODE_NAME or FABRIC_CHAINCODE,
        "--peerAddresses",
        ORG1_PEER_ADDRESS,
        "--tlsRootCertFiles",
        ORG1_TLS_ROOTCERT,
    ]
    if ORG2_PEER_ADDRESS and ORG2_TLS_ROOTCERT:
        cmd += [
            "--peerAddresses",
            ORG2_PEER_ADDRESS,
            "--tlsRootCertFiles",
            ORG2_TLS_ROOTCERT,
        ]
    cmd += ["-c", payload]
    ok, output = _run(cmd, timeout=120)
    if ok:
        time.sleep(2)
    return ok, output


class FabricClient:
    """封装 Hyperledger Fabric 链码交互。"""

    def __init__(self):
        self.enabled = FABRIC_ENABLED

    def is_ready(self) -> bool:
        if not self.enabled:
            return False
        if not os.path.isfile(PEER_BIN) or not os.access(PEER_BIN, os.X_OK):
            log.warning("[Fabric] peer binary unavailable: %s", PEER_BIN)
            return False
        if not os.path.isdir(FABRIC_NETWORK_DIR):
            log.warning("[Fabric] network directory missing: %s", FABRIC_NETWORK_DIR)
            return False
        if not os.path.isdir(FABRIC_CFG_PATH):
            log.warning("[Fabric] fabric config directory missing: %s", FABRIC_CFG_PATH)
            return False
        if not FABRIC_MSPCONFIGPATH or not os.path.isdir(FABRIC_MSPCONFIGPATH):
            log.warning("[Fabric] MSP config path missing: %s", FABRIC_MSPCONFIGPATH)
            return False
        if _bool_value(FABRIC_TLS_ENABLED):
            tls_files = {
                "CORE_PEER_TLS_ROOTCERT_FILE": FABRIC_TLS_ROOTCERT_FILE,
                "ORDERER_TLS_CA": ORDERER_TLS_CA,
                "ORG1_TLS_ROOTCERT": ORG1_TLS_ROOTCERT,
            }
            if ORG2_PEER_ADDRESS and ORG2_TLS_ROOTCERT:
                tls_files["ORG2_TLS_ROOTCERT"] = ORG2_TLS_ROOTCERT
            for name, path in tls_files.items():
                if not path or not os.path.isfile(path):
                    log.warning("[Fabric] TLS certificate missing for %s: %s", name, path)
                    return False
        return True

    def add_donation(
        self,
        tracking_id: str,
        item_type: str,
        condition: str,
        donor_name: str,
        photo_hash: str,
        note: str = "",
    ) -> tuple[bool, str]:
        return invoke_chaincode(
            "CreateDonation",
            [tracking_id, item_type, condition, donor_name, photo_hash, note],
        )

    def update_status(
        self,
        tracking_id: str,
        new_status: str,
        note: str = "",
    ) -> tuple[bool, str]:
        return invoke_chaincode("UpdateStatus", [tracking_id, new_status, note])

    def confirm_receipt(
        self,
        tracking_id: str,
        receiver_name: str,
        note: str = "",
    ) -> tuple[bool, str]:
        return invoke_chaincode("ConfirmReceipt", [tracking_id, receiver_name, note])

    def get_all_donations(self) -> list[dict]:
        ok, result = query_chaincode("GetAllDonations", [])
        if not ok or not result:
            return []
        if isinstance(result, list):
            return result
        return []

    def get_donation(self, tracking_id: str) -> dict | None:
        ok, result = query_chaincode("GetDonation", [tracking_id])
        if not ok or not result:
            return None
        if isinstance(result, dict):
            return result
        return None

    def get_item_history(self, tracking_id: str) -> list[dict]:
        ok, result = query_chaincode("GetDonationHistory", [tracking_id])
        if not ok or not result:
            return []
        if isinstance(result, list):
            return result
        return []

    def get_latest_item(self, tracking_id: str) -> dict | None:
        donation = self.get_donation(tracking_id)
        if not donation:
            return None
        return {
            "event": donation,
            "timestamp": donation.get("timestamp", ""),
            "tracking_id": tracking_id,
        }

    def get_all_trackings(self) -> list[str]:
        return [
            d["tracking_id"] for d in self.get_all_donations() if isinstance(d, dict) and "tracking_id" in d
        ]

    def is_valid_chain(self) -> bool:
        cmd = [PEER_BIN, "channel", "getinfo", "-c", FABRIC_CHANNEL]
        ok, _ = _run(cmd, timeout=10)
        return ok

    def get_block_height(self) -> int:
        cmd = [PEER_BIN, "channel", "getinfo", "-c", FABRIC_CHANNEL]
        ok, output = _run(cmd, timeout=10)
        if not ok:
            return 0
        try:
            start = output.index("{")
            info = json.loads(output[start:])
            return int(info.get("height", 0))
        except (ValueError, KeyError, json.JSONDecodeError):
            return 0

    def add_block(self, event: dict) -> tuple[bool, str]:
        tracking_id = event.get("tracking_id", "")
        status = event.get("status", "")
        note = event.get("note", "")

        if status == "待接收":
            return self.add_donation(
                tracking_id=tracking_id,
                item_type=event.get("item_type", ""),
                condition=event.get("condition", ""),
                donor_name=event.get("donor_name", ""),
                photo_hash=event.get("photo_hash", ""),
                note=note,
            )
        if status == "已签收":
            return self.confirm_receipt(
                tracking_id=tracking_id,
                receiver_name=event.get("receiver", ""),
                note=note,
            )
        return self.update_status(
            tracking_id=tracking_id,
            new_status=status,
            note=note,
        )

    def get_all_events(self) -> list[dict]:
        return self.get_all_donations()

    @property
    def chain(self):
        return _FabricChainProxy(self)


class _FabricChainProxy:
    def __init__(self, client: FabricClient):
        self._client = client
        self._blocks: list[_FabricBlockProxy] | None = None

    def _load(self):
        if self._blocks is None:
            donations = self._client.get_all_donations()
            self._blocks = [_FabricBlockProxy(d) for d in donations]

    def __iter__(self):
        self._load()
        return iter(self._blocks)

    def __len__(self):
        self._load()
        return len(self._blocks)

    def __getitem__(self, idx):
        self._load()
        return self._blocks[idx]


class _FabricBlockProxy:
    def __init__(self, donation: dict):
        self.data = donation
        self.timestamp = donation.get("timestamp", "")
        self.hash = donation.get("tracking_id", "")

    def to_dict(self):
        return {
            "data": self.data,
            "timestamp": self.timestamp,
            "hash": self.hash,
            "tracking_id": self.data.get("tracking_id", ""),
        }
