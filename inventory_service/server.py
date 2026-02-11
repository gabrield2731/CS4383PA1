import sys
from pathlib import Path

# Ensure project root is on path when run as script (e.g. python inventory_service/server.py)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from concurrent import futures
import grpc

from proto import common_pb2
from proto import ordering_inventory_pb2_grpc
from proto import robot_inventory_pb2_grpc


class InventoryService(ordering_inventory_pb2_grpc.InventoryServiceServicer):
    def ProcessOrder(self, request, context):
        # Milestone 1: just reply with success
        return common_pb2.BasicReply(
            code=common_pb2.ReplyCode.OK,
            message="Inventory received request (Milestone 1 stub): OK",
        )


# Banner so you can confirm this file (with ReportTaskResult) is the one running
print("[inventory_service] server.py loaded (InventoryService + InventoryRobotService)")


class InventoryRobotService(robot_inventory_pb2_grpc.InventoryRobotServiceServicer):
    def ReportTaskResult(self, request, context):
        print(f"[inventory_service] ReportTaskResult: robot_id={request.robot_id} task_id={request.task_id}")
        return common_pb2.BasicReply(
            code=common_pb2.ReplyCode.OK,
            message=f"Robot {request.robot_id} task {request.task_id} result received",
        )


def serve(host="0.0.0.0", port=50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # Register both services (order does not matter)
    robot_inventory_pb2_grpc.add_InventoryRobotServiceServicer_to_server(InventoryRobotService(), server)
    ordering_inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryService(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"[inventory_service] gRPC listening on {host}:{port}")
    print("[inventory_service] Registered: InventoryService (ProcessOrder), InventoryRobotService (ReportTaskResult)")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
