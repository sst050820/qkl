import hashlib
import json
import os
import time
from config import CHAIN_PATH, POW_DIFFICULTY


class Block:
    """表示区块链中的单个区块。

    每个区块包含索引、时间戳、存储的数据、前一个区块的哈希、Nonce 值和当前区块的哈希。
    """

    def __init__(self, index, timestamp, data, previous_hash, nonce=0, hash_value=None):
        # 区块在链中的位置序号，从 0 开始
        self.index = index
        # 区块生成时间，字符串格式
        self.timestamp = timestamp
        # 区块承载的业务数据，可以是字典或其他可 JSON 序列化对象
        self.data = data
        # 前一个区块的哈希值，用于链接区块
        self.previous_hash = previous_hash
        # 工作量证明过程中变化的值，用于生成满足难度要求的哈希
        self.nonce = nonce
        # 如果传入了哈希值就使用传入值，否则自动计算当前区块的哈希
        self.hash = hash_value or self.compute_hash()

    def compute_hash(self):
        """计算当前区块的 SHA-256 哈希值。"""
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
        # 使用 UTF-8 编码后的字符串计算 SHA-256 哈希
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def to_dict(self):
        """将区块对象转换为可序列化的字典，便于持久化存储。"""
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
        """从字典恢复 Block 对象。"""
        return cls(
            index=block_dict["index"],
            timestamp=block_dict["timestamp"],
            data=block_dict["data"],
            previous_hash=block_dict["previous_hash"],
            nonce=block_dict.get("nonce", 0),
            hash_value=block_dict.get("hash"),
        )


class Blockchain:
    """管理区块链数据结构，包括加载、保存、添加区块和验证链。"""

    def __init__(self, path=CHAIN_PATH):
        # 区块链文件保存路径
        self.path = path
        # 内存中的区块链列表
        self.chain = []
        # 初始化时尝试从文件加载现有区块链
        self.load_chain()

    def create_genesis_block(self):
        """创建创世区块，这个区块是链中的第一个区块。"""
        genesis_data = {
            "type": "genesis",
            "message": "公益捐赠溯源系统创世区块",
            "status": "初始化",
        }
        genesis = Block(
            0,
            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            genesis_data,
            "0",
        )
        # 对创世区块执行工作量证明，确保其哈希满足难度要求
        self.proof_of_work(genesis)
        return genesis

    def load_chain(self):
        """从磁盘加载区块链，如果文件不存在或内容无效则重新创建创世区块。"""
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            # 如果保存目录不存在则创建目录
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.chain = [self.create_genesis_block()]
            self.save_chain()
            return

        with open(self.path, "r", encoding="utf-8") as file:
            try:
                chain_data = json.load(file)
                # 将存储的每个区块字典转换回 Block 对象
                self.chain = [Block.from_dict(block) for block in chain_data]
                if not self.chain:
                    # 如果文件中没有区块则创建创世区块并保存
                    self.chain = [self.create_genesis_block()]
                    self.save_chain()
            except (ValueError, json.JSONDecodeError):
                # 文件格式错误或内容损坏时，重新创建创世区块并保存
                self.chain = [self.create_genesis_block()]
                self.save_chain()

    def save_chain(self):
        """将当前区块链写入磁盘，保存为 JSON 格式。"""
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump([block.to_dict() for block in self.chain], file, indent=2, ensure_ascii=False)

    def get_last_block(self):
        """返回链中最后一个区块。"""
        return self.chain[-1]

    def proof_of_work(self, block):
        """执行简单的工作量证明。

        不断增加 nonce，直到区块哈希前缀满足难度要求。
        """
        target = "0" * POW_DIFFICULTY
        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.compute_hash()
        return block.hash

    def add_block(self, data):
        """创建新块、挖矿并追加到区块链中，然后持久化保存。"""
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
        """返回区块链中所有非创世区块的事件数据。"""
        return [block.to_dict() for block in self.chain if block.data.get("type") != "genesis"]

    def get_item_history(self, tracking_id):
        """根据跟踪 ID 返回该物品在区块链中的完整历史记录。"""
        items = []
        for block in self.chain:
            data = block.data
            if data.get("tracking_id") == tracking_id:
                item = block.to_dict()
                # 附加原始事件数据，便于前端或业务逻辑读取
                item["event"] = data
                items.append(item)
        return items

    def get_latest_item(self, tracking_id):
        """获取指定跟踪 ID 的最新一次区块事件。"""
        history = self.get_item_history(tracking_id)
        return history[-1] if history else None

    def is_valid_chain(self):
        """验证区块链的完整性。

        检查每个区块的前置哈希、哈希值一致性以及工作量证明是否有效。
        """
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
        """收集区块链中所有存在的 tracking_id 列表。"""
        records = {}
        for block in self.chain:
            data = block.data
            if data.get("tracking_id"):
                # 保证同一个 tracking_id 只出现一次，返回最后见到的区块
                records[data["tracking_id"]] = block
        return list(records.keys())
