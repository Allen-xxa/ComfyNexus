"""
AI 助手数据模型

定义 AI 助手模块使用的数据结构。
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


@dataclass
class Topic:
    """
    话题数据模型
    
    Attributes:
        id: 话题唯一标识符（UUID）
        name: 话题名称
        created_at: 创建时间（ISO 8601 格式）
        updated_at: 更新时间（ISO 8601 格式）
        message_count: 消息数量（可选，用于列表显示）
        active_config_id: 激活的 API 配置 ID（可选，用于对话级配置选择）
    """
    id: str
    name: str
    created_at: str
    updated_at: str
    message_count: Optional[int] = None
    active_config_id: Optional[str] = None
    
    @classmethod
    def create(cls, name: str = "新对话") -> "Topic":
        """
        创建新话题
        
        Args:
            name: 话题名称，默认为"新对话"
            
        Returns:
            Topic: 新创建的话题对象
        """
        now = datetime.now().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            created_at=now,
            updated_at=now
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            Dict: 话题数据字典
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Topic":
        """
        从字典创建话题对象
        
        Args:
            data: 话题数据字典
            
        Returns:
            Topic: 话题对象
        """
        return cls(**data)
    
    def validate(self) -> bool:
        """
        验证话题数据的有效性
        
        Returns:
            bool: 数据是否有效
            
        Raises:
            ValueError: 数据无效时抛出异常
        """
        if not self.id:
            raise ValueError("话题 ID 不能为空")
        if not self.name or not self.name.strip():
            raise ValueError("话题名称不能为空")
        if len(self.name) > 100:
            raise ValueError("话题名称不能超过 100 个字符")
        return True


@dataclass
class Message:
    """
    消息数据模型
    
    Attributes:
        id: 消息唯一标识符（UUID）
        topic_id: 所属话题 ID
        role: 消息角色（"user" 或 "assistant"）
        content: 消息内容（Markdown 格式）
        timestamp: 消息时间戳（ISO 8601 格式）
        model: AI 模型名称（仅 assistant 消息）
        files: 附件文件列表（可选）
    """
    id: str
    topic_id: str
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
    model: Optional[str] = None
    files: Optional[List[Dict[str, Any]]] = field(default=None)
    
    @classmethod
    def create_user_message(cls, topic_id: str, content: str, files: list = None) -> "Message":
        """
        创建用户消息
        
        Args:
            topic_id: 所属话题 ID
            content: 消息内容
            files: 附件文件列表（可选）
            
        Returns:
            Message: 新创建的用户消息对象
        """
        return cls(
            id=str(uuid.uuid4()),
            topic_id=topic_id,
            role="user",
            content=content,
            timestamp=datetime.now().isoformat(),
            files=files
        )
    
    @classmethod
    def create_assistant_message(
        cls, 
        topic_id: str, 
        content: str, 
        model: str
    ) -> "Message":
        """
        创建 AI 助手消息
        
        Args:
            topic_id: 所属话题 ID
            content: 消息内容
            model: AI 模型名称
            
        Returns:
            Message: 新创建的助手消息对象
        """
        return cls(
            id=str(uuid.uuid4()),
            topic_id=topic_id,
            role="assistant",
            content=content,
            timestamp=datetime.now().isoformat(),
            model=model
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            Dict: 消息数据字典
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """
        从字典创建消息对象
        
        Args:
            data: 消息数据字典
            
        Returns:
            Message: 消息对象
        """
        return cls(**data)
    
    def validate(self) -> bool:
        """
        验证消息数据的有效性
        
        Returns:
            bool: 数据是否有效
            
        Raises:
            ValueError: 数据无效时抛出异常
        """
        if not self.id:
            raise ValueError("消息 ID 不能为空")
        if not self.topic_id:
            raise ValueError("话题 ID 不能为空")
        if self.role not in ("user", "assistant"):
            raise ValueError("消息角色必须是 'user' 或 'assistant'")
        if not self.content or not self.content.strip():
            raise ValueError("消息内容不能为空")
        if len(self.content) > 100000:
            raise ValueError("消息内容不能超过 100000 个字符")
        if self.role == "assistant" and not self.model:
            raise ValueError("助手消息必须指定模型名称")
        return True


@dataclass
class ProviderConfig:
    """
    AI 服务商配置
    
    Attributes:
        enabled: 是否启用
        api_key: API 密钥
        base_url: API 基础 URL（可选）
        models: 可用模型列表
        extra: 其他服务商特定配置
    """
    enabled: bool
    api_key: str
    base_url: Optional[str] = None
    models: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderConfig":
        """从字典创建配置对象"""
        return cls(**data)


@dataclass
class AIParameters:
    """
    AI 参数配置
    
    Attributes:
        temperature: 温度参数（0.0 - 2.0）
        max_tokens: 最大 Token 数
        context_length: 上下文长度（-1 表示无限制）
        system_prompt: 系统提示词
    """
    temperature: float = 0.5
    max_tokens: Optional[int] = None  # None 表示不限制，使用模型默认最大值
    context_length: int = -1
    system_prompt: str = "你是一个有帮助的 AI 助手。"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIParameters":
        """从字典创建参数对象"""
        return cls(**data)
    
    def validate(self) -> bool:
        """
        验证参数的有效性
        
        Returns:
            bool: 参数是否有效
            
        Raises:
            ValueError: 参数无效时抛出异常
        """
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("温度参数必须在 0.0 到 2.0 之间")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("最大 Token 数必须大于 0")
        if self.context_length < -1:
            raise ValueError("上下文长度必须大于等于 -1")
        return True


@dataclass
class ProxyConfig:
    """
    代理配置
    
    Attributes:
        enabled: 是否启用代理
        http_proxy: HTTP 代理地址
        https_proxy: HTTPS 代理地址
    """
    enabled: bool = False
    http_proxy: str = ""
    https_proxy: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyConfig":
        """从字典创建代理配置对象"""
        return cls(**data)


@dataclass
class AIConfig:
    """
    AI 助手完整配置
    
    Attributes:
        providers: 服务商配置字典
        default_provider: 默认服务商
        default_model: 默认模型
        parameters: AI 参数配置
        proxy: 代理配置
    """
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    default_provider: str = "openai"
    default_model: str = "gpt-3.5-turbo"
    parameters: AIParameters = field(default_factory=AIParameters)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "providers": {k: v.to_dict() for k, v in self.providers.items()},
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "parameters": self.parameters.to_dict(),
            "proxy": self.proxy.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIConfig":
        """从字典创建配置对象"""
        providers = {
            k: ProviderConfig.from_dict(v) 
            for k, v in data.get("providers", {}).items()
        }
        parameters = AIParameters.from_dict(data.get("parameters", {}))
        proxy = ProxyConfig.from_dict(data.get("proxy", {}))
        
        return cls(
            providers=providers,
            default_provider=data.get("default_provider", "openai"),
            default_model=data.get("default_model", "gpt-3.5-turbo"),
            parameters=parameters,
            proxy=proxy
        )
    
    @classmethod
    def create_default(cls) -> "AIConfig":
        """
        创建默认配置
        
        Returns:
            AIConfig: 默认配置对象
        """
        return cls(
            providers={
                "openai": ProviderConfig(
                    enabled=False,
                    api_key="",
                    models=["gpt-4", "gpt-3.5-turbo"]
                ),
                "xflow": ProviderConfig(
                    enabled=False,
                    api_key="",
                    base_url="https://api.xflow.cc/v1",
                    models=[]
                ),
                "iflow": ProviderConfig(
                    enabled=False,
                    api_key="",
                    base_url="https://apis.iflow.cn/v1",
                    models=[]
                ),
                "custom-openai": ProviderConfig(
                    enabled=False,
                    api_key="",
                    base_url="",
                    models=[]
                )
            },
            default_provider="openai",
            default_model="gpt-3.5-turbo",
            parameters=AIParameters(),
            proxy=ProxyConfig()
        )


@dataclass
class APIConfigEntity:
    """
    API 配置实体
    
    用于多配置管理，支持为同一服务商创建多个独立的 API 配置。
    
    Attributes:
        id: 配置唯一标识符（UUID）
        alias: 配置别名（用户自定义名称，如"工作账号"、"个人账号"）
        provider: 服务商名称（如 "openai"、"xflow"、"spark" 等）
        api_key: API 密钥（加密存储）
        base_url: API 基础 URL（可选，某些服务商支持自定义）
        model: 当前选择的模型
        models: 可用模型列表
        extra: 服务商特定配置（JSON 格式，如讯飞星火的 App ID 和 API Secret）
        is_default: 是否为默认配置
        status: 配置状态（"available" | "unavailable" | "untested"）
        last_tested_at: 最后测试时间（ISO 8601 格式）
        last_test_latency: 最后测试延迟（毫秒）
        usage_count: 使用次数
        created_at: 创建时间（ISO 8601 格式）
        updated_at: 更新时间（ISO 8601 格式）
    """
    id: str
    alias: str
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model: str = ""
    models: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    status: str = "untested"
    last_tested_at: Optional[str] = None
    last_test_latency: Optional[float] = None
    usage_count: int = 0
    use_system_proxy: bool = False  # 是否使用系统代理
    created_at: str = ""
    updated_at: str = ""
    
    @classmethod
    def create(
        cls,
        alias: str,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        models: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> "APIConfigEntity":
        """
        创建新配置实体
        
        Args:
            alias: 配置别名
            provider: 服务商名称
            api_key: API 密钥
            model: 当前模型
            base_url: API 基础 URL（可选）
            models: 可用模型列表（可选）
            extra: 服务商特定配置（可选）
            
        Returns:
            APIConfigEntity: 新创建的配置实体
        """
        now = datetime.now().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            alias=alias,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            models=models or [],
            extra=extra or {},
            created_at=now,
            updated_at=now
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（**包含明文 api_key**）
        
        Returns:
            Dict[str, Any]: 配置数据字典
        
        Warning:
            仅限后端内部使用（如导出配置、构造 Provider）。
            任何回给前端的 bridge 接口都必须改用 `to_masked_dict()`，
            否则明文密钥会经由 pywebview 序列化进入渲染进程。
        """
        return asdict(self)

    def to_masked_dict(self) -> Dict[str, Any]:
        """
        转换为**可安全回传前端**的字典。

        移除 `api_key` 字段，改为：
            - `api_key_masked`: 掩码（形如 `sk-******XjX9`），空密钥为 ""
            - `has_api_key`: 是否已保存密钥

        Returns:
            Dict[str, Any]: 不含明文密钥的配置字典
        """
        from backend.src.core.ai.secret_store import mask_api_key

        data = asdict(self)
        api_key = data.pop("api_key", "") or ""
        data["api_key_masked"] = mask_api_key(api_key)
        data["has_api_key"] = bool(api_key)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIConfigEntity":
        """
        从字典创建配置实体
        
        Args:
            data: 配置数据字典
            
        Returns:
            APIConfigEntity: 配置实体对象
        """
        return cls(**data)
    
    def validate(self, require_api_key: bool = True) -> bool:
        """
        验证配置数据的有效性
        
        Args:
            require_api_key: 是否强制要求 API Key。仅"导入其它设备的配置"这类
                密钥确实无法带过来的场景会传 False，用户需要补填密钥后才能使用。
        
        Returns:
            bool: 数据是否有效
            
        Raises:
            ValueError: 数据无效时抛出异常，包含具体错误信息
        """
        if not self.id:
            raise ValueError("配置 ID 不能为空")
        if not self.alias or not self.alias.strip():
            raise ValueError("配置别名不能为空")
        if len(self.alias) > 50:
            raise ValueError("配置别名不能超过 50 个字符")
        if not self.provider:
            raise ValueError("服务商不能为空")
        # Ollama 不需要 API Key
        if require_api_key and self.provider != "ollama" and not self.api_key:
            raise ValueError("API Key 不能为空")
        if not self.model:
            raise ValueError("模型不能为空")
        if self.status not in ("available", "unavailable", "untested"):
            raise ValueError("配置状态无效")
        return True
