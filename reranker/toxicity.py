"""Offline scoring of the original Detoxify checkpoint, without runtime downloads.

The checkpoint contains the BERT state dict, architecture and class order. This
uses the same sigmoid scores and label aliases as Detoxify's original scorer.
"""


class OfflineToxicity:
    def __init__(self, checkpoint, device="cpu"):
        import torch
        import transformers
        loaded = torch.load(checkpoint, map_location="cpu", weights_only=False)
        args = loaded["config"]["arch"]["args"]
        aliases = {"toxic": "toxicity", "identity_hate": "identity_attack", "severe_toxic": "severe_toxicity"}
        self.classes = [aliases.get(c, c) for c in loaded["config"]["dataset"]["args"]["classes"]]
        model_class = getattr(transformers, args["model_name"])
        config = model_class.config_class.from_pretrained(
            args["model_type"], num_labels=len(self.classes), local_files_only=True)
        self.model = model_class(config)
        self.model.load_state_dict(loaded["state_dict"])
        self.model.to(device).eval()
        self.tokenizer = getattr(transformers, args["tokenizer_name"]).from_pretrained(
            args["model_type"], local_files_only=True)
        self.device = device

    def __call__(self, poems):
        import torch
        scores = []
        with torch.inference_mode():
            for start in range(0, len(poems), 8):
                encoded = self.tokenizer(poems[start:start + 8], return_tensors="pt", truncation=True,
                                         max_length=512, padding=True).to(self.device)
                values = self.model(**encoded).logits.sigmoid().cpu().tolist()
                scores.extend(dict(zip(self.classes, row)) for row in values)
        return scores
