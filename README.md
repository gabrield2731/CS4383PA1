# CS4383 PA1 — Automated Grocery Ordering System

A distributed grocery ordering system using gRPC (Protobuf), ZMQ (FlatBuffers), Flask, and Streamlit.

## Components & Ports

| Service              | Protocol       | Port         | Description                               |
| -------------------- | -------------- | ------------ | ----------------------------------------- |
| `pricing_service`    | gRPC           | 50052        | Per-unit price lookup, returns total cost |
| `inventory_service`  | gRPC + ZMQ PUB | 50051 / 5556 | Manages stock, coordinates robot tasks    |
| `robot_service` (x5) | ZMQ SUB + gRPC | —            | One per aisle, fetches/restocks items     |
| `ordering_service`   | HTTP + ZMQ PUB | 5001 / 5557  | REST API, routes orders to inventory      |
| `client` (Streamlit) | HTTP           | 8501         | Browser UI for placing orders             |
| `analytics_service`  | ZMQ SUB        | —            | Collects latency/success stats (optional) |

## Prerequisites

- Python 3.10+
- `pip` (or a virtualenv)
- Ports **50051, 50052, 5001, 5556, 5557, 8501** open between VMs

---

## Setup (each VM)

```bash
cd ~/CS4383PA1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Proto `__init__.py` (required on every VM)

The `proto/` package needs an `__init__.py` that exposes the generated modules.
If it's missing or empty, create it:

```bash
cat > proto/__init__.py << 'PYEOF'
import importlib

def __getattr__(name):
    if name in (
        "common_pb2", "common_pb2_grpc",
        "ordering_inventory_pb2", "ordering_inventory_pb2_grpc",
        "robot_inventory_pb2", "robot_inventory_pb2_grpc",
        "inventory_pricing_pb2", "inventory_pricing_pb2_grpc",
    ):
        mod = importlib.import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
PYEOF
```

### FlatBuffers import patch (required on every VM)

The generated FlatBuffers code may use absolute imports that don't work from
the project root. Fix with:

```bash
sed -i 's/from grocery\.fb\.ItemQty import ItemQty/from .ItemQty import ItemQty/g' \
  fbschemas/grocery/fb/FetchTask.py fbschemas/grocery/fb/RestockTask.py
```

Or run `python3 scripts/patch_fbs_imports.py`.

### Generate protobuf stubs (only after `.proto` changes)

```bash
cd proto
python -m grpc_tools.protoc -I . --python_out=. common.proto
python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. \
  ordering_inventory.proto inventory_pricing.proto robot_inventory.proto
cd ..
```

Then fix imports in the generated `*_pb2*.py` files (change
`import common_pb2 as` to `from . import common_pb2 as`, etc.).

### Generate FlatBuffers stubs (only after `.fbs` changes)

```bash
cd fbschemas
flatc --python -o . common.fbs fetch.fbs restock.fbs analytics.fbs
cd ..
```

---

## Single-VM Quick Start

Run everything from the **repo root** (`~/CS4383PA1`), each in its own terminal:

```bash
# 1. Pricing (required by inventory)
python -m pricing_service.server

# 2. Inventory (starts ZMQ PUB on 5556)
python -m inventory_service.server

# 3. All 5 robots (background)
python -m robot_service.robot --aisle bread &
python -m robot_service.robot --aisle dairy &
python -m robot_service.robot --aisle meat &
python -m robot_service.robot --aisle produce &
python -m robot_service.robot --aisle party &

# 4. Ordering (HTTP 5001 + analytics PUB 5557)
python -m ordering_service.app

# 5. Analytics (optional)
python -m analytics_service.subscriber

# 6. Streamlit client (browser at http://localhost:8501)
streamlit run client/app.py --server.port 8501
```

---

## Multi-VM Setup (4 VMs)

### VM assignments

| VM      | IP           | Services                    |
| ------- | ------------ | --------------------------- |
| **VM1** | 172.16.5.77  | Ordering + Streamlit client |
| **VM2** | 172.16.5.69  | Inventory                   |
| **VM3** | 172.16.5.214 | Pricing + Analytics         |
| **VM4** | 172.16.5.58  | All 5 robots                |

### Network connections

| From → To                         | Address                 | Protocol |
| --------------------------------- | ----------------------- | -------- |
| Ordering (VM1) → Inventory (VM2)  | 172.16.5.69:50051       | gRPC     |
| Inventory (VM2) → Pricing (VM3)   | 172.16.5.214:50052      | gRPC     |
| Robots (VM4) → Inventory (VM2)    | 172.16.5.69:50051       | gRPC     |
| Robots (VM4) → Inventory (VM2)    | tcp://172.16.5.69:5556  | ZMQ SUB  |
| Analytics (VM3) → Ordering (VM1)  | tcp://172.16.5.77:5557  | ZMQ SUB  |
| Client (browser) → Ordering (VM1) | http://172.16.5.77:5001 | HTTP     |

These IPs are hardcoded in the service source files (`ordering_service/app.py`,
`inventory_service/server.py`, `robot_service/robot.py`, `analytics_service/subscriber.py`,
`client/app.py`). Change them if your VMs have different IPs.

### Setup on each VM

On **every VM**, clone the repo and install dependencies:

```bash
cd ~/CS4383PA1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then apply the proto `__init__.py` and FlatBuffers patches described above.

### Start order

Start services in this order so dependencies are ready:

#### 1. VM2 (172.16.5.69) — Inventory

```bash
cd ~/CS4383PA1
source .venv/bin/activate
python -m inventory_service.server
```

Listens on gRPC 50051 and ZMQ PUB 5556.

#### 2. VM3 (172.16.5.214) — Pricing + Analytics

**Terminal 1 — Pricing:**

```bash
cd ~/CS4383PA1
source .venv/bin/activate
python -m pricing_service.server
```

Listens on gRPC 50052.

**Terminal 2 — Analytics:**

```bash
cd ~/CS4383PA1
source .venv/bin/activate
python -m analytics_service.subscriber
```

Subscribes to VM1's ZMQ analytics stream (tcp://172.16.5.77:5557).

#### 3. VM4 (172.16.5.58) — All 5 robots

```bash
cd ~/CS4383PA1
source .venv/bin/activate
python -m robot_service.robot --aisle bread &
python -m robot_service.robot --aisle dairy &
python -m robot_service.robot --aisle meat &
python -m robot_service.robot --aisle produce &
python -m robot_service.robot --aisle party &
wait
```

Robots subscribe to VM2's ZMQ (tcp://172.16.5.69:5556) and report results via
gRPC to VM2 (172.16.5.69:50051).

To stop all robots: `pkill -f "robot_service.robot"`

#### 4. VM1 (172.16.5.77) — Ordering + Streamlit

**Terminal 1 — Ordering:**

```bash
cd ~/CS4383PA1
source .venv/bin/activate
python -m ordering_service.app
```

Listens on HTTP 5001 and ZMQ PUB 5557.

**Terminal 2 — Streamlit:**

```bash
cd ~/CS4383PA1
source .venv/bin/activate
streamlit run client/app.py --server.port 8501
```

Open **http://172.16.5.77:8501** in your browser.

---

## Pricing Model

Fixed per-unit prices (see `pricing_service/server.py`). Total = sum of
(unit_price × qty) for each item. Only charged for fulfilled quantities
(capped to available stock).

## Inventory Behavior

- Starts with **100 units** of each of the 25 items.
- **Grocery orders** (FETCH): requested quantities are capped to available stock.
  Items with 0 stock return qty 0 in the response.
- **Restock orders**: add to current stock (no cap).
- Stock persists in memory; restarting the inventory service resets to 100.

## Notes

- Run everything from the **repo root** so Python finds `proto/` and `fbschemas/`.
- Inventory waits up to 10s for all 5 robots to respond (barrier). Without all 5
  running, orders will timeout with partial results.
- Robots retry gRPC calls up to 3 times and survive errors (they don't crash on
  network hiccups).
- All services use insecure channels (no TLS). Use only in a controlled environment.
