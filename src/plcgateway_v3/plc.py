import logging
import sys
import threading
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from pymcprotocol import Type3E

logger = logging.getLogger(__name__)


# PLC読み取りデータのバリデーションおよびDTO
class TelemetryDTO(BaseModel, validate_assignment=True):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    RotateDirection: int = Field(strict=True, ge=0, le=1)
    Rotation: int = Field(strict=True, ge=0)
    ElectricCurrent: int = Field(strict=True)


class PlcController:
    def __init__(self, plc_host: str, plc_port: int) -> None:
        self.lock = threading.Lock()
        self.plc = Type3E()
        self.host = plc_host
        self.port = plc_port

    def connect_plc(self) -> None:
        try:
            self.plc.connect(self.host, self.port)
            logger.info("PLCと接続しました")
        except Exception as e:
            logger.error("PLCとの接続エラー: %s", e)
            sys.exit(1)

    def disconnect_plc(self) -> None:
        self.plc.close()
        logger.info("PLCから切断しました")

    def read_telemetry(self) -> TelemetryDTO | None:
        """PLCからデータを読み取る

        Returns:
            TelemetryDTO | None: TelemetryDTO (PydanticのDTOクラス) | None (バリデーションエラーなど)
        """
        with self.lock:
            try:
                # D1000: ハートビート, D1001: モータ回転フラグ, D1002: モータ回転方向, D1003: インバータ周波数設定,
                # D1004: モータステータス, D1005: モータ電流測定値, D1006: モータ回転数測定値
                data = self.plc.batchread_wordunits(headdevice="D1000", readsize=7)
                _, _, rotate_dir, _, _, current, rotate_speed = data
            except Exception as e:
                logger.error(
                    "PLCデータ読み取りエラー, 読み取りはスキップされます: %s", e
                )
                return

            telemetry = TelemetryDTO(
                RotateDirection=int(rotate_dir),
                Rotation=int(rotate_speed),
                ElectricCurrent=int(current),
            )
            return telemetry

    def write_motor_run(self, freq: int, dir: int) -> None:
        """モータ回転開始関連のPLCデバイスに書き込む

        Args:
            freq (int): インバータ周波数設定値
            dir (int): 回転方向 (0: 正転, 1: 反転)
        """
        with self.lock:
            self.plc.batchwrite_wordunits(headdevice="D1001", values=[1, dir, freq])

    def write_motor_stop(self) -> None:
        """モータ回転停止のPLCデバイスに書き込む"""
        with self.lock:
            self.plc.batchwrite_wordunits(headdevice="D1001", values=[0])

    def write_motor_dir(self, dir: int) -> None:
        """モータ回転方向のデバイスに書き込む

        Args:
            dir (int): 回転方向 (0: 正転, 1: 反転)
        """
        with self.lock:
            self.plc.batchwrite_wordunits(headdevice="D1002", values=[dir])

    def write_freq(self, freq: int) -> None:
        """インバータ周波数設定値のPLCデバイスに書き込む

        Args:
            freq (int): インバータ周波数設定値
        """
        with self.lock:
            self.plc.batchwrite_wordunits(headdevice="D1003", values=[freq])
