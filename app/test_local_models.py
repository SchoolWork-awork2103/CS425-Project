"""Library-level smoke tests using tiny random models, never project weights."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


HAS_MODELS = all(importlib.util.find_spec(name) for name in ("torch", "transformers", "peft", "tokenizers"))


@unittest.skipUnless(HAS_MODELS, "Optional model dependencies are not installed")
class TinyModelTest(unittest.TestCase):
    def test_system_a_package_import_checkpoint_and_existing_decoder(self):
        from generation.gru_lm import GRULM, generate, load_generator, save_checkpoint
        from generation.sequences import PoemCodec
        codec = PoemCodec(reverse=True)
        model = GRULM(codec.vocab_size, emb_dim=8, hidden=8, layers=1, dropout=0)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "tiny_gru.pt"
            save_checkpoint(checkpoint, model, reverse=True)
            loaded, codec = load_generator(checkpoint)
            poems = generate(loaded, codec, ["confident"], "mild", ["proud", "loud", "wise", "eyes"],
                             n=1, max_line_tokens=6, min_line_tokens=1)
            self.assertEqual(len(poems), 1)
            self.assertEqual(len(poems[0]["lines"]), 4)

    def test_real_peft_switching_and_qwen_service_input_api(self):
        from transformers import PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from peft import LoraConfig, get_peft_model
        from app.model_service import SharedModelService
        raw = Tokenizer(WordLevel({"[UNK]": 0, "[PAD]": 1, "hello": 2, "assistant": 3}, unk_token="[UNK]"))
        raw.pre_tokenizer = Whitespace()
        tok = PreTrainedTokenizerFast(tokenizer_object=raw, unk_token="[UNK]", pad_token="[PAD]")
        tok.chat_template = "{% for message in messages %}{{ message['content'] }} {% endfor %}assistant"
        base = Qwen2ForCausalLM(Qwen2Config(vocab_size=4, hidden_size=32, intermediate_size=64,
                                           num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2,
                                           max_position_embeddings=64, eos_token_id=0, pad_token_id=1))
        model = get_peft_model(base, LoraConfig(r=2, lora_alpha=4, target_modules=["q_proj", "v_proj"],
                                              task_type="CAUSAL_LM", init_lora_weights=False)).eval()
        observed = []
        def generate(current, tokenizer, *args, **kwargs):
            observed.append(current.get_model_status().enabled)
            return []
        service = SharedModelService({}, model=model, tokenizer=tok, generate_fn=generate)
        text = service.interpret([{"role": "user", "content": "hello"}], max_input_tokens=16, max_new_tokens=2)
        self.assertIsInstance(text, str)
        self.assertTrue(model.get_model_status().enabled)
        service.generate([], "mild", ["x"] * 4)
        self.assertEqual(observed, [True])


if __name__ == "__main__":
    unittest.main()
