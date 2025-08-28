import sys
from loguru import logger
from settings.config import BASE_DIR, settings

log_path = BASE_DIR / 'logs'
log_path.mkdir(exist_ok=True, parents=True) # 确保创建

logger.remove()

# 之前的 可用
# logger.add(
#     log_path / 'log.log',
#     format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} {module}:{line} | {message}", # 后期可加上 {extra[error_id]}
#     rotation="10 MB",
#     compression="zip",
#     enqueue=True, # 防止丢失 尤其是多线程
#     # serialize=True  # 方便后期复盘
# )

# --------------------------
# 控制台输出配置（核心修复点）
# --------------------------
logger.add(
    sink=sys.stdout,  # 直接使用标准输出
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,  # 控制台日志级别
    colorize=True,  # 启用颜色
    backtrace=True,  # 显示异常堆栈
    diagnose=True,  # 显示诊断信息
)

# --------------------------
# 文件日志配置
# --------------------------
logger.add(
    sink=log_path / 'app.log',
    rotation="10 MB",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{module}:{line} | {message}",
    level="INFO",  # 文件日志级别
    enqueue=True,
    retention="30 days",
    encoding="utf-8"
)