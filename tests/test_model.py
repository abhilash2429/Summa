import torch
import time
from transformers import pipeline

print("Loading model...")
device = 0 if torch.cuda.is_available() else -1
summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn",
    device=device,
    torch_dtype=torch.float32  # Using FP32 for RTX 3050 stability
)
print(f"Model loaded on {'GPU' if device == 0 else 'CPU'}")

test_text = (
    "Climate change refers to long-term shifts in temperatures and weather patterns. "
    "These shifts may be natural, but since the 1800s, human activities have been the main "
    "driver of climate change, primarily due to the burning of fossil fuels like coal, oil "
    "and gas. Burning fossil fuels generates greenhouse gas emissions that act like a blanket "
    "wrapped around the Earth, trapping the sun's heat and raising temperatures."
)

start = time.time()
result = summarizer(test_text, max_length=50, min_length=10, do_sample=False)
elapsed = time.time() - start

print(f"Summary: {result[0]['summary_text']}")
print(f"Inference time: {elapsed:.2f} seconds")
print(f"Device used: {'GPU' if device == 0 else 'CPU'}")
