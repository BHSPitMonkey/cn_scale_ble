from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.qn_scale_ble.const import DISPLAY_UNIT_KEY, IMPEDANCE_KEY, WEIGHT_KEY
from src.qn_scale_ble.parser import (
    QnScale,
    ScaleData,
    WeightUnit,
    parse,
)


@pytest.mark.asyncio
async def test_scale_initialization():
    callback = Mock()
    scale = QnScale("00:11:22:33:44:55", callback)

    assert scale.address == "00:11:22:33:44:55"
    assert scale._notification_callback == callback
    assert scale._display_unit is None
    assert scale._unit_update_flag is False


@pytest.mark.asyncio
async def test_scale_notification_handler():
    callback = Mock()
    scale = QnScale("00:11:22:33:44:55", callback)
    scale._hw_version = "1.0"
    scale._sw_version = "2.0"
    mock_data = bytearray(
        b"\x10\x0b\xff\x00\x64\x01\x00\x00\x00\x00\xcf"
    )
    scale._notification_handler(None, mock_data, "Test Scale", "00:11:22:33:44:55")
    callback.assert_called_once()
    called_scale_info = callback.call_args[0][0]
    assert isinstance(called_scale_info, ScaleData)
    assert called_scale_info.name == "Test Scale"
    assert called_scale_info.address == "00:11:22:33:44:55"
    assert called_scale_info.hw_version == "1.0"
    assert called_scale_info.sw_version == "2.0"
    assert called_scale_info.display_unit == WeightUnit.KG
    assert called_scale_info.measurements["weight"] == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize("display_unit", [WeightUnit.KG, WeightUnit.LB, WeightUnit.ST])
async def test_etekcity_scale_set_display_unit(display_unit):
    scale = QnScale("00:11:22:33:44:55", Mock())
    scale.display_unit = display_unit

    assert scale._display_unit == display_unit
    assert scale._unit_update_flag is True


@pytest.mark.parametrize(
    "test_id, input_data, expected_output",
    [
        # (
        #     "valid_with_impedance",
        #     bytearray(
        #         b"\xa5\x02\x00\x10\x00\x00\x01\x61\xa1\x00\xe8\x03\x00\x64\x00\x00\x00\x00\x00\x01\x01\x00"
        #     ),
        #     {WEIGHT_KEY: 1.0, IMPEDANCE_KEY: 100, DISPLAY_UNIT_KEY: 0},
        # ),
        # (
        #     "valid_without_impedance",
        #     bytearray(
        #         b"\xa5\x02\x00\x10\x00\x00\x01\x61\xa1\x00\xe8\x03\x00\x64\x00\x00\x00\x00\x00\x01\x00\x00"
        #     ),
        #     {WEIGHT_KEY: 1.0, DISPLAY_UNIT_KEY: 0},
        # ),
        ("invalid_data", bytearray(b"\x00" * 22), None),
        (
            "invalid_length",
            bytearray(
                b"\xa5\x02\x00\x10\x00\x00\x01\x61\xa1\x00\xe8\x03\x00\x64\x00\x00\x00\x00\x00\x01\x01"
            ),
            None,
        ),
    ],
)
def test_parse(test_id, input_data, expected_output):
    result = parse(input_data)
    assert result == expected_output, f"Test case '{test_id}' failed"


@pytest.mark.asyncio
async def test_scale_start_stop():
    with patch(
        "src.qn_scale_ble.parser.create_adv_receiver"
    ) as mock_create_adv_receiver:
        mock_scanner = AsyncMock()
        mock_create_adv_receiver.return_value = mock_scanner

        scale = QnScale("00:11:22:33:44:55", Mock())

        await scale.async_start()
        mock_scanner.start.assert_called_once()

        await scale.async_stop()
        mock_scanner.stop.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
