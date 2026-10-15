"""Chạy thử toàn bộ blockchain trong 1 file, không cần mở server.

python demo.py
"""
import time

from pychain import Blockchain, Transaction, Wallet


def short(addr: str) -> str:
    return addr[:8] + "…"


def main():
    bc = Blockchain(difficulty=4)
    alice, bob, carol, miner = Wallet(), Wallet(), Wallet(), Wallet()
    names = {alice.address: "Alice", bob.address: "Bob", carol.address: "Carol", miner.address: "Miner"}
    print("Genesis:", bc.chain[0].hash[:20], "…")

    print("\n1) Alice đào block đầu tiên để có tiền")
    b = bc.mine_pending(alice.address)
    print(f"   block {b.index}: nonce={b.nonce:,}, hash={b.hash[:20]}…")

    print("\n2) Alice ký và gửi 2 giao dịch")
    bc.add_transaction(Transaction(alice.address, bob.address, 20, fee=2).sign(alice))
    bc.add_transaction(Transaction(alice.address, carol.address, 10, fee=1).sign(alice))
    print(f"   mempool: {len(bc.mempool)} giao dịch")

    print("\n3) Alice thử tiêu quá số dư")
    try:
        bc.add_transaction(Transaction(alice.address, bob.address, 30).sign(alice))
    except ValueError as e:
        print("   bị từ chối:", e)

    print("\n4) Miner đào block, nhận thưởng 50 + phí 3")
    b = bc.mine_pending(miner.address)
    print(f"   block {b.index}: {len(b.transactions)} giao dịch, nonce={b.nonce:,}")
    for addr, bal in bc.balances().items():
        print(f"   {names[addr]:<6} {short(addr)} = {bal}")

    print("\n5) Kẻ gian sửa số tiền Bob nhận trong block 2")
    bc.chain[2].transactions[1].amount = 2000
    print("   validate_chain():", bc.validate_chain(bc.chain))
    bc.chain[2].transactions[1].amount = 20
    print("   sau khi hoàn lại:", bc.validate_chain(bc.chain) or "hợp lệ")

    print("\n6) Độ khó càng cao, đào càng lâu (mỗi số 0 thêm vào ~ x16 số lần thử)")
    for d in range(1, 5):  # difficulty=5 mất khoảng 20 giây
        t0 = time.time()
        blk = Blockchain.genesis_block(d)
        print(f"   difficulty={d}: nonce={blk.nonce:>9,}  {time.time() - t0:6.2f}s")


if __name__ == "__main__":
    main()
