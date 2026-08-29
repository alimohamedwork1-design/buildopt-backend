import importlib.util
from pathlib import Path


def _load_local_queue():
    path = Path(__file__).resolve().parents[1] / "buildopt-edge" / "app" / "storage" / "local_queue.py"
    spec = importlib.util.spec_from_file_location("edge_local_queue", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.LocalQueue


def test_edge_queue_dedupe(tmp_path):
    LocalQueue = _load_local_queue()
    queue = LocalQueue(str(tmp_path / "edge.db"))
    queue.enqueue("b1:sat:ts", {"value": 1})
    queue.enqueue("b1:sat:ts", {"value": 2})
    assert queue.depth() == 1
    _, payload, _ = queue.dequeue_batch()[0]
    assert payload["value"] == 2
