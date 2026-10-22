from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "products"
    internal_token: str


settings = Settings()
