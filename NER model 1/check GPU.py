import shutil, subprocess, re, sys

nsmi = shutil.which("nvidia-smi")
if not nsmi:
    print("nvidia-smi not found → NVIDIA driver not installed/visible to Windows.")
    sys.exit(0)

try:
    out = subprocess.check_output([nsmi], text=True, stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as e:
    print("Failed to run nvidia-smi:\n", e.output)
    sys.exit(0)

m = re.search(r"Driver Version:\s*([\d.]+)\s+CUDA Version:\s*([\d.]+)", out)
if m:
    driver, cuda = m.groups()
    print(f"Driver Version: {driver}")
    print(f"CUDA (driver supports up to): {cuda}")
else:
    print("Could not parse driver/CUDA from nvidia-smi output.")

# Optional: list GPUs
try:
    gpus = subprocess.check_output([nsmi, "-L"], text=True)
    print("\nGPUs detected:")
    print(gpus.strip())
except Exception:
    pass

import torch
print("python exe:", sys.executable)
print("torch version:", torch.__version__)
print("torch wheel CUDA:", torch.version.cuda)   # None == CPU-only wheel
print("cuda.is_available():", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device:", torch.cuda.get_device_name(0))


import torch, time
torch.set_float32_matmul_precision("high")

# warmup
x = torch.randn(4096, 4096, device="cuda")
y = torch.randn(4096, 4096, device="cuda")
torch.cuda.synchronize()

t0 = time.time()
for _ in range(10):
    z = x @ y
torch.cuda.synchronize()
print("10 matmuls (4096x4096) on GPU:", round(time.time()-t0, 3), "s")