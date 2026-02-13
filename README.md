## Components & Ports
- pricing_service: gRPC price calculator on 50052
- inventory_service: gRPC order coordinator on 50051; publishes robot tasks via ZMQ PUB on 5556
- robot_service: ZMQ SUB worker per aisle; reports back to inventory via gRPC
- ordering_service: Flask HTTP API on 5001; talks to inventory via gRPC; publishes analytics via ZMQ PUB on 5557
- client (Streamlit UI): browser UI on 8501
- analytics_service: ZMQ SUB consumer for analytics on 5557 (optional)

## Prereqs
- Python 3.10+ and `pip`
- Open ports 50052, 50051, 5001, 8501, 5556, 5557

## Setup
```bash
pip install -r requirements.txt
```

### Generate protobuf stubs (run after any .proto change)
```bash
cd proto
python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. \
  common.proto ordering_inventory.proto inventory_pricing.proto robot_inventory.proto
cd ..
```

## Run Order (each in its own terminal, repo root)
1) Pricing service (required by inventory)
```bash
python pricing_service/server.py
```
2) Inventory service (starts ZMQ PUB on 5556)
```bash
python inventory_service/server.py
```
3) Robot fleet (one per aisle; they SUB 5556 and report via gRPC)
```bash
for a in bread dairy meat produce party; do \
  python robot_service/robot.py --aisle $a --zmq-addr tcp://localhost:5556; \
  done
```
4) Ordering service (HTTP API + analytics PUB on 5557)
```bash
python ordering_service/app.py
```
5) Analytics subscriber (optional, prints stats)
```bash
python analytics_service/subscriber.py --zmq-addr tcp://localhost:5557
```
6) Client UI (browser at http://localhost:8501)
```bash
streamlit run client/app.py --server.enableXsrfProtection false --server.port 8501
```

## Notes
- Run everything from the repo root so Python finds `proto/` and `fbschemas/` modules.
- Inventory waits for results from all 5 robots (one per aisle); without them it times out after ~10s.
- The Streamlit app can place grocery orders and restock requests; both flow through Ordering → Inventory → Robots/ Pricing.

## Multi-VM Layout (4 VMs)
- VM1: `pricing_service` (gRPC 50052)
- VM2: `inventory_service` (gRPC 50051, ZMQ PUB 5556)
- VM3: `robot_service` instances (one per aisle, SUB 5556, gRPC back to inventory)
- VM4: `ordering_service` (HTTP 5001, analytics PUB 5557) + `client` Streamlit UI (8501); optionally `analytics_service` SUB on 5557
