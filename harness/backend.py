# -*- coding: utf-8 -*-
"""推理后端：TransformersBackend（M2）+ VLLMBackend（M6），统一 infer() 接口。

VLLMBackend 走 OpenAI 兼容接口，约束解码 schema 直接由 PredSchema 生成——
同一份契约驱动训练（to_sft）/ 评测（parse）/ 服务（response_format）三层。
"""
import os
import time


def verdict_response_format():
    """从 PredSchema 生成 vLLM OpenAI 兼容 response_format（json_schema）。"""
    from .parse import PredSchema
    schema = PredSchema.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "json_schema",
        "json_schema": {"name": "verdict", "schema": schema},
    }


class TransformersBackend:
    """transformers 批量 generate 后端。

    - 自动识别 LoRA 适配器目录（含 adapter_config.json 则 base + Peft 加载）
    - chat template 统一 enable_thinking=False（Qwen3 关思考）
    - 采样参数按 Qwen3 官方非思考模式 best practice: 温度降 0.2 保 JSON 稳定
    """

    def __init__(self, model_path, base_path=None, dtype="bfloat16", device="cuda"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        # 生成场景必须左填充，否则 batch 内右侧 pad token 进入生成
        self.tokenizer.padding_side = "left"

        adapter_cfg = os.path.join(model_path, "adapter_config.json")
        attn_impl = "eager"  # WSL2 cuDNN SDPA 批量左填充推理偶发 nan（M0 同源坑），eager 稳
        if os.path.exists(adapter_cfg):
            from peft import PeftModel
            if base_path is None:
                base_path = self._read_base_from_adapter(adapter_cfg)
            base = AutoModelForCausalLM.from_pretrained(
                base_path, torch_dtype=getattr(torch, dtype),
                device_map=device, attn_implementation=attn_impl)
            self.model = PeftModel.from_pretrained(base, model_path)
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=getattr(torch, dtype),
                device_map=device, attn_implementation=attn_impl)
        self.model.eval()

        # logits 净化器：任何 nan/inf logit 一律压到 -1e9，防 multinomial 断言
        class _NanSanitize:
            def __call__(self, input_ids, scores):
                return torch.nan_to_num(scores, nan=-1e9, posinf=-1e9, neginf=-1e9)
        self._logits_processors = [_NanSanitize()]

    @staticmethod
    def _read_base_from_adapter(cfg_path):
        import json
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f).get("base_model_name_or_path")

    def infer(self, prompts, max_new_tokens=64, batch_size=16,
              temperature=0.7, top_p=0.8, top_k=20):
        """prompts: list[(instruction, text)]；返回生成文本列表（与输入等长有序）。

        容错: 批量 generate 在 WSL2 cuDNN SDPA 下偶发 logits nan（CUDA assert），
        崩溃的 batch 降级为单样本重试；单样本仍崩则记空串（评测侧计格式错误）。
        """
        outs = [None] * len(prompts)
        for i in range(0, len(prompts), batch_size):
            chunk = prompts[i:i + batch_size]
            try:
                gen_texts = self._generate_batch(chunk, max_new_tokens,
                                                 temperature, top_p, top_k)
                for j, t in enumerate(gen_texts):
                    outs[i + j] = t
            except RuntimeError as e:
                print(f"[backend] batch {i}-{i + len(chunk)} 崩溃({str(e)[:60]}), 单样本重试")
                for j in range(len(chunk)):
                    try:
                        one = self._generate_batch([chunk[j]], max_new_tokens,
                                                    temperature, top_p, top_k)
                        outs[i + j] = one[0]
                    except RuntimeError:
                        print(f"[backend] 样本 {i + j} 单样本仍崩 -> 空输出")
                        outs[i + j] = ""
        return outs

    def _generate_batch(self, chunk, max_new_tokens, temperature, top_p, top_k):
        texts = [
            self.tokenizer.apply_chat_template(
                [{"role": "user", "content": f"{ins}\n{txt}"}],
                tokenize=False, add_generation_prompt=True,
                enable_thinking=False)
            for ins, txt in chunk
        ]
        enc = self.tokenizer(texts, return_tensors="pt",
                             padding=True, truncation=True, max_length=512).to("cuda")
        with self.torch.no_grad():
            gen = self.model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                do_sample=True, temperature=temperature,
                top_p=top_p, top_k=top_k,
                logits_processor=self._logits_processors,
                pad_token_id=self.tokenizer.pad_token_id
                or self.tokenizer.eos_token_id)
        outs = []
        for j in range(len(chunk)):
            # 只取新增 token（去掉 prompt 部分）
            new_ids = gen[j][enc["input_ids"].shape[1]:]
            outs.append(self.tokenizer.decode(new_ids, skip_special_tokens=True))
        return outs


class VLLMBackend:
    """vLLM OpenAI 兼容后端（M6，评测=生产同链路）。

    - 走 /v1/chat/completions；structured=True 时挂 response_format
      （第 6 层约束解码，schema 由 PredSchema 单一来源生成）
    - chat_template_kwargs.enable_thinking=False 关思考（与训练侧一致）
    - 采样参数与 TransformersBackend 对齐：temp 0.7 / top_p 0.8 / top_k 20
    - 依赖 openai 包（仅在 serve-venv 中执行 vLLM 评测时装载）

    注意 top_k 不是 OpenAI 标准字段，经 extra_body 透传给 vLLM。
    """

    def __init__(self, model="guardlm", endpoint="http://localhost:8000/v1",
                 structured=False, api_key="EMPTY", max_retries=2):
        from openai import OpenAI
        self.client = OpenAI(base_url=endpoint, api_key=api_key, timeout=120.0)
        self.model = model
        self.structured = structured
        self.max_retries = max_retries

    def infer(self, prompts, max_new_tokens=64, batch_size=16,
              temperature=0.7, top_p=0.8, top_k=20):
        """prompts: list[(instruction, text)]；顺序同步返回。单请求重试，失败记空串。"""
        fmt = verdict_response_format() if self.structured else None
        outs = []
        for ins, txt in prompts:
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": f"{ins}\n{txt}"}],
                "max_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "extra_body": {
                    "top_k": top_k,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            }
            if fmt:
                body["response_format"] = fmt
            out = ""
            for attempt in range(self.max_retries + 1):
                try:
                    resp = self.client.chat.completions.create(**body)
                    out = resp.choices[0].message.content or ""
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == self.max_retries:
                        print(f"[vllm-backend] 请求失败: {str(e)[:80]} -> 空输出")
                    else:
                        time.sleep(1.0)
            outs.append(out)
        return outs
