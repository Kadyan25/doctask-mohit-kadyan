from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://docdesk:docdesk@localhost:5433/docdesk"
    llm_provider: str = "fake"
    llm_api_key: str = ""
    watch_folder_path: str = "/data/watch"
    mcp_server_port: int = 8001
    app_port: int = 8000


settings = Settings()
