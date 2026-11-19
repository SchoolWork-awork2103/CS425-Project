"""Validate the requested device before opening the UI or loading model weights."""


def validate_device(device, torch_module=None):
    if device == "cpu":
        return
    if device != "cuda":
        raise ValueError("Device must be cpu or cuda")
    if torch_module is None:
        import torch as torch_module
    if torch_module.version.cuda is None:
        raise RuntimeError(
            "--device cuda requires a CUDA-enabled PyTorch build; this environment has CPU-only PyTorch. "
            "Follow the GPU installation instructions in README.md, or run with --device cpu.")
    if not torch_module.cuda.is_available():
        raise RuntimeError(
            "PyTorch includes CUDA, but no usable CUDA GPU is available. "
            "Check the NVIDIA driver with nvidia-smi, or run with --device cpu.")
