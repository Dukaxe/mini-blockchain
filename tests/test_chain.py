import pytest

from pychain import COINBASE, MINING_REWARD, Blockchain, Transaction, Wallet

DIFF = 2  # độ khó thấp cho test chạy nhanh


@pytest.fixture
def setup():
    bc = Blockchain(DIFF)
    alice, bob, miner = Wallet(), Wallet(), Wallet()
    bc.mine_pending(alice.address)  # alice nhận 50 tiền thưởng
    return bc, alice, bob, miner


def test_genesis_is_identical_across_nodes():
    assert Blockchain(DIFF).chain[0].hash == Blockchain(DIFF).chain[0].hash


def test_mining_reward_and_pow(setup):
    bc, alice, *_ = setup
    assert bc.balance(alice.address) == MINING_REWARD
    assert bc.last_block.hash.startswith("0" * DIFF)
    assert bc.validate_chain(bc.chain) is None


def test_signed_transfer_and_fee_goes_to_miner(setup):
    bc, alice, bob, miner = setup
    bc.add_transaction(Transaction(alice.address, bob.address, 20, fee=2).sign(alice))
    bc.mine_pending(miner.address)
    assert bc.balance(alice.address) == 28
    assert bc.balance(bob.address) == 20
    assert bc.balance(miner.address) == MINING_REWARD + 2
    assert not bc.mempool


def test_reject_wrong_signature(setup):
    bc, alice, bob, _ = setup
    tx = Transaction(alice.address, bob.address, 10)
    tx.public_key = bob.public_key_hex
    tx.signature = bob.sign(tx.payload())
    with pytest.raises(ValueError, match="public key"):
        bc.add_transaction(tx)


def test_reject_tampered_amount(setup):
    bc, alice, bob, _ = setup
    tx = Transaction(alice.address, bob.address, 10).sign(alice)
    tx.amount = 40  # sửa sau khi ký
    with pytest.raises(ValueError, match="chữ ký"):
        bc.add_transaction(tx)


def test_reject_overspend_including_mempool(setup):
    bc, alice, bob, _ = setup
    bc.add_transaction(Transaction(alice.address, bob.address, 30).sign(alice))
    with pytest.raises(ValueError, match="Không đủ số dư"):
        bc.add_transaction(Transaction(alice.address, bob.address, 30).sign(alice))


def test_reject_replay(setup):
    bc, alice, bob, miner = setup
    tx = Transaction(alice.address, bob.address, 5).sign(alice)
    bc.add_transaction(tx)
    bc.mine_pending(miner.address)
    with pytest.raises(ValueError, match="replay"):
        bc.add_transaction(Transaction.from_dict(tx.to_dict()))


def test_reject_coinbase_from_user(setup):
    bc, alice, *_ = setup
    with pytest.raises(ValueError):
        bc.add_transaction(Transaction(COINBASE, alice.address, 1000))


def test_tampering_breaks_chain(setup):
    bc, alice, bob, miner = setup
    bc.add_transaction(Transaction(alice.address, bob.address, 10).sign(alice))
    bc.mine_pending(miner.address)
    bc.chain[1].transactions[0].amount = 1_000_000  # sửa thưởng block 1
    assert "hash" in bc.validate_chain(bc.chain)


def test_remined_tampered_block_breaks_link(setup):
    bc, alice, bob, miner = setup
    bc.mine_pending(miner.address)
    bc.chain[1].transactions[0].amount = 1_000_000
    bc.chain[1].mine()  # kẻ gian đào lại block 1 -> block 2 không còn trỏ đúng
    assert bc.validate_chain(bc.chain) is not None


def test_consensus_longest_valid_chain(setup):
    bc, alice, bob, miner = setup
    other = Blockchain(DIFF)
    for _ in range(3):
        other.mine_pending(miner.address)
    assert bc.replace_chain(other.chain)
    assert len(bc.chain) == 4
    assert not bc.replace_chain(Blockchain(DIFF).chain)  # chuỗi ngắn hơn bị từ chối


def test_save_and_load(tmp_path, setup):
    bc, alice, bob, _ = setup
    bc.add_transaction(Transaction(alice.address, bob.address, 7).sign(alice))
    path = tmp_path / "chain.json"
    bc.save(path)
    loaded = Blockchain.load(path)
    assert loaded.last_block.hash == bc.last_block.hash
    assert len(loaded.mempool) == 1
