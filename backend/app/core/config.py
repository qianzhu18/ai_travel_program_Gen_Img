"""
系统核心配置
"""
import os
from pathlib import Path
from pydantic import field_validator, computed_field
from pydantic_settings import BaseSettings

# 项目根目录（从 backend/app/core/config.py 向上 3 级是不够的，需要 4 级才能到项目根目录）
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    """系统配置类"""

    # 应用配置
    APP_NAME: str = "AI图片批量生成系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _normalize_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if v in {"0", "false", "no", "off", "release", "prod", "production", ""}:
                return False
        return False

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库配置
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/database.db"

    # 文件存储路径（Docker 中通过环境变量覆盖）
    # pydantic-settings 会自动将环境变量 DATA_DIR 映射到 data_dir 字段
    data_dir: str = ""  # 环境变量覆盖
    models_dir: str = ""  # 环境变量覆盖

    @computed_field
    @property
    def DATA_DIR(self) -> Path:
        """数据目录，可通过环境变量 DATA_DIR 覆盖"""
        if self.data_dir:
            return Path(self.data_dir)
        return BASE_DIR / "data"

    @computed_field
    @property
    def UPLOAD_DIR(self) -> Path:
        return self.DATA_DIR / "uploads"

    @computed_field
    @property
    def PROCESSED_DIR(self) -> Path:
        return self.DATA_DIR / "processed"

    @computed_field
    @property
    def GENERATED_DIR(self) -> Path:
        return self.DATA_DIR / "generated"

    @computed_field
    @property
    def SELECTED_DIR(self) -> Path:
        return self.DATA_DIR / "selected"

    @computed_field
    @property
    def PENDING_DIR(self) -> Path:
        return self.DATA_DIR / "pending"

    @computed_field
    @property
    def COMPRESSED_DIR(self) -> Path:
        return self.DATA_DIR / "compressed"

    @computed_field
    @property
    def TRASH_DIR(self) -> Path:
        return self.DATA_DIR / "trash"

    @computed_field
    @property
    def LOGS_DIR(self) -> Path:
        return self.DATA_DIR / "logs"

    # AI模型路径
    @computed_field
    @property
    def MODELS_DIR(self) -> Path:
        """模型目录，可通过环境变量 MODELS_DIR 覆盖"""
        if self.models_dir:
            return Path(self.models_dir)
        return BASE_DIR / "models"

    @computed_field
    @property
    def LAMA_MODEL_PATH(self) -> Path:
        return self.MODELS_DIR / "lama"

    # AI服务API配置
    # API易平台统一密钥（SeedDream 4.5 + Nano Banana Pro 共用）
    APIYI_API_KEY: str = ""
    APIYI_API_URL: str = "https://api.apiyi.com"

    # 阿里百炼API（提示词生成）
    BAILIAN_API_KEY: str = ""
    BAILIAN_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"

    # 生图引擎选择（当前固定 Ark 图文生图）
    IMAGE_GENERATION_ENGINE: str = "ark"

    # 宽脸图生成引擎选择 (seedream / nanobanana)
    WIDEFACE_GENERATION_ENGINE: str = "nanobanana"

    # IOPaint 服务地址（Docker 内通过环境变量覆盖为 http://iopaint:8090）
    IOPAINT_URL: str = "http://localhost:8090"

    # Volcengine 视觉服务（去水印）
    VOLC_ACCESS_KEY_ID: str = ""
    VOLC_SECRET_ACCESS_KEY: str = ""
    VOLC_REGION: str = "cn-north-1"
    VOLC_SERVICE: str = "cv"

    # 提示词生成系统Prompt
    PROMPT_SYSTEM_PROMPT: str = """你是一个专业的AI图片生成提示词专家。
请根据用户提供的风格模板（风格描述、服饰要点、场景氛围），生成高质量的提示词。
参考底图时只锁定背景场景、构图、机位和光线，不要继承底图人物身份或面部特征，应按目标人群重建人物。
这是“同一景点多人物打卡图”任务：景点建筑与光影保持一致，仅替换人物和穿搭。
提示词重点写“服装/发型/配饰/姿态”，避免过度面部特写，确保后续换脸流程友好（脸部清晰无遮挡）。
每个提示词应包含：
1. 人物造型描述（服装、发型、气质）
2. 场景融合描述
3. 画面氛围描述
4. 技术参数（高质量、4K、自然光等）
"""

    # 宽脸图生成系统提示词
    WIDEFACE_SYSTEM_PROMPT: str = """基于原图编辑人物肖像：
1) 保持人物身份、发型、服装、背景、构图和机位不变
2) 仅增加面部宽度与下颌宽度约18-25%，脸高基本不变
3) 保持真实皮肤质感，避免卡通化、畸形或夸张变形"""

    # 上传限制
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_BATCH_SIZE: int = 100  # 单次最多100张
    ALLOWED_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".webp"}

    # 并发配置
    MAX_CONCURRENT_TASKS: int = 10

    # 导出配置（Docker 中通过环境变量覆盖为 /app/data/exports）
    DEFAULT_EXPORT_DIR: Path = Path.home() / "Pictures" / "AI图片导出"

    @computed_field
    @property
    def EXPORT_DIR(self) -> Path:
        return self.DATA_DIR / "exports"

    class Config:
        env_file = str(BASE_DIR / ".env")  # 使用绝对路径，确保无论从哪里运行都能找到
        case_sensitive = False  # 允许环境变量不区分大小写匹配
        extra = "ignore"

# 创建全局配置实例
settings = Settings()

# 确保所有目录存在（忽略只读卷的权限错误）
for directory in [
    settings.DATA_DIR,
    settings.UPLOAD_DIR,
    settings.PROCESSED_DIR,
    settings.GENERATED_DIR,
    settings.SELECTED_DIR,
    settings.PENDING_DIR,
    settings.COMPRESSED_DIR,
    settings.TRASH_DIR,
    settings.LOGS_DIR,
    settings.MODELS_DIR,
    settings.EXPORT_DIR,
]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # 忽略只读卷的权限错误（如 Docker 挂载的 /app/models）
        pass
