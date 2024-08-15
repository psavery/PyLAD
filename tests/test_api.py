import pytest

from pyxisl import api


def test_version():
    api.init()
    version = api.get_version()

    # Verify that it is a valid version
    assert len(version) == 4
    assert version != (0, 0, 0, 0)
    assert all(x >= 0 for x in version)


def test_logging():
    api.enable_logging()


def test_initialize_sensors():
    # If we are not connected, we get a LOADDRIVER error
    with pytest.raises(api.XISLErrorReturn, match='39: HIS_ERROR_LOADDRIVER'):
        num_sensors = api.initialize_sensors()

    # When we are actually connected, we should see this:
    # assert num_sensors == 2


def test_get_next_sensor():
    # If we are not connected, we get a NODESC_AVAILABLE error
    with pytest.raises(
        api.XISLErrorReturn,
        match='28: HIS_ERROR_NODESC_AVAILABLE',
    ):
        api.get_next_sensor()

    # When we are actually connected, we should receive a handle.


def test_set_camera_mode():
    # Verify that we get an exception with an invalid detector
    with pytest.raises(
        api.XISLErrorReturn,
        match='7: HIS_ERROR_INVALIDACQDESC',
    ):
        api.set_camera_mode(17532, 0)
