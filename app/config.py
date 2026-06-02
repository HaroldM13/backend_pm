from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "jht_pm"
    secret_key: str = Field(default="dev_secret_cambiar_en_produccion")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    allowed_origins: str = "http://localhost:5174,http://localhost:3000"

    # SMTP para envío de códigos de verificación
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # En True imprime el código en consola en vez de enviar email
    dev_mode: bool = True

    model_config = {"env_file": ".env"}


settings = Settings()
