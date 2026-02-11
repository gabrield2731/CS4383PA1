import sys
import time
from pathlib import Path

# Ensure project root is on path (for fbschemas.grocery when run as script)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import zmq
import flatbuffers

from fbschemas.grocery.fb import FetchTask, RestockTask
from fbschemas.grocery.fb import ItemQty as FbItemQty

# fetch.fbs: TaskType FETCH=1; restock.fbs: TaskType RESTOCK=1 (single generated TaskType.py)
FETCH_TASK_TYPE = 1
RESTOCK_TASK_TYPE = 1


def build_items(builder: flatbuffers.Builder, items: list[tuple[str, float]]):
    offsets = []
    for name, qty in items:
        name_off = builder.CreateString(name)
        FbItemQty.Start(builder)
        FbItemQty.AddItem(builder, name_off)
        FbItemQty.AddQty(builder, float(qty))
        offsets.append(FbItemQty.End(builder))

    # vector
    FetchTask.StartItemsVector(builder, len(offsets))
    for off in reversed(offsets):
        builder.PrependUOffsetTRelative(off)
    return builder.EndVector()


def build_fetch_task(task_id: str, items: list[tuple[str, float]]) -> bytes:
    b = flatbuffers.Builder(1024)
    items_vec = build_items(b, items)
    task_id_off = b.CreateString(task_id)

    FetchTask.Start(b)
    FetchTask.AddTaskId(b, task_id_off)
    FetchTask.AddTaskType(b, FETCH_TASK_TYPE)
    FetchTask.AddItems(b, items_vec)
    FetchTask.AddTimestampMs(b, int(time.time() * 1000))
    root = FetchTask.End(b)

    b.Finish(root)
    return bytes(b.Output())


def build_restock_task(task_id: str, items: list[tuple[str, float]]) -> bytes:
    b = flatbuffers.Builder(1024)
    items_vec = build_items(b, items)
    task_id_off = b.CreateString(task_id)

    RestockTask.Start(b)
    RestockTask.AddTaskId(b, task_id_off)
    RestockTask.AddTaskType(b, RESTOCK_TASK_TYPE)
    RestockTask.AddItems(b, items_vec)
    RestockTask.AddTimestampMs(b, int(time.time() * 1000))
    root = RestockTask.End(b)

    b.Finish(root)
    return bytes(b.Output())


def main(bind_addr="tcp://*:5556"):
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.bind(bind_addr)

    print(f"[inventory_service] ZMQ PUB bound at {bind_addr}")

    i = 1
    while True:
        # Alternate publishing fetch/restock
        if i % 2 == 1:
            payload = build_fetch_task(f"fetch_{i}", [("milk", 1), ("eggs", 1)])
            pub.send_multipart([b"FETCH", payload])
            print(f"[inventory_service] published FETCH fetch_{i}")
        else:
            payload = build_restock_task(f"restock_{i}", [("bread", 3)])
            pub.send_multipart([b"RESTOCK", payload])
            print(f"[inventory_service] published RESTOCK restock_{i}")

        i += 1
        time.sleep(5)


if __name__ == "__main__":
    main()
