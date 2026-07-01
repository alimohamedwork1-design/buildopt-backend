from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_mode: bool = Field(default=True, alias="DEMO_MODE")
    app_env: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    allowed_origins: str = Field(
        default="https://build-opt.site,https://www.build-opt.site,http://localhost:5173,https://localhost,capacitor://localhost,http://localhost",
        alias="ALLOWED_ORIGINS",
    )

    influx_url: str = Field(default="http://localhost:8086", alias="INFLUX_URL")
    influx_token: str = Field(default="", alias="INFLUX_TOKEN")
    influx_org: str = Field(default="buildopt", alias="INFLUX_ORG")
    influx_bucket: str = Field(default="building_metrics", alias="INFLUX_BUCKET")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")

    supabase_alert_webhook_url: str = Field(default="", alias="SUPABASE_ALERT_WEBHOOK_URL")
    alert_webhook_secret: str = Field(default="", alias="ALERT_WEBHOOK_SECRET")

    jci_metasys_host: str = Field(default="", alias="JCI_METASYS_HOST")
    jci_metasys_username: str = Field(default="", alias="JCI_METASYS_USERNAME")
    jci_metasys_password: str = Field(default="", alias="JCI_METASYS_PASSWORD")
    jci_metasys_version: str = Field(default="v4", alias="JCI_METASYS_VERSION")

    bacnet_ip: str = Field(default="192.168.1.100", alias="BACNET_IP")
    bacnet_port: int = Field(default=47808, alias="BACNET_PORT")

    modbus_host: str = Field(default="192.168.1.101", alias="MODBUS_HOST")
    modbus_port: int = Field(default=502, alias="MODBUS_PORT")

    mqtt_broker: str = Field(default="localhost", alias="MQTT_BROKER")
    mqtt_port: int = Field(default=1883, alias="MQTT_PORT")
    mqtt_username: str = Field(default="buildopt", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")

    timezone: str = Field(default="Asia/Dubai", alias="TIMEZONE")
    prayer_api_key: str = Field(default="", alias="PRAYER_API_KEY")
    latitude: float = Field(default=25.2048, alias="LATITUDE")
    longitude: float = Field(default=55.2708, alias="LONGITUDE")

    ingest_api_key: str = Field(default="", alias="INGEST_API_KEY")
    poll_interval_seconds: int = Field(default=30, alias="POLL_INTERVAL_SECONDS")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
