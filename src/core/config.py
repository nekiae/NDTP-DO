"""
Централизованная система конфигурации для NDTP Bot с использованием Pydantic
"""
import logging
from pathlib import Path
from typing import Literal, Set

from dotenv import load_dotenv
from pydantic import Field, validator
from pydantic_settings import BaseSettings

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)


class Config(BaseSettings):
    """Центральный класс конфигурации приложения с использованием Pydantic"""
    
    # === БАЗОВЫЕ НАСТРОЙКИ ===
    debug: bool = Field(default=False, env="DEBUG", description="Режим отладки")
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent,
        description="Корневая директория проекта"
    )
    
    # === НАСТРОЙКИ БОТА ===
    bot_token: str = Field(
        ...,
        env="BOT_TOKEN",
        description="Токен Telegram бота",
        min_length=1
    )
    
    # === API НАСТРОЙКИ ===
    deepseek_api_key: str = Field(
        ...,
        env="DEEPSEEK_API_KEY",
        description="API ключ для DeepSeek",
        min_length=1
    )
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/v1/chat/completions",
        description="URL API DeepSeek"
    )
    
    # === НАСТРОЙКИ ЛИМИТОВ ===
    hourly_request_limit: int = Field(
        default=50,
        env="HOURLY_REQUEST_LIMIT",
        ge=1,
        le=10000,
        description="Лимит запросов в час"
    )
    llm_concurrency_limit: int = Field(
        default=10,
        env="LLM_CONCURRENCY_LIMIT",
        ge=1,
        le=100,
        description="Лимит одновременных запросов к LLM"
    )

    max_file_size: int = Field(default = 1024 * 1024 * 1024)  # 1GB
    
    allowed_file_types: list[str] = ["image/jpeg", "image/png", "image/heic", "video/mp4", "video/mov", "image/jpg"]
    # === НАСТРОЙКИ REDIS ===
    redis_url: str = Field(
        default="redis://localhost",
        env="REDIS_URL",
        description="URL для подключения к Redis"
    )
    
    # Database
    postgres_db: str
    postgres_user: str
    postgres_password : str
    postgres_host : str
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:5432/{self.postgres_db}"

    # === НАСТРОЙКИ ЛОГИРОВАНИЯ ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="Уровень логирования"
    )
    log_format: str = Field(
        default="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        description="Формат логирования"
    )
    log_date_format: str = Field(
        default="%H:%M:%S",
        description="Формат времени в логах"
    )
    
    # === ПРАВА ДОСТУПА ===
    admin_ids: Set[int] = Field(
        default_factory=set,
        env="ADMIN_IDS",
        description="ID администраторов через запятую"
    )
    
    # === НАСТРОЙКИ МОДУЛЕЙ ===
    enable_calendar: bool = Field(
        default=True,
        env="ENABLE_CALENDAR",
        description="Включить модуль календаря"
    )
    enable_quiz: bool = Field(
        default=True,
        env="ENABLE_QUIZ",
        description="Включить модуль викторин"
    )
    enable_brainstorm: bool = Field(
        default=True,
        env="ENABLE_BRAINSTORM",
        description="Включить модуль брейнштормов"
    )
    enable_lists: bool = Field(
        default=True,
        env="ENABLE_LISTS",
        description="Включить модуль списков"
    )
    enable_documents: bool = Field(
        default=True,
        env="ENABLE_DOCUMENTS",
        description="Включить модуль документов"
    )
    
    # === НАСТРОЙКИ RAG ===
    rag_mode: Literal["basic"] = Field(
        default="basic",
        env="RAG_MODE",
        description="Режим работы RAG системы"
    )
    # AWS S3
    aws_access_key_id: str = Field()
    aws_secret_access_key: str = Field()
    aws_s3_bucket_name: str = Field()
    aws_host: str = Field()
    # === ДИРЕКТОРИИ (вычисляемые поля) ===
    @property
    def data_dir(self) -> Path:
        """Директория для данных"""
        return self.project_root / "data"
    
    @property
    def cache_dir(self) -> Path:
        """Директория кэша"""
        return self.data_dir / "cache"
    
    @property
    def knowledge_base_dir(self) -> Path:
        """Директория базы знаний"""
        return self.data_dir / "knowledge_base"
    
    @property
    def parsers_data_dir(self) -> Path:
        """Директория данных парсеров"""
        return self.data_dir / "parsers"
    
    @property
    def notifications_dir(self) -> Path:
        """Директория уведомлений"""
        return self.data_dir / "notifications"
    
    @property
    def prompts_dir(self) -> Path:
        """Директория промптов"""
        return self.data_dir / "prompts"
    
    @property
    def logs_dir(self) -> Path:
        """Директория логов"""
        return self.data_dir / "logs"
    
    @property
    def chroma_db_dir(self) -> Path:
        """Директория ChromaDB"""
        return self.project_root / "chroma_db"
    
    @validator("admin_ids", pre=True)
    def parse_admin_ids(cls, v):
        """Парсинг ID администраторов из строки"""
        if isinstance(v, str):
            admin_ids = set()
            if v.strip():
                for part in v.split(","):
                    part = part.strip()
                    if part:
                        try:
                            admin_ids.add(int(part))
                        except ValueError:
                            logger.warning(f"⚠️ Некорректный ID администратора: {part}")
            return admin_ids
        return v
    
    def setup_logging(self) -> None:
        """Настройка логирования"""
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format=self.log_format,
            datefmt=self.log_date_format,
        )
        
        # Настройка уровней для внешних библиотек
        logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
        logging.getLogger("aiogram.bot").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
    
    def ensure_directories(self) -> None:
        """Создание необходимых директорий"""
        directories_to_create = [
            self.data_dir,
            self.cache_dir,
            self.knowledge_base_dir,
            self.parsers_data_dir,
            self.notifications_dir,
            self.prompts_dir,
            self.logs_dir,
            self.chroma_db_dir
        ]
        
        for directory in directories_to_create:
            directory.mkdir(parents=True, exist_ok=True)
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        return user_id in self.admin_ids
    
    class Config:
        """Настройки Pydantic"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        arbitrary_types_allowed = True


# Создание и настройка глобального экземпляра конфигурации
config = Config()
config.setup_logging()
config.ensure_directories()
