from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
import os

class Settings(BaseSettings):
    # App settings
    app_name: str = "mymeta"
    version: str = "1.0.0"
    description: str = "A FastAPI application created with fastapi-init"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Security
    secret_key: str = Field(default="your-secret-key-here", alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days (7 * 24 * 60 = 10080 minutes)
    
    # Database - can be overridden by environment variables
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_user: str = Field(default="root", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_name: str = Field(default="mymeta", alias="DB_NAME")
    
    @property
    def database_url(self) -> str:
        """Construct MySQL database URL from components"""
        # URL encode password if it contains special characters
        password = self.db_password or ""
        return f"mysql+pymysql://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略未定义的环境变量
        populate_by_name=True,  # 允许通过字段名或别名设置值
    )
    
    # CORS
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:5173",
        "http://localhost:5174",  # Alternative Vite port
        "http://127.0.0.1:5174"
    ]
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "app.log"
    
    # Rate limiting
    rate_limit_per_minute: int = 60

settings = Settings()