import numpy as np
import timeit
import fd_kernel

row = 1024
col = 4096


mat = np.ones((row, col), dtype=np.float32)
vec = np.ones(col, dtype=mat.dtype)
out = np.zeros_like(vec)
h = np.float32(0.1)


def work():
    fd_kernel.matvec(out, mat, vec)


times = timeit.repeat(work, repeat=10, number=1)
print(f"Fastest time: {min(times):f} (s).")
