# 設定ファイルの読み込みとバリデーション
import logging
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class Config(BaseModel):
    mq_host: str
    mq_port: int = Field(strict=True, gt=0)
    plc_host: str
    plc_port: int = Field(strict=True, gt=0)
    read_interval_ms: int = Field(strict=True, gt=0)


def load_config(path: Path) -> Config:
    try:
        with open(path, "r", encoding="utf-8") as f:
            config_yml = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("設定ファイルが存在しません: %s", path)
        sys.exit(1)
    try:
        config = Config(**config_yml)
        logger.info(
            "設定を読み込みました: MQTT=%s:%d PLC=%s:%d",
            config.mq_host,
            config.mq_port,
            config.plc_host,
            config.plc_port,
        )
        return config
    except ValidationError as e:
        logger.error("設定値が不正です: %s", e.errors())
        sys.exit(1)
