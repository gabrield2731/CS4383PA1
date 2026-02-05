from concurrent import futures
import grpc
import time

import pa1.inventory_pb2 as inv_pb2
import pa1.inventory_pb2_grpc as inv_grpc


class InventoryServicer(inv_grpc.InventoryServicer):
    def ProcessOrder(self, request, context):
        if len(request.items) == 0:
            return inv_pb2.OrderReply(ok=False, message="BAD_REQUEST: must include at least one item")

        msg = (
            f"OK: received {len(request.items)} items for "
            f"{inv_pb2.OrderType.Name(request.order_type)} (request_id={request.request_id})"
        )
        print(msg, flush=True)
        return inv_pb2.OrderReply(ok=True, message=msg)


def serve(host="0.0.0.0", port=50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inv_grpc.add_InventoryServicer_to_server(InventoryServicer(), server)

    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"[Inventory] gRPC server listening on {host}:{port}", flush=True)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[Inventory] shutting down...", flush=True)
        server.stop(0)


if __name__ == "__main__":
    serve()
