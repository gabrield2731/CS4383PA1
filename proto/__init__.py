# Lazy imports so "from proto import common_pb2" works without circular/partial init.
import importlib.util

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
