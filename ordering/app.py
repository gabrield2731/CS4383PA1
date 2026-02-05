import os
import time
from flask import Flask, request, jsonify
import grpc

import pa1.inventory_pb2 as inv_pb2
import pa1.inventory_pb2_grpc as inv_grpc

app = Flask(__name__)

INVENTORY_HOST = os.environ.get("INVENTORY_HOST", "localhost")
INVENTORY_PORT = int(os.environ.get("INVENTORY_PORT", "50051"))


def build_items(items_json):
    items = []
    for it in items_json:
        name = str(it.get("name", "")).strip()
        qty = int(it.get("qty", 0))
        category = str(it.get("category", "")).strip().upper()

        if not name or qty <= 0:
            continue

        cat_map = {
            "BREAD": inv_pb2.BREAD,
            "DAIRY": inv_pb2.DAIRY,
            "MEAT": inv_pb2.MEAT,
            "PRODUCE": inv_pb2.PRODUCE,
            "PARTY": inv_pb2.PARTY,
        }
        cat_enum = cat_map.get(category, inv_pb2.CATEGORY_UNSPECIFIED)
        items.append(inv_pb2.Item(name=name, qty=qty, category=cat_enum))
    return items


def call_inventory(order_type, payload):
    request_id = str(payload.get("request_id", "")).strip()
    items_json = payload.get("items", [])

    items = build_items(items_json)
    if not request_id or len(items) == 0:
        return False, "BAD_REQUEST: request_id required and must include at least one valid item"

    req = inv_pb2.OrderRequest(
        request_id=request_id,
        order_type=order_type,
        items=items,
    )

    with grpc.insecure_channel(f"{INVENTORY_HOST}:{INVENTORY_PORT}") as channel:
        stub = inv_grpc.InventoryStub(channel)
        resp = stub.ProcessOrder(req)

    return resp.ok, resp.message


@app.post("/grocery_order")
def grocery_order():
    t0 = time.time()
    payload = request.get_json(silent=True) or {}
    ok, msg = call_inventory(inv_pb2.GROCERY_ORDER, payload)
    latency_ms = int((time.time() - t0) * 1000)
    return jsonify({"ok": ok, "message": msg, "latency_ms": latency_ms})


@app.post("/restock_order")
def restock_order():
    t0 = time.time()
    payload = request.get_json(silent=True) or {}
    ok, msg = call_inventory(inv_pb2.RESTOCK_ORDER, payload)
    latency_ms = int((time.time() - t0) * 1000)
    return jsonify({"ok": ok, "message": msg, "latency_ms": latency_ms})


if __name__ == "__main__":
    print(f"[Ordering] using Inventory at {INVENTORY_HOST}:{INVENTORY_PORT}", flush=True)
    app.run(host="0.0.0.0", port=8080, debug=True)
