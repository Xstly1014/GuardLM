"""Quick check: nvrtc loadable + bnb 4bit linear fwd/bwd + SDPA on 4090."""
import ctypes

# 1. nvrtc must be loadable by dlopen (cuDNN JIT dependency)
ctypes.CDLL("libnvrtc.so.12")
ctypes.CDLL("libnvJitLink.so.12")
print("[1] libnvrtc.so.12 + libnvJitLink.so.12 loadable OK")

import torch
import torch.nn.functional as F

print("[2] torch:", torch.__version__, "| cuda:", torch.cuda.is_available(),
      "| device:", torch.cuda.get_device_name(0))

# 3. bitsandbytes 4bit quantized linear layer fwd+bwd (mimics QLoRA path)
import bitsandbytes as bnb
lin = bnb.nn.Linear4bit(256, 256, bias=False).cuda()
x = torch.randn(4, 256, device="cuda", dtype=torch.bfloat16, requires_grad=True)
y = lin(x)
y.sum().backward()
print("[3] bnb Linear4bit fwd/bwd OK, out:", tuple(y.shape))

# 4. SDPA fwd+bwd (attention path)
q = torch.randn(1, 8, 64, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
k = torch.randn(1, 8, 64, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
v = torch.randn(1, 8, 64, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
o = F.scaled_dot_product_attention(q, k, v)
o.sum().backward()
print("[4] SDPA fwd/bwd OK, out:", tuple(o.shape))

# 5. Reproduce exact training path: GQA + bf16 + 4D attn_mask (padding)
#    This forces SDPA away from flash into cuDNN backend -> needs libcuda.so + nvrtc.
q = torch.randn(1, 16, 32, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
k = torch.randn(1, 8, 32, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
v = torch.randn(1, 8, 32, 128, device="cuda", dtype=torch.bfloat16, requires_grad=True)
mask = torch.zeros(1, 1, 32, 32, device="cuda", dtype=torch.bfloat16)
mask[..., 10:] = torch.finfo(torch.bfloat16).min
o = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)
o.sum().backward()
print("[5] GQA SDPA with 4D padding mask fwd/bwd OK, out:", tuple(o.shape))

print("ALL CHECKS PASSED")
