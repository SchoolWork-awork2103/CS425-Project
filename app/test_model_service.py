from contextlib import contextmanager, nullcontext
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from .model_service import SharedModelService
from dialogue.types import InterpretationError


class Tensor:
    shape = (1, 3)
    def __getitem__(self, index):
        return [7, 8]


class Encoding(dict):
    def __init__(self):
        super().__init__(input_ids=Tensor())
    def to(self, device):
        return self


class Tokenizer:
    pad_token_id = 0
    def apply_chat_template(self, *args, **kwargs):
        return Encoding()
    def decode(self, *args, **kwargs):
        return "{}"


class Model:
    def __init__(self):
        self.enabled = True
        self.fail = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
    @contextmanager
    def disable_adapter(self):
        previous, self.enabled = self.enabled, False
        try:
            yield
        finally:
            self.enabled = previous
    def generate(self, **kwargs):
        assert not self.enabled
        self.entered.set()
        self.release.wait(timeout=2)
        if self.fail:
            raise RuntimeError("inference failure")
        return Tensor()


class SharedModelTest(unittest.TestCase):
    def setUp(self):
        self.model = Model()
        self.generated = threading.Event()
        def generate(model, *args, **kwargs):
            self.assertTrue(model.enabled)
            self.generated.set()
            return []
        self.service = SharedModelService({}, model=self.model, tokenizer=Tokenizer(),
                                          generate_fn=generate, inference_context=nullcontext)

    def test_adapter_restored_after_success_exception_and_budget_rejection(self):
        self.assertEqual(self.service.interpret([]), "{}")
        self.assertTrue(self.model.enabled)
        self.model.fail = True
        with self.assertRaises(RuntimeError):
            self.service.interpret([])
        self.assertTrue(self.model.enabled)
        self.model.fail = False
        with self.assertRaises(InterpretationError):
            self.service.interpret([], max_input_tokens=2)
        self.assertTrue(self.model.enabled)
        self.service.generate([], "mild", ["x"] * 4)

    def test_enabled_generation_waits_for_disabled_interpretation(self):
        self.model.release.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            interpretation = pool.submit(self.service.interpret, [])
            self.assertTrue(self.model.entered.wait(timeout=1))
            generation = pool.submit(self.service.generate, [], "mild", ["x"] * 4)
            self.assertFalse(self.generated.wait(timeout=0.05))
            self.model.release.set()
            interpretation.result(timeout=2)
            generation.result(timeout=2)
        self.assertTrue(self.generated.is_set())


if __name__ == "__main__":
    unittest.main()
