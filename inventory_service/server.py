from concurrent import futures
import sys
import time
import grpc
import zmq
import flatbuffers

from proto import common_pb2 as pb2
from proto import ordering_inventory_pb2_grpc as inv_from_ordering_grpc
from proto import robot_inventory_pb2_grpc as inv_from_robot_grpc
from proto import robot_inventory_pb2 as robot_pb2

# Flatbuffers generated python (your project uses fbschemas/)
from fbschemas.grocery.fb import FetchTask, RestockTask, TaskType
from fbschemas.grocery.fb import ItemQty as FbItemQty


# ----------------------------
# Flatbuffers builders
# ----------------------------
def build_fetch_payload(task_id: str, items: list[tuple[str, float]]) -> bytes:
    b = flatbuffers.Builder(1024)

    item_offsets = []
    for name, qty in items:
        name_off = b.CreateString(name)
        FbItemQty.Start(b)
        FbItemQty.AddItem(b, name_off)
        FbItemQty.AddQty(b, float(qty))
        item_offsets.append(FbItemQty.End(b))

    FetchTask.StartItemsVector(b, len(item_offsets))
    for off in reversed(item_offsets):
        b.PrependUOffsetTRelative(off)
    items_vec = b.EndVector()

    task_id_off = b.CreateString(task_id)
    FetchTask.Start(b)
    FetchTask.AddTaskId(b, task_id_off)
    FetchTask.AddTaskType(b, TaskType.TaskType.FETCH)
    FetchTask.AddItems(b, items_vec)
    FetchTask.AddTimestampMs(b, int(time.time() * 1000))
    root = FetchTask.End(b)

    b.Finish(root)
    return bytes(b.Output())


def build_restock_payload(task_id: str, items: list[tuple[str, float]]) -> bytes:
    b = flatbuffers.Builder(1024)

    item_offsets = []
    for name, qty in items:
        name_off = b.CreateString(name)
        FbItemQty.Start(b)
        FbItemQty.AddItem(b, name_off)
        FbItemQty.AddQty(b, float(qty))
        item_offsets.append(FbItemQty.End(b))

    RestockTask.StartItemsVector(b, len(item_offsets))
    for off in reversed(item_offsets):
        b.PrependUOffsetTRelative(off)
    items_vec = b.EndVector()

    task_id_off = b.CreateString(task_id)
    RestockTask.Start(b)
    RestockTask.AddTaskId(b, task_id_off)
    RestockTask.AddTaskType(b, TaskType.TaskType.RESTOCK)
    RestockTask.AddItems(b, items_vec)
    RestockTask.AddTimestampMs(b, int(time.time() * 1000))
    root = RestockTask.End(b)

    b.Finish(root)
    return bytes(b.Output())


def pb_order_to_items(order: pb2.Order) -> list[tuple[str, float]]:
    """Flatten protobuf order into list[(item, qty)] across all aisles."""
    out: list[tuple[str, float]] = []
    for aisle in [order.bread, order.meat, order.produce, order.dairy, order.party]:
        for it in aisle.items:
            if it.item and it.qty > 0:
                out.append((it.item, float(it.qty)))
    return out


# ----------------------------
# Services
# ----------------------------
class InventoryService(inv_from_ordering_grpc.InventoryServiceServicer):
    def __init__(self, zmq_pub):
        self.zmq_pub = zmq_pub
        self.task_counter = 1

    def ProcessOrder(self, request: pb2.OrderRequest, context):
        # Always ack for Milestone 1+2 demo
        # But ALSO publish a robot task for Milestone 2
        items = pb_order_to_items(request.order)

        # if empty, return BAD_REQUEST
        if len(items) == 0:
            return pb2.BasicReply(code=pb2.BAD_REQUEST, message="Order cannot be empty")

        task_id = f"task_{self.task_counter}"
        self.task_counter += 1

        if request.message_type == pb2.GROCERY_ORDER:
            payload = build_fetch_payload(task_id, items)
            self.zmq_pub.send_multipart([b"FETCH", payload])
            print(f"[inventory_service] published FETCH {task_id} items={items}", flush=True)

        elif request.message_type == pb2.RESTOCK_ORDER:
            payload = build_restock_payload(task_id, items)
            self.zmq_pub.send_multipart([b"RESTOCK", payload])
            print(f"[inventory_service] published RESTOCK {task_id} items={items}", flush=True)

        else:
            return pb2.BasicReply(code=pb2.BAD_REQUEST, message="Unknown message_type")

        return pb2.BasicReply(code=pb2.OK, message="Inventory received order: OK")


class InventoryRobotService(inv_from_robot_grpc.InventoryRobotServiceServicer):
    def ReportTaskResult(self, request: robot_pb2.RobotTaskResult, context):
        print(
            f"[inventory_service] robot_result robot={request.robot_id} "
            f"task={request.task_id} code={request.code} msg={request.message}",
            flush=True,
        )
        return pb2.BasicReply(code=pb2.OK, message="Inventory received robot result: OK")


def serve(grpc_host="0.0.0.0", grpc_port=50051, zmq_bind="tcp://*:5556"):
    # ZMQ publisher lives in the Inventory service (correct direction for Milestone 2)
    zmq_ctx = zmq.Context()
    zmq_pub = zmq_ctx.socket(zmq.PUB)
    zmq_pub.bind(zmq_bind)
    print(f"[inventory_service] ZMQ PUB bound at {zmq_bind}", flush=True)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    inv_from_ordering_grpc.add_InventoryServiceServicer_to_server(
        InventoryService(zmq_pub), server
    )
    inv_from_robot_grpc.add_InventoryRobotServiceServicer_to_server(
        InventoryRobotService(), server
    )

    server.add_insecure_port(f"{grpc_host}:{grpc_port}")
    server.start()
    print(f"[inventory_service] gRPC listening on {grpc_host}:{grpc_port}", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
