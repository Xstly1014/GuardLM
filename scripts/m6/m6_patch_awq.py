# -*- coding: utf-8 -*-
"""M6 环境补丁：autoawq 0.2.9 × transformers 4.57 兼容 shim（两处）。

背景：autoawq 已官方弃用（被 vLLM 的 llm-compressor 接管），其最后测试配置为
transformers 4.51.3。

补丁 1（scale.py import）：transformers 4.55+ 移除了 activations 中的
NewGELUActivation / PytorchGELUTanh（统一为 GELUActivation(approximate=...)），
导致 awq.quantize.scale import 失败。这些类仅为 GELU 识别的 isinstance 注册表，
shim 为"导入失败时将三个名字统一指向现存的 GELUActivation"，语义不变。

补丁 2（quantizer.py Catcher）：transformers 4.57 的 Qwen3Model.forward 会访问
decoder_layer.attention_type（causal_mask_mapping 键），而 autoawq 的 Catcher 只代理
forward 不代理属性 -> AttributeError。给 Catcher 加 __getattr__ 委托到被包装的
原模块（_modules["module"] 直取，避免递归）。

用法 (WSL): /root/serve-venv/bin/python scripts/m6_patch_awq.py
"""
import sys

VENV = "/root/serve-venv/lib/python3.10/site-packages"

# ---------- 补丁 1：activations import ----------
PATH1 = f"{VENV}/awq/quantize/scale.py"
OLD1 = ("from transformers.activations import "
        "NewGELUActivation, PytorchGELUTanh, GELUActivation")
NEW1 = """try:
    from transformers.activations import NewGELUActivation, PytorchGELUTanh, GELUActivation
except ImportError:
    # transformers >=4.55: 老激活类已并入 GELUActivation，仅保留同名占位
    from transformers.activations import GELUActivation
    NewGELUActivation = PytorchGELUTanh = GELUActivation"""


def patch1():
    with open(PATH1, encoding="utf-8") as f:
        src = f.read()
    if "except ImportError:" in src:
        print("patch1: already patched")
        return
    if OLD1 not in src:
        print("!! patch1 目标 import 行不匹配，请人工检查", file=sys.stderr)
        sys.exit(2)
    src = src.replace(OLD1, NEW1, 1)
    with open(PATH1, "w", encoding="utf-8") as f:
        f.write(src)
    print("patch1 patched:", PATH1)


# ---------- 补丁 2：Catcher 属性代理 ----------
PATH2 = f"{VENV}/awq/quantize/quantizer.py"
OLD2 = """        class Catcher(nn.Module):
            def __init__(self, module):
                super().__init__()
                self.module = module

            def forward(self, *args, **kwargs):"""
NEW2 = """        class Catcher(nn.Module):
            def __init__(self, module):
                super().__init__()
                self.module = module

            def __getattr__(self, name):
                # autoawq 0.2.9 x transformers 4.57 shim: Qwen3Model.forward
                # 访问 decoder_layer.attention_type -> 委托到被包装的原模块
                try:
                    return super().__getattr__(name)
                except AttributeError:
                    return getattr(self._modules["module"], name)

            def forward(self, *args, **kwargs):"""


def patch2():
    with open(PATH2, encoding="utf-8") as f:
        src = f.read()
    if "__getattr__" in src.split("class Catcher", 1)[-1].split("def forward", 1)[0]:
        print("patch2: already patched")
        return
    if OLD2 not in src:
        print("!! patch2 目标 Catcher 代码不匹配，请人工检查", file=sys.stderr)
        sys.exit(2)
    src = src.replace(OLD2, NEW2, 1)
    with open(PATH2, "w", encoding="utf-8") as f:
        f.write(src)
    print("patch2 patched:", PATH2)


if __name__ == "__main__":
    patch1()
    patch2()
