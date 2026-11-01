"""One unmerged Qwen model, serialized across both inference roles."""
from pathlib import Path
import threading

from dialogue.types import InterpretationError
from .device import validate_device

ROOT = Path(__file__).resolve().parents[1]


class SharedModelService:
    def __init__(self, cfg, device="cpu", model=None, tokenizer=None, generate_fn=None,
                 inference_context=None):
        self.cfg, self.device = cfg, device
        self.model, self.tokenizer = model, tokenizer
        self._generate_fn, self._inference_context = generate_fn, inference_context
        self._lock = threading.RLock()

    def _load(self):
        if self.model is not None:
            return
        validate_device(self.device)
        adapter = ROOT / self.cfg["paths"]["checkpoints"] / self.cfg["reranker"]["tuning"]["checkpoints"]["D"]
        if not (adapter / "adapter_config.json").is_file():
            raise FileNotFoundError(f"Missing poem adapter: {adapter}. See README.md for model setup.")
        from generation.qwen_lora import load_generator
        self.model, self.tokenizer = load_generator(
            adapter, self.device, local_files_only=self.cfg.get("dialogue", {}).get("local_files_only", True))

    def _context(self):
        if self._inference_context is not None:
            return self._inference_context()
        import torch
        return torch.inference_mode()

    def interpret(self, messages, max_input_tokens=4096, max_new_tokens=384):
        with self._lock:
            self._load()
            with self.model.disable_adapter(), self._context():
                encoded = self.tokenizer.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=True, return_tensors="pt",
                    return_dict=True)
                length = encoded["input_ids"].shape[-1]
                if length > max_input_tokens:
                    raise InterpretationError("Message and session exceed the input budget. Please shorten the message.")
                encoded = encoded.to(self.device)
                encoded.pop("token_type_ids", None)  # decoder-only Qwen has no segment embeddings
                output = self.model.generate(
                    **encoded, do_sample=False, num_beams=1, max_new_tokens=max_new_tokens,
                    temperature=None, top_p=None, top_k=None,
                    repetition_penalty=1.0, pad_token_id=self.tokenizer.pad_token_id,
                    return_dict_in_generate=False, output_scores=False, output_logits=False,
                    use_cache=True)
                return self.tokenizer.decode(output[0, length:], skip_special_tokens=True).strip()

    def generate(self, traits, intensity, end_words, **kwargs):
        with self._lock:
            self._load()
            with self._context():
                if self._generate_fn is None:
                    from generation.qwen_lora import generate
                    self._generate_fn = generate
                return self._generate_fn(self.model, self.tokenizer, traits, intensity, end_words,
                                         device=self.device, **kwargs)
