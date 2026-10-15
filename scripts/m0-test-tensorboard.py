"""Verify TensorBoard stack: torch SummaryWriter, protobuf/numpy pins, llamafactory intact."""
from torch.utils.tensorboard import SummaryWriter

import numpy
import google.protobuf
import transformers

print("SummaryWriter OK")
print("tensorboard via torch OK")
print("numpy:", numpy.__version__)
print("protobuf:", google.protobuf.__version__)
print("transformers:", transformers.__version__)

# write a tiny event file to a temp dir to prove the writer path works end-to-end
w = SummaryWriter(log_dir="/tmp/tb-smoke-test")
for step in range(5):
    w.add_scalar("smoke/loss", 1.0 / (step + 1), step)
w.close()
print("event file written to /tmp/tb-smoke-test")
