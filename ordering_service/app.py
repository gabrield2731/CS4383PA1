import time
from typing import Dict, Any, List

import grpc
from flask import Flask, request, jsonify

from proto import common_pb2 as pb2
from proto import ordering_inventory_pb2_grpc as inv_grpc

app = Flask(__name__)

INVENTORY_GRPC_ADDR = "localhost:50051"


def _items_from_json(arr: Any) -> List[pb2.ItemQty]:
    if not isinstance(arr, list):
        return []
    out = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        item = str(x.get("item", "")).strip()
        qty = x.get("qty", 0)
        try:
            qty = float(qty)
        except Exception:
            qty = 0.0
        if item and qty > 0:
            out.append(pb2.ItemQty(item=item, qty=qty))
    return out


def _order_from_json(order_json: Dict[str, Any]) -> pb2.Order:
    # Expecting: order = { "bread": [{item,qty}], "produce": [...], ... }
    return pb2.Order(
        bread=pb2.AisleItems(items=_items_from_json(order_json.get("bread"))),
        meat=pb2.AisleItems(items=_items_from_json(order_json.get("meat"))),
        produce=pb2.AisleItems(items=_items_from_json(order_json.get("produce"))),
        dairy=pb2.AisleItems(items=_items_from_json(order_json.get("dairy"))),
        party=pb2.AisleItems(items=_items_from_json(order_json.get("party"))),
    )


def _count_items(o: pb2.Order) -> int:
    return (
        len(o.bread.items)
        + len(o.meat.items)
        + len(o.produce.items)
        + len(o.dairy.items)
        + len(o.party.items)
    )


def _reply_code_name(code) -> str:
    """Get string name for ReplyCode enum (works for enum member or int from gRPC)."""
    if getattr(code, "name", None):
        return code.name
    names = {0: "REPLY_CODE_UNSPECIFIED", 1: "OK", 2: "BAD_REQUEST", 3: "INTERNAL_ERROR"}
    return names.get(int(code), str(code))


def _call_inventory(req_pb: pb2.OrderRequest) -> pb2.BasicReply:
    with grpc.insecure_channel(INVENTORY_GRPC_ADDR) as channel:
        stub = inv_grpc.InventoryServiceStub(channel)
        # Timeout must exceed the inventory barrier timeout (10s) + buffer
        return stub.ProcessOrder(req_pb, timeout=20)


@app.post("/api/order")
def grocery_order():
    # HTTP-JSON between client and Ordering :contentReference[oaicite:8]{index=8}
    data = request.get_json(silent=True) or {}
    customer_id = str(data.get("customer_id", "")).strip()
    order_json = data.get("order", {})

    req_pb = pb2.OrderRequest(
        message_type=pb2.MessageType.GROCERY_ORDER,
        customer_id=customer_id,
        timestamp_ms=int(time.time() * 1000),
        order=_order_from_json(order_json if isinstance(order_json, dict) else {}),
    )

    if not customer_id:
        return jsonify({"code": "BAD_REQUEST", "message": "customer_id required"}), 400
    if _count_items(req_pb.order) == 0:
        # Spec: cannot be empty :contentReference[oaicite:9]{index=9}
        return jsonify({"code": "BAD_REQUEST", "message": "order cannot be empty"}), 400

    # Ordering -> Inventory via gRPC/Protobuf :contentReference[oaicite:10]{index=10}
    resp = _call_inventory(req_pb)

    http_code = 200 if resp.code == pb2.ReplyCode.OK else 400
    code_name = _reply_code_name(resp.code)
    items_list = [{"item": it.item, "qty": it.qty} for it in resp.items]
    return jsonify({"code": code_name, "message": resp.message, "items": items_list}), http_code


@app.post("/api/restock")
def restock_order():
    data = request.get_json(silent=True) or {}
    supplier_id = str(data.get("supplier_id", "")).strip()
    order_json = data.get("order", {})

    req_pb = pb2.OrderRequest(
        message_type=pb2.MessageType.RESTOCK_ORDER,
        supplier_id=supplier_id,
        timestamp_ms=int(time.time() * 1000),
        order=_order_from_json(order_json if isinstance(order_json, dict) else {}),
    )

    if not supplier_id:
        return jsonify({"code": "BAD_REQUEST", "message": "supplier_id required"}), 400
    if _count_items(req_pb.order) == 0:
        return jsonify({"code": "BAD_REQUEST", "message": "restock order cannot be empty"}), 400

    resp = _call_inventory(req_pb)

    http_code = 200 if resp.code == pb2.ReplyCode.OK else 400
    code_name = _reply_code_name(resp.code)
    items_list = [{"item": it.item, "qty": it.qty} for it in resp.items]
    return jsonify({"code": code_name, "message": resp.message, "items": items_list}), http_code


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # Flask web server required :contentReference[oaicite:11]{index=11}
    app.run(host="0.0.0.0", port=5001, debug=True)
