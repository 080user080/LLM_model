import torch
print(f"CUDA: {torch.cuda.is_available()}")
print(f"Версія: {torch.version.cuda}")