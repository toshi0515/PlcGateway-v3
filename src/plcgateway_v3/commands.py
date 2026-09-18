import json
import logging

from pydantic import BaseModel, Field, ValidationError

from .plc import PlcController


class CommandDTO(BaseModel, validate_assignment=True):
    command: str
    frequency: int | None = Field(default=None, ge=0, le=120)
    direction: int | None = Field(default=None, ge=0, le=1)


logger = logging.getLogger(__name__)


class CommandDispatcher:
    def __init__(self, plc_controller: PlcController) -> None:
        self.plc_controller = plc_controller
        self.cmd_dict = {
            "RUN": self.run_cmd,
            "STOP": self.stop_cmd,
            "SET_FREQUENCY": self.set_freq_cmd,
            "SET_DIRECTION": self.ser_dir_cmd,
        }

    def dispatch(self, json_msg) -> None:
        try:
            payload_dict = json.loads(json_msg)
            cmd_dto = CommandDTO(**payload_dict)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("受信コマンドペイロードが不正です: %s", e)
            return

        # commandに対応する関数を実行
        action = self.cmd_dict.get(cmd_dto.command)
        if action is None:
            logger.error("未知のコマンドです: %s", cmd_dto.command)
            return
        action(cmd_dto)

    def run_cmd(self, cmd_dto: CommandDTO) -> None:
        if cmd_dto.direction is None:
            cmd_dto.direction = 0
        if cmd_dto.frequency is None:
            cmd_dto.frequency = 30
        self.plc_controller.write_motor_run(
            freq=cmd_dto.frequency, dir=cmd_dto.direction
        )
        logger.info(
            "[RUN]コマンド実行: freq=%d, dir=%d", cmd_dto.frequency, cmd_dto.direction
        )

    def stop_cmd(self, cmd_dto: CommandDTO) -> None:
        self.plc_controller.write_motor_stop()
        logger.info("[STOP]コマンド実行")

    def set_freq_cmd(self, cmd_dto: CommandDTO) -> None:
        if cmd_dto.frequency is None:
            logger.error("周波数設定値がNoneです")
            return
        self.plc_controller.write_freq(freq=cmd_dto.frequency)
        logger.info("[SET_FREQ]コマンド実行: freq=%d", cmd_dto.frequency)

    def ser_dir_cmd(self, cmd_dto: CommandDTO) -> None:
        if cmd_dto.direction is None:
            logger.error("回転方向設定値がNoneです")
            return
        self.plc_controller.write_motor_dir(dir=cmd_dto.direction)
        logger.info("[SET_DIR]コマンド実行: dir=%d", cmd_dto.direction)
