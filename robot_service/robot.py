import time
import zmq
import grpc

from proto import common_pb2 as pb2
from proto import robot_inventory_pb2 as robot_pb2
from proto import robot_inventory_pb2_grpc as inv_robot_grpc

from fbschemas.grocery.fb import FetchTask, RestockTask
from fbschemas.grocery.fb import ItemQty, TaskType


INVENTORY_GRPC_ADDR = "localhost:50051"
ZMQ_SUB_ADDR = "tcp://localhost:5556"


def send_result(robot_id: str, task_id: str, ok: bool, msg: str):
    with grpc.insecure_channel(INVENTORY_GRPC_ADDR) as channel:
        stub = inv_robot_grpc.InventoryRobotServiceStub(channel)
        req = robot_pb2.RobotTaskResult(
            robot_id=robot_id,
            task_id=task_id,
            code=pb2.OK if ok else pb2.INTERNAL_ERROR,
            message=msg,
            timestamp_ms=int(time.time() * 1000),
        )
        stub.ReportTaskResult(req, timeout=5)


def decode_fetch(payload: bytes):
    t = FetchTask.FetchTask.GetRootAsFetchTask(payload, 0)
    task_id = t.TaskId().decode()
    items = [(t.Items(i).Item().decode(), t.Items(i).Qty()) for i in range(t.ItemsLength())]
    return task_id, items


def decode_restock(payload: bytes):
    t = RestockTask.RestockTask.GetRootAsRestockTask(payload, 0)
    task_id = t.TaskId().decode()
    items = [(t.Items(i).Item().decode(), t.Items(i).Qty()) for i in range(t.ItemsLength())]
    return task_id, items


def main(robot_id="robot_1"):
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect(ZMQ_SUB_ADDR)
    sub.setsockopt(zmq.SUBSCRIBE, b"FETCH")
    sub.setsockopt(zmq.SUBSCRIBE, b"RESTOCK")

    print(f"[robot_service] {robot_id} subscribed to {ZMQ_SUB_ADDR}")

    while True:
        topic, payload = sub.recv_multipart()
        topic = topic.decode()

        if topic == "FETCH":
            task_id, items = decode_fetch(payload)
        else:
            task_id, items = decode_restock(payload)

        print(f"[robot_service] got {topic} task_id={task_id} items={items}")

        # simulate doing work
        time.sleep(1)

        # reply back to inventory using protobuf/gRPC
        send_result(robot_id, task_id, ok=True, msg=f"{topic} completed")
        print(f"[robot_service] sent result for {task_id}")


if __name__ == "__main__":
    main()
