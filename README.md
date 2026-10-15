# PyChain: blockchain tự xây bằng Python

Một blockchain nhỏ nhưng đủ các cơ chế cốt lõi của Bitcoin: proof-of-work, giao dịch ký số ECDSA, ví, mempool, phí giao dịch, phần thưởng đào, cây Merkle, kiểm tra toàn chuỗi và đồng thuận giữa nhiều node qua API FastAPI. Mục tiêu là hiểu tận gốc vì sao dữ liệu trên blockchain "không sửa được" và tiền không bị tiêu hai lần.

## 1. Chạy thử nhanh (không cần server)

```bash
pip install -r requirements.txt
python demo.py      # đào block, gửi tiền, thử gian lận, đo thời gian đào theo độ khó
pytest -q           # 13 test: chữ ký sai, sửa dữ liệu, tiêu quá số dư, replay, đồng thuận...
```

Kết quả `demo.py` (rút gọn):

```
4) Miner đào block, nhận thưởng 50 + phí 3
   Alice = 17   Miner = 53   Bob = 20   Carol = 10
5) Kẻ gian sửa số tiền Bob nhận trong block 2
   validate_chain(): block 2: hash không đúng với nội dung (dữ liệu bị sửa?)
6) Độ khó càng cao, đào càng lâu
   difficulty=3: nonce=    6,451    0.04s
   difficulty=4: nonce=   25,220    0.15s
   difficulty=5: nonce=3,070,306   19.93s
```

## 2. Chạy mạng 2 node

```bash
# Terminal 1 và 2
DIFFICULTY=3 DATA_FILE=node_5000.json uvicorn pychain.node:app --port 5000
DIFFICULTY=3 DATA_FILE=node_5001.json uvicorn pychain.node:app --port 5001

# Terminal 3: tạo ví, đào, gửi tiền (khóa bí mật chỉ nằm trên máy bạn, node chỉ nhận giao dịch đã ký)
python wallet_cli.py new alice
python wallet_cli.py new bob
curl -X POST localhost:5000/mine -H "content-type: application/json" \
     -d "{\"miner_address\": \"$(python wallet_cli.py address alice)\"}"
python wallet_cli.py send alice $(python wallet_cli.py address bob) 12 --fee 1
curl -X POST localhost:5000/mine -H "content-type: application/json" \
     -d "{\"miner_address\": \"$(python wallet_cli.py address alice)\"}"

# Node 5001 học chuỗi từ node 5000
curl -X POST localhost:5001/nodes/register -H "content-type: application/json" -d '{"nodes": ["http://localhost:5000"]}'
curl localhost:5001/nodes/resolve
python wallet_cli.py balance bob --node http://localhost:5001   # confirmed: 12
```

Tài liệu API tự sinh: mở `http://localhost:5000/docs`.

| Endpoint | Việc làm |
|---|---|
| `GET /` | chiều cao chuỗi, độ khó, số giao dịch chờ, danh sách peer |
| `GET /chain`, `GET /blocks/{i}` | toàn bộ chuỗi, một block |
| `POST /transactions` | nhận giao dịch đã ký, kiểm tra chữ ký và số dư rồi đưa vào mempool |
| `GET /mempool` | giao dịch đang chờ |
| `POST /mine` | đào block mới, thưởng 50 + tổng phí cho `miner_address` |
| `GET /balance/{addr}`, `GET /history/{addr}` | số dư đã xác nhận / khả dụng, lịch sử |
| `GET /validate` | kiểm tra lại toàn chuỗi |
| `POST /nodes/register`, `GET /nodes/resolve` | thêm peer, đồng thuận theo chuỗi hợp lệ dài nhất |

## 3. Thiết kế

| Thành phần | Cách làm | Vì sao |
|---|---|---|
| Ví | Khóa ECDSA secp256k1 (thư viện `cryptography`), địa chỉ = 40 ký tự đầu SHA-256(public key) | Giống Bitcoin: ai giữ khóa bí mật mới tiêu được tiền |
| Giao dịch | Ký phần nội dung (người gửi, nhận, số tiền, phí, thời điểm); `txid` = hash nội dung + chữ ký | Sửa một chữ số là chữ ký sai; gửi lại giao dịch cũ bị bắt vì trùng `txid` |
| Số tiền | Số nguyên | Tránh sai số số thực, giống satoshi |
| Block | Header gồm index, thời điểm, Merkle root, hash block trước, độ khó, nonce | Hash block phụ thuộc mọi giao dịch qua Merkle root |
| Proof-of-work | Tăng nonce đến khi SHA-256(header) bắt đầu bằng `difficulty` số 0 | Mỗi số 0 thêm vào tốn khoảng 16 lần công sức |
| Mempool | Kiểm tra số dư tính cả giao dịch đang chờ; đào ưu tiên phí cao, tối đa 100 giao dịch/block | Chặn tiêu hai lần trước khi vào block |
| Kiểm tra chuỗi | Genesis, index, liên kết hash, PoW, đúng 1 coinbase, thưởng không vượt mức, chữ ký, số dư không âm, không trùng giao dịch | Node không tin dữ liệu nhận từ peer |
| Đồng thuận | Nhận chuỗi hợp lệ dài hơn; giao dịch chờ còn hợp lệ được giữ lại | Quy tắc chuỗi dài nhất của Nakamoto (bản đơn giản) |

## 4. Giới hạn so với Bitcoin thật

- Dùng mô hình số dư tài khoản thay vì UTXO.
- Độ khó cố định, không tự điều chỉnh theo thời gian ra block; đồng thuận so độ dài chuỗi thay vì tổng công sức.
- Node không tự lan truyền giao dịch và block; peer phải gọi `/nodes/resolve`.
- `/mine` mở cho mọi người gọi, không có xác thực; chỉ dùng để học.

## 5. Cấu trúc

```
pychain/
  wallet.py     khóa, chữ ký, địa chỉ
  core.py       Transaction, Block, Blockchain (PoW, mempool, kiểm tra, đồng thuận, lưu file)
  node.py       API FastAPI cho 1 node
wallet_cli.py   ví dòng lệnh: tạo ví, ký và gửi giao dịch
demo.py         chạy toàn bộ luồng trong 1 file
tests/          13 test pytest
```
