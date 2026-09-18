import logging
import sys
import threading

import paho.mqtt.client as mqtt

from .commands import CommandDispatcher
from .plc import TelemetryDTO

logger = logging.getLogger(__name__)

TELEMETRY_TOPIC = "ARMotorSystem/data"
COMMAND_TOPIC = "ARMotorSystem/cmd"
STATUS_TOPIC = "ARMotorSystem/plc/status"


class MqttController:
    def __init__(
        self,
        mqtt_host: str,
        mqtt_port: int,
        dispatcher: CommandDispatcher,
        error_event: threading.Event,
    ) -> None:
        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.dispatcher = dispatcher
        self.error_event = error_event
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_disconnect = self.on_disconnect

    def connect_mqtt(self) -> None:
        try:
            self.mqttc.will_set(
                topic=STATUS_TOPIC, payload="offline", qos=1, retain=True
            )
            self.mqttc.connect(host=self.mqtt_host, port=self.mqtt_port)
            self.mqttc.loop_start()
            self.subscribe_commands()
        except Exception as e:
            logger.error("MQTTとの接続エラー: %s", e)
            sys.exit(1)

    def disconnect_mqtt(self) -> None:
        self.mqttc.loop_stop()
        self.mqttc.disconnect()

    def on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            self.dispatcher.dispatch(msg.payload)
        except Exception as e:
            logger.error("コマンド処理中にエラー: %s", e)
            self.error_event.set()

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        logger.info("MQTT接続しました: %s", reason_code)

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ) -> None:
        logger.info("MQTT切断しました: %s", reason_code)

    def publish_telemetry(self, msg: TelemetryDTO) -> None:
        try:
            payload = msg.model_dump_json()
            self.mqttc.publish(topic=TELEMETRY_TOPIC, payload=payload)
        except ValueError as e:
            logger.error("MQTTパブリッシュエラー: %s", e)

    def subscribe_commands(self) -> None:
        self.mqttc.subscribe(topic=COMMAND_TOPIC)

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties) -> None:
        logger.info("MQTTサブスクライブしました")
