"""Lõi blockchain: Transaction, Block, Blockchain.

Đơn vị tiền là số nguyên (giống satoshi) để tránh sai số số thực.
"""
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field

from .wallet import Wallet, address_from_public_key, verify_signature

COINBASE = "COINBASE"      # "người gửi" của giao dịch thưởng đào block
MINING_REWARD = 50         # phần thưởng mỗi block
MAX_TX_PER_BLOCK = 100     # giới hạn số giao dịch trong 1 block (không tính coinbase)
GENESIS_TIME = 1_700_000_000.0


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------- Transaction
@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    fee: int = 0
    timestamp: float = field(default_factory=time.time)
    public_key: str = ""
    signature: str = ""

    def payload(self) -> str:
        """Phần nội dung được ký (không gồm chữ ký)."""
        return json.dumps(
            {"sender": self.sender, "recipient": self.recipient, "amount": self.amount,
             "fee": self.fee, "timestamp": self.timestamp},
            sort_keys=True,
        )

    @property
    def txid(self) -> str:
        return sha256(self.payload() + self.signature)

    @property
    def is_coinbase(self) -> bool:
        return self.sender == COINBASE

    def sign(self, wallet: Wallet) -> "Transaction":
        if wallet.address != self.sender:
            raise ValueError("Ví ký không phải chủ của địa chỉ gửi")
        self.public_key = wallet.public_key_hex
        self.signature = wallet.sign(self.payload())
        return self

    def check(self) -> str | None:
        """Trả về lý do lỗi (chuỗi) hoặc None nếu hợp lệ về mặt hình thức và chữ ký."""
        if not isinstance(self.amount, int) or not isinstance(self.fee, int):
            return "amount và fee phải là số nguyên"
        if self.amount <= 0 or self.fee < 0:
            return "amount phải > 0 và fee phải >= 0"
        if self.sender == self.recipient:
            return "không thể tự gửi cho chính mình"
        if self.is_coinbase:
            return None if self.fee == 0 else "coinbase không có phí"
        if address_from_public_key(self.public_key) != self.sender:
            return "public key không khớp địa chỉ người gửi"
        if not verify_signature(self.public_key, self.payload(), self.signature):
            return "chữ ký không hợp lệ"
        return None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def merkle_root(txids: list[str]) -> str:
    """Gộp hash từng cặp cho đến khi còn 1 hash (giống cây Merkle của Bitcoin)."""
    if not txids:
        return sha256("")
    level = txids[:]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [sha256(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


# ---------------------------------------------------------------------- Block
@dataclass
class Block:
    index: int
    timestamp: float
    transactions: list[Transaction]
    previous_hash: str
    difficulty: int
    nonce: int = 0
    hash: str = ""

    @property
    def merkle_root(self) -> str:
        return merkle_root([tx.txid for tx in self.transactions])

    def compute_hash(self) -> str:
        header = {"index": self.index, "timestamp": self.timestamp, "merkle_root": self.merkle_root,
                  "previous_hash": self.previous_hash, "difficulty": self.difficulty, "nonce": self.nonce}
        return sha256(json.dumps(header, sort_keys=True))

    def mine(self) -> "Block":
        """Proof-of-work: tăng nonce đến khi hash bắt đầu bằng `difficulty` số 0."""
        target = "0" * self.difficulty
        root = self.merkle_root  # tính 1 lần cho nhanh
        base = {"index": self.index, "timestamp": self.timestamp, "merkle_root": root,
                "previous_hash": self.previous_hash, "difficulty": self.difficulty}
        self.nonce = 0
        while True:
            h = sha256(json.dumps({**base, "nonce": self.nonce}, sort_keys=True))
            if h.startswith(target):
                self.hash = h
                return self
            self.nonce += 1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["transactions"] = [tx.to_dict() for tx in self.transactions]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(index=d["index"], timestamp=d["timestamp"],
                   transactions=[Transaction.from_dict(t) for t in d["transactions"]],
                   previous_hash=d["previous_hash"], difficulty=d["difficulty"],
                   nonce=d["nonce"], hash=d["hash"])


# ----------------------------------------------------------------- Blockchain
class Blockchain:
    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty
        self.chain: list[Block] = [self.genesis_block(difficulty)]
        self.mempool: list[Transaction] = []

    @staticmethod
    def genesis_block(difficulty: int) -> Block:
        # Mọi node cùng difficulty tạo ra đúng một genesis block giống hệt nhau
        return Block(0, GENESIS_TIME, [], "0" * 64, difficulty).mine()

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    # ---------- số dư
    @staticmethod
    def _apply(balances: dict, tx: Transaction) -> None:
        if not tx.is_coinbase:
            balances[tx.sender] = balances.get(tx.sender, 0) - tx.amount - tx.fee
        balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount

    def balances(self, include_mempool: bool = False) -> dict[str, int]:
        result: dict[str, int] = {}
        for block in self.chain:
            for tx in block.transactions:
                self._apply(result, tx)
        if include_mempool:
            for tx in self.mempool:
                self._apply(result, tx)
        return result

    def balance(self, address: str, include_mempool: bool = False) -> int:
        return self.balances(include_mempool).get(address, 0)

    def history(self, address: str) -> list[dict]:
        rows = []
        for block in self.chain:
            for tx in block.transactions:
                if address in (tx.sender, tx.recipient):
                    rows.append({"block": block.index, "txid": tx.txid, **tx.to_dict()})
        return rows

    # ---------- giao dịch
    def known_txids(self) -> set[str]:
        return {tx.txid for b in self.chain for tx in b.transactions} | {tx.txid for tx in self.mempool}

    def add_transaction(self, tx: Transaction) -> str:
        """Kiểm tra rồi đưa giao dịch vào mempool. Trả về txid, lỗi thì raise ValueError."""
        if tx.is_coinbase:
            raise ValueError("Không được gửi giao dịch coinbase vào mempool")
        error = tx.check()
        if error:
            raise ValueError(error)
        if tx.txid in self.known_txids():
            raise ValueError("Giao dịch đã tồn tại (chống gửi lại - replay)")
        available = self.balance(tx.sender, include_mempool=True)  # tính cả khoản đang chờ
        if available < tx.amount + tx.fee:
            raise ValueError(f"Không đủ số dư: có {available}, cần {tx.amount + tx.fee}")
        self.mempool.append(tx)
        return tx.txid

    # ---------- đào block
    def mine_pending(self, miner_address: str) -> Block:
        # Ưu tiên giao dịch phí cao, giống thợ đào thật
        selected = sorted(self.mempool, key=lambda t: t.fee, reverse=True)[:MAX_TX_PER_BLOCK]
        fees = sum(t.fee for t in selected)
        reward = Transaction(COINBASE, miner_address, MINING_REWARD + fees,
                             timestamp=time.time())
        block = Block(len(self.chain), time.time(), [reward] + selected,
                      self.last_block.hash, self.difficulty).mine()
        self.chain.append(block)
        mined = {t.txid for t in selected}
        self.mempool = [t for t in self.mempool if t.txid not in mined]
        return block

    # ---------- kiểm tra toàn chuỗi
    def validate_chain(self, chain: list[Block]) -> str | None:
        """Trả về lý do lỗi hoặc None nếu chuỗi hợp lệ."""
        if not chain or chain[0].to_dict() != self.genesis_block(self.difficulty).to_dict():
            return "genesis block không khớp"
        balances: dict[str, int] = {}
        seen: set[str] = set()
        for i, block in enumerate(chain[1:], start=1):
            prev = chain[i - 1]
            if block.index != i:
                return f"block {i}: sai index"
            if block.previous_hash != prev.hash:
                return f"block {i}: previous_hash không khớp block trước"
            if block.difficulty != self.difficulty:
                return f"block {i}: sai độ khó"
            if block.hash != block.compute_hash():
                return f"block {i}: hash không đúng với nội dung (dữ liệu bị sửa?)"
            if not block.hash.startswith("0" * block.difficulty):
                return f"block {i}: chưa đạt proof-of-work"
            txs = block.transactions
            if not txs or not txs[0].is_coinbase or any(t.is_coinbase for t in txs[1:]):
                return f"block {i}: phải có đúng 1 coinbase ở đầu"
            if len(txs) - 1 > MAX_TX_PER_BLOCK:
                return f"block {i}: quá nhiều giao dịch"
            fees = sum(t.fee for t in txs[1:])
            if txs[0].amount > MINING_REWARD + fees:
                return f"block {i}: thưởng coinbase vượt mức"
            for tx in txs:
                error = tx.check()
                if error:
                    return f"block {i}: {error}"
                if tx.txid in seen:
                    return f"block {i}: giao dịch bị lặp"
                seen.add(tx.txid)
                self._apply(balances, tx)
                if not tx.is_coinbase and balances[tx.sender] < 0:
                    return f"block {i}: {tx.sender[:8]}… tiêu quá số dư"
        return None

    def replace_chain(self, new_chain: list[Block]) -> bool:
        """Quy tắc đồng thuận: nhận chuỗi hợp lệ dài hơn chuỗi hiện tại."""
        if len(new_chain) <= len(self.chain) or self.validate_chain(new_chain):
            return False
        self.chain = new_chain
        # Giữ lại các giao dịch chưa vào chuỗi mới và vẫn còn hợp lệ
        old_pool, self.mempool = self.mempool, []
        for tx in old_pool:
            try:
                self.add_transaction(tx)
            except ValueError:
                pass
        return True

    # ---------- lưu / nạp
    def to_dict(self) -> dict:
        return {"difficulty": self.difficulty, "chain": [b.to_dict() for b in self.chain],
                "mempool": [t.to_dict() for t in self.mempool]}

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=1)

    @classmethod
    def load(cls, path: str) -> "Blockchain":
        with open(path) as f:
            d = json.load(f)
        bc = cls(d["difficulty"])
        chain = [Block.from_dict(b) for b in d["chain"]]
        error = bc.validate_chain(chain)
        if error:
            raise ValueError(f"File chuỗi không hợp lệ: {error}")
        bc.chain = chain
        for t in d.get("mempool", []):
            try:
                bc.add_transaction(Transaction.from_dict(t))
            except ValueError:
                pass  # bỏ giao dịch chờ không còn hợp lệ
        return bc
