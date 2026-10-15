"""Node blockchain chạy bằng FastAPI.

Chạy 1 node:   uvicorn pychain.node:app --port 5000
Chạy node khác: PORT=5001 DATA_FILE=node_5001.json uvicorn pychain.node:app --port 5001
"""
import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .core import Block, Blockchain, Transaction


class TxIn(BaseModel):
    sender: str
    recipient: str
    amount: int
    fee: int = 0
    timestamp: float
    public_key: str
    signature: str


class MineIn(BaseModel):
    miner_address: str


class NodesIn(BaseModel):
    nodes: list[str]


def http_fetch_chain(url: str) -> list[dict]:
    return httpx.get(f"{url.rstrip('/')}/chain", timeout=10).json()["chain"]


def create_app(difficulty: int = 4, data_file: str | None = None, fetch_chain=http_fetch_chain) -> FastAPI:
    app = FastAPI(title="PyChain node", version="1.0")
    bc = Blockchain.load(data_file) if data_file and os.path.exists(data_file) else Blockchain(difficulty)
    peers: set[str] = set()

    def persist():
        if data_file:
            bc.save(data_file)

    @app.get("/")
    def info():
        return {"height": len(bc.chain) - 1, "difficulty": bc.difficulty, "last_hash": bc.last_block.hash,
                "mempool": len(bc.mempool), "peers": sorted(peers)}

    @app.get("/chain")
    def get_chain():
        return {"length": len(bc.chain), "chain": [b.to_dict() for b in bc.chain]}

    @app.get("/blocks/{index}")
    def get_block(index: int):
        if not 0 <= index < len(bc.chain):
            raise HTTPException(404, "Không có block này")
        return bc.chain[index].to_dict()

    @app.get("/mempool")
    def get_mempool():
        return [{"txid": t.txid, **t.to_dict()} for t in bc.mempool]

    @app.get("/balance/{address}")
    def get_balance(address: str):
        return {"address": address, "confirmed": bc.balance(address),
                "available": bc.balance(address, include_mempool=True)}

    @app.get("/history/{address}")
    def get_history(address: str):
        return bc.history(address)

    @app.post("/transactions", status_code=201)
    def post_transaction(tx: TxIn):
        # Node chỉ nhận giao dịch ĐÃ KÝ: khóa bí mật không bao giờ rời khỏi máy người dùng
        try:
            txid = bc.add_transaction(Transaction.from_dict(tx.model_dump()))
        except ValueError as e:
            raise HTTPException(400, str(e))
        persist()
        return {"txid": txid, "message": "Đã vào mempool, chờ đào"}

    @app.post("/mine", status_code=201)
    def mine(body: MineIn):
        block = bc.mine_pending(body.miner_address)
        persist()
        return block.to_dict()

    @app.get("/validate")
    def validate():
        error = bc.validate_chain(bc.chain)
        return {"valid": error is None, "error": error}

    @app.post("/nodes/register", status_code=201)
    def register_nodes(body: NodesIn):
        peers.update(n.rstrip("/") for n in body.nodes)
        return {"peers": sorted(peers)}

    @app.get("/nodes/resolve")
    def resolve():
        """Hỏi tất cả peer, nhận chuỗi hợp lệ dài nhất (longest valid chain rule)."""
        replaced, errors = False, {}
        for url in sorted(peers):
            try:
                chain = [Block.from_dict(b) for b in fetch_chain(url)]
            except Exception as e:  # peer tắt hoặc trả dữ liệu hỏng
                errors[url] = str(e)
                continue
            if bc.replace_chain(chain):
                replaced = True
        if replaced:
            persist()
        return {"replaced": replaced, "length": len(bc.chain), "errors": errors}

    app.state.blockchain = bc
    return app


app = create_app(difficulty=int(os.getenv("DIFFICULTY", "4")), data_file=os.getenv("DATA_FILE", "chain.json"))
