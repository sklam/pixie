# cython: infer_types=True
import numpy as np
import cython
cimport libc.math

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.cdivision(True)
def matvec(float[::1] out, float[:, ::1] mat, float[::1] vec):
    cdef size_t row = mat.shape[0]
    cdef size_t col = mat.shape[1]
    cdef size_t i, j
    cdef float c

    for i in range(row):
        c = 0.
        for j in range(col):
            c += mat[i, j] * vec[j]
        out[i] = c
    
    