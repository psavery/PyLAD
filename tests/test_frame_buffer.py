from pylad.instrument.frame_buffer import FrameBufferAllocator


def test_frame_buffer_allocator():
    rows = 2880
    columns = 2880
    num_frames_in_buffer = 50

    allocator = FrameBufferAllocator(
        rows,
        columns,
        num_frames_in_buffer,
    )

    array = allocator.allocate()

    assert array.shape == (num_frames_in_buffer, rows, columns)
