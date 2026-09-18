from unittest.mock import MagicMock

from plcgateway_v3.commands import CommandDispatcher


def test_run_command_with_explicit_values() -> None:
    mock_plc = MagicMock()

    dispatcher = CommandDispatcher(plc_controller=mock_plc)

    dispatcher.dispatch('{"command": "RUN", "frequency": 45, "direction": 1}')
    mock_plc.write_motor_run.assert_called_once_with(freq=45, dir=1)


def test_run_command_with_default_values() -> None:
    mock_plc = MagicMock()
    dispatcher = CommandDispatcher(plc_controller=mock_plc)

    # frequencyとdirectionを省略する
    dispatcher.dispatch('{"command": "RUN"}')

    mock_plc.write_motor_run.assert_called_once_with(freq=30, dir=0)


def test_unknown_command_does_nothing() -> None:
    mock_plc = MagicMock()
    dispatcher = CommandDispatcher(plc_controller=mock_plc)

    dispatcher.dispatch('{"command": "FOO"}')

    # どのメソッドも呼ばれていないことを確認する
    mock_plc.write_motor_run.assert_not_called()
    mock_plc.write_motor_stop.assert_not_called()
    mock_plc.write_motor_dir.assert_not_called()
    mock_plc.write_freq.assert_not_called()


def test_set_direction_without_value_is_skipped():
    mock_plc = MagicMock()
    dispatcher = CommandDispatcher(plc_controller=mock_plc)

    dispatcher.dispatch('{"command": "SET_DIRECTION"}')

    # directionが省略されているので、write_motor_dirは呼ばれないはず
    mock_plc.write_motor_dir.assert_not_called()
