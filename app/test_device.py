from types import SimpleNamespace
import unittest
import contextlib
import io
from unittest.mock import Mock, patch

from .device import validate_device
from .pipeline import Pipeline


class DeviceTest(unittest.TestCase):
    def test_cpu_needs_no_cuda_checks(self):
        torch = Mock()
        validate_device("cpu", torch)
        torch.cuda.is_available.assert_not_called()

    def test_cpu_only_torch_explains_how_to_recover(self):
        torch = SimpleNamespace(version=SimpleNamespace(cuda=None), cuda=Mock())
        with self.assertRaisesRegex(RuntimeError, "CPU-only PyTorch"):
            validate_device("cuda", torch)
        torch.cuda.is_available.assert_not_called()

    def test_cuda_build_without_usable_gpu_has_driver_message(self):
        torch = SimpleNamespace(version=SimpleNamespace(cuda="12.6"), cuda=Mock())
        torch.cuda.is_available.return_value = False
        with self.assertRaisesRegex(RuntimeError, "NVIDIA driver"):
            validate_device("cuda", torch)

    def test_available_cuda_is_accepted(self):
        torch = SimpleNamespace(version=SimpleNamespace(cuda="12.6"), cuda=Mock())
        torch.cuda.is_available.return_value = True
        validate_device("cuda", torch)

    def test_pipeline_checks_device_before_loading_any_assets(self):
        with patch("app.pipeline.validate_device", side_effect=RuntimeError("CPU-only PyTorch")):
            with self.assertRaisesRegex(RuntimeError, "CPU-only PyTorch"):
                Pipeline({}, device="cuda")

    def test_cli_rejects_unavailable_cuda_before_opening_ui(self):
        from .chat import main
        with patch("sys.argv", ["app.chat", "--device", "cuda"]), \
                patch("app.chat.Pipeline", side_effect=RuntimeError("CPU-only PyTorch")), \
                patch("app.chat.create_app") as create_app, contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 2)
        self.assertIn("CPU-only PyTorch", stderr.getvalue())
        create_app.assert_not_called()


if __name__ == "__main__":
    unittest.main()
