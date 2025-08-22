# Visit API 配置文件

# 网络配置
NETWORK_CONFIG = {
    "timeout": {
        "total": 60,        # 总超时时间（秒）
        "connect": 15       # 连接超时时间（秒）
    },
    "retries": {
        "max_attempts": 3,  # 最大重试次数
        "delay_factor": 2   # 重试延迟因子
    },
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "proxy": {
        "enabled": True,    # 启用代理
        "http": "http://127.0.0.1:63763",  # HTTP代理地址，格式: "http://proxy_host:port"
        "https": "http://127.0.0.1:63763",       # HTTPS代理地址，格式: "https://proxy_host:port"
        "auth": {            # 代理认证（如果需要）
            "username": None,
            "password": None
        }
    }
}

# 内容提取配置
CONTENT_CONFIG = {
    "max_length": {
        "default": 10000,     # 默认最大内容长度
        "min": 100,           # 最小内容长度
        "max": 50000         # 最大内容长度
    },
    "parallel_limit": 10,     # 并行处理最大数量
    "encoding_fallbacks": [   # 编码回退列表
        "utf-8", "gb2312", "gbk", "gb18030", "latin-1"
    ]
}

# 服务配置
SERVICE_CONFIG = {
    "host": "0.0.0.0",
    "port": 8001,
    "debug": True,
    "reload": False
}

# 日志配置
LOG_CONFIG = {
    "level": "DEBUG",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_rotation": True,    # 是否启用日志文件轮转
    "max_file_size": "10MB"  # 最大日志文件大小
}
