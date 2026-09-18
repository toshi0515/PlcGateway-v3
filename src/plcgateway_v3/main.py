import logging
import sys
import threading
import time
from pathlib import Path

from .commands import CommandDispatcher
from .config import Config, load_config
from .mqtt import MqttController
from .plc import PlcController, TelemetryDTO


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    logger: logging.Logger = logging.getLogger(__name__)

    # バックグラウンドスレッドのエラー通知用
    error_event = threading.Event()

    # config.yamlは，プロジェクトのルートディレクトリに置く
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    conf: Config = load_config(config_path)

    plc = PlcController(plc_host=conf.plc_host, plc_port=conf.plc_port)
    dispatcher = CommandDispatcher(plc_controller=plc)
    mqtt = MqttController(
        mqtt_host=conf.mq_host,
        mqtt_port=conf.mq_port,
        dispatcher=dispatcher,
        error_event=error_event,
    )

    plc.connect_plc()
    mqtt.connect_mqtt()

    logger.info("ループ開始")
    try:
        while True:
            if error_event.is_set():
                break

            telemetry: TelemetryDTO | None = plc.read_telemetry()
            if telemetry is None:
                continue

            mqtt.publish_telemetry(telemetry)

            time.sleep(conf.read_interval_ms / 1000)
    except KeyboardInterrupt:
        logger.info("キーボード操作による終了")
    finally:
        mqtt.disconnect_mqtt()
        plc.disconnect_plc()


if __name__ == "__main__":
    main()
