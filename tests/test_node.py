from fastapi.testclient import TestClient

from pychain import Transaction, Wallet
from pychain.node import create_app

DIFF = 2


def make_network():
    clients = {}
    fetch = lambda url: clients[url].get("/chain").json()["chain"]
    for url in ["http://a", "http://b"]:
        clients[url] = TestClient(create_app(DIFF, fetch_chain=fetch))
    return clients


def test_api_flow_and_consensus():
    net = make_network()
    a, b = net["http://a"], net["http://b"]
    alice, bob = Wallet(), Wallet()

    a.post("/mine", json={"miner_address": alice.address})
    tx = Transaction(alice.address, bob.address, 15, fee=1).sign(alice)
    r = a.post("/transactions", json=tx.to_dict())
    assert r.status_code == 201
    assert a.get(f"/balance/{alice.address}").json()["available"] == 34

    bad = Transaction(alice.address, bob.address, 999).sign(alice)
    assert a.post("/transactions", json=bad.to_dict()).status_code == 400

    a.post("/mine", json={"miner_address": alice.address})
    assert a.get(f"/balance/{bob.address}").json()["confirmed"] == 15
    assert a.get("/validate").json()["valid"]

    b.post("/nodes/register", json={"nodes": ["http://a"]})
    r = b.get("/nodes/resolve").json()
    assert r["replaced"] and r["length"] == 3
    assert b.get(f"/balance/{bob.address}").json()["confirmed"] == 15
