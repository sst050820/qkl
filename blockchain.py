import hashlib
import json
import os
import time
from config import CHAIN_PATH, POW_DIFFICULTY


class Block:
    def __init__(self, index, timestamp, data, previous_hash, nonce=0, hash_value=None):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash_value or self.compute_hash()

    def compute_hash(self):
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, block_dict):
        return cls(
            index=block_dict["index"],
            timestamp=block_dict["timestamp"],
            data=block_dict["data"],
            previous_hash=block_dict["previous_hash"],
            nonce=block_dict.get("nonce", 0),
            hash_value=block_dict.get("hash"),
        )


class Blockchain:
    def __init__(self, path=CHAIN_PATH):
        self.path = path
        self.chain = []
        self.load_chain()

    def create_genesis_block(self):
        genesis_data = {
            "type": "genesis",
            "message": "公益捐赠溯源系统创世区块",
            "status": "初始化",
        }
        genesis = Block(0, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), genesis_data, "0")
        self.proof_of_work(genesis)
        return genesis

    def load_chain(self):
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.chain = [self.create_genesis_block()]
            self.save_chain()
            return

        with open(self.path, "r", encoding="utf-8") as file:
            try:
                chain_data = json.load(file)
                self.chain = [Block.from_dict(block) for block in chain_data]
                if not self.chain:
                    self.chain = [self.create_genesis_block()]
                    self.save_chain()
            except (ValueError, json.JSONDecodeError):
                self.chain = [self.create_genesis_block()]
                self.save_chain()

    def save_chain(self):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump([block.to_dict() for block in self.chain], file, indent=2, ensure_ascii=False)

    def get_last_block(self):
        return self.chain[-1]

    def proof_of_work(self, block):
        target = "0" * POW_DIFFICULTY
        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.compute_hash()
        return block.hash

    def add_block(self, data):
        last_block = self.get_last_block()
        new_block = Block(
            index=last_block.index + 1,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            data=data,
            previous_hash=last_block.hash,
        )
        self.proof_of_work(new_block)
        self.chain.append(new_block)
        self.save_chain()
        return new_block

    def get_all_events(self):
        return [block.to_dict() for block in self.chain if block.data.get("type") != "genesis"]

    def get_item_history(self, tracking_id):
        items = []
        for block in self.chain:
            data = block.data
            if data.get("tracking_id") == tracking_id:
                item = block.to_dict()
                item["event"] = data
                items.append(item)
        return items

    def get_latest_item(self, tracking_id):
        history = self.get_item_history(tracking_id)
        return history[-1] if history else None

    def is_valid_chain(self):
        for index in range(1, len(self.chain)):
            current = self.chain[index]
            previous = self.chain[index - 1]
            if current.previous_hash != previous.hash:
                return False
            if current.hash != current.compute_hash():
                return False
            if not current.hash.startswith("0" * POW_DIFFICULTY):
                return False
        return True

    def get_all_trackings(self):
        records = {}
        for block in self.chain:
            data = block.data
            if data.get("tracking_id"):
                records[data["tracking_id"]] = block
        return list(records.keys())
