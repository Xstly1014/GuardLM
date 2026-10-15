# -*- coding: utf-8 -*-
"""推理后端：TransformersBackend（M2），统一 infer(texts) 接口，M6 换 VLLMBackend。"""
import os


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
