from concurrent import futures
import grpc

from proto import common_pb2
from proto import ordering_inventory_pb2_grpc


class InventoryService(ordering_inventory_pb2_grpc.InventoryServiceServicer):
    def ProcessOrder(self, request, context):
        # Milestone 1: just reply with success
        return common_pb2.BasicReply(
            code=common_pb2.ReplyCode.OK,
            message="Inventory received request (Milestone 1 stub): OK",
        )


def serve(host="0.0.0.0", port=50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ordering_inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryService(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"[inventory_service] gRPC listening on {host}:{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
