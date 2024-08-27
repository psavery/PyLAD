import ctypes

import numpy as np


class FrameBufferAllocator:
    # These are the same settings used in Clemens Prescher's code
    # See: https://github.com/CPrescher/Varex4343HED/blob/2f4566feda503123eeb62e6773bf70df56af9952/VarexLib/varex.h  # noqa
    PIXEL_TYPE = ctypes.c_uint16
    PIXEL_TYPE_SIZE = ctypes.sizeof(PIXEL_TYPE)
    BUFFER_ALIGNMENT = 4096

    def __init__(self, rows: int, columns: int, num_frames_in_buffer: int):
        self.rows = rows
        self.columns = columns
        self.num_frames_in_buffer = num_frames_in_buffer

    @property
    def num_pixels_per_frame(self) -> int:
        return self.rows * self.columns

    @property
    def num_bytes_per_frame(self) -> int:
        return self.num_pixels_per_frame * self.PIXEL_TYPE_SIZE

    @property
    def num_pixels_in_buffer(self) -> int:
        return self.num_pixels_per_frame * self.num_frames_in_buffer

    @property
    def num_bytes_in_buffer(self) -> int:
        return self.num_bytes_per_frame * self.num_frames_in_buffer

    def allocate_raw(self) -> ctypes.Array:
        # This will return a char array that is at least the size of the buffer
        # (potentially larger, if that was necessary for alignment) that is
        # aligned according to the specified buffer alignment.
        return ctypes_alloc_aligned(
            size=self.num_bytes_in_buffer,
            alignment=self.BUFFER_ALIGNMENT,
        )

    def allocate(self) -> np.ndarray:
        # This will return a numpy array referring to an aligned buffer that
        # is the required size.
        # A pointer to the data may be obtained via `array.ctypes.data`.
        raw = self.allocate_raw()
        return np.frombuffer(
            raw,
            dtype=np.dtype(self.PIXEL_TYPE),
            count=self.num_pixels_in_buffer,
        ).reshape(
            self.num_frames_in_buffer, self.rows, self.columns,
        )


def ctypes_alloc_aligned(size: int, alignment: int) -> ctypes.Array:
    """This utility function allocates aligned memory in ctypes

    I am not 100% certain that aligned memory is needed or helpful for
    our application. However, Clemens Prescher's code used an aligned
    malloc (see: https://github.com/CPrescher/Varex4343HED/blob/2f4566feda503123eeb62e6773bf70df56af9952/VarexLib/varex.cpp#L75).  # noqa

    We are assuming an aligned malloc was used for a reason, and thus
    are using it as well. Unfortunately, aligned malloc is not that
    straightforward to do within ctypes. This function should hopefully
    take care of it, though.

    This was adapted from the following links:
    https://stackoverflow.com/questions/8658813/control-memory-alignment-in-python-ctypes
    https://github.com/python/cpython/issues/112448
    """
    buffer_size = size + alignment - 1
    raw_memory = bytearray(buffer_size)

    ctypes_raw_type = ctypes.c_char * buffer_size
    ctypes_raw_memory = ctypes_raw_type.from_buffer(raw_memory)

    raw_address = ctypes.addressof(ctypes_raw_memory)
    offset = raw_address % alignment
    offset_to_aligned = (alignment - offset) % alignment

    ctypes_aligned_type = ctypes.c_char * (buffer_size - offset_to_aligned)
    ctypes_aligned_memory = ctypes_aligned_type.from_buffer(
        raw_memory, offset_to_aligned
    )

    return ctypes_aligned_memory
