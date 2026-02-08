"""
Test script to verify Whisper installation and GPU access.
Run: python test_whisper.py
"""
import torch

print("=" * 50)
print("Whisper Installation Test")
print("=" * 50)

# Check PyTorch and CUDA
print(f"\nPyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# Load Whisper
print("\nLoading Whisper model (base)...")
try:
    import whisper
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("base", device=device)
    print(f"✓ Model loaded on: {device}")
    print(f"✓ Model parameters device: {next(model.parameters()).device}")
    print("\nAvailable Whisper models:")
    print("  tiny    (~39M params, ~1GB VRAM)")
    print("  base    (~74M params, ~1.5GB VRAM) ← Currently loaded")
    print("  small   (~244M params, ~2GB VRAM)")
    print("  medium  (~769M params, ~5GB VRAM)")
    print("  large-v3 (~1550M params, ~10GB VRAM)")
    print("\n✓ Whisper is ready for audio transcription!")
except ImportError:
    print("✗ Whisper not installed. Run: pip install openai-whisper")
except Exception as e:
    print(f"✗ Error loading Whisper: {e}")

print("=" * 50)
