"""Ví dòng lệnh: tạo ví, xem số dư, ký và gửi giao dịch tới một node.

python wallet_cli.py new alice                 # tạo ví, lưu khóa vào wallets/alice.pem
python wallet_cli.py address alice
python wallet_cli.py balance alice --node http://localhost:5000
python wallet_cli.py send alice <địa_chỉ_nhận> 10 --fee 1 --node http://localhost:5000
"""
import argparse
import os
import sys

import httpx

from pychain import Transaction, Wallet

WALLET_DIR = "wallets"


def load_wallet(name: str) -> Wallet:
    path = os.path.join(WALLET_DIR, f"{name}.pem")
    if not os.path.exists(path):
        sys.exit(f"Chưa có ví '{name}'. Tạo bằng: python wallet_cli.py new {name}")
    with open(path) as f:
        return Wallet.from_pem(f.read())


def main():
    p = argparse.ArgumentParser(description="PyChain wallet")
    p.add_argument("command", choices=["new", "address", "balance", "send"])
    p.add_argument("name")
    p.add_argument("recipient", nargs="?")
    p.add_argument("amount", nargs="?", type=int)
    p.add_argument("--fee", type=int, default=0)
    p.add_argument("--node", default="http://localhost:5000")
    a = p.parse_args()

    if a.command == "new":
        os.makedirs(WALLET_DIR, exist_ok=True)
        w = Wallet()
        with open(os.path.join(WALLET_DIR, f"{a.name}.pem"), "w") as f:
            f.write(w.to_pem())
        print(f"Đã tạo ví {a.name}: {w.address}")
        return

    w = load_wallet(a.name)
    if a.command == "address":
        print(w.address)
    elif a.command == "balance":
        print(httpx.get(f"{a.node}/balance/{w.address}").json())
    elif a.command == "send":
        if not a.recipient or not a.amount:
            sys.exit("Cần: send <tên_ví> <địa_chỉ_nhận> <số_tiền>")
        tx = Transaction(w.address, a.recipient, a.amount, a.fee).sign(w)  # ký tại máy
        r = httpx.post(f"{a.node}/transactions", json=tx.to_dict())
        print(r.status_code, r.json())


if __name__ == "__main__":
    main()
