"""
AI 助手控制器

负责处理前端的 AI 助手相关请求，提供以下功能：
- 话题管理（创建、删除、重命名、查询）
- 消息管理（发送、查询、清空）
- 配置管理（保存、读取、测试连接）
- 流式响应（实时生成 AI 回复）
"""

from typing import Dict, Any, Optional
import logging
import asyncio

# 导入 AI 模块
from backend.src.core.ai.database import init_database
from backend.src.core.ai.topic_manager import TopicManager
from backend.src.core.ai.message_repository import MessageRepository
from backend.src.core.ai.ai_service import AIService
from backend.src.core.ai.config_manager import ConfigManager
from backend.src.core.ai.models import APIConfigEntity
from backend.src.core.ai.model_list_cache import ModelListCache
from backend.src.core.ai.providers.factory import ProviderFactory
from backend.src.core.ai.security_utils import mask_api_key
from backend.src.core.ai import secret_store


logger = logging.getLogger(__name__)


class AIController:
    """
    AI 助手控制器
    
    提供前端调用的 API 接口，协调各个服务层组件。
    """
    
    def __init__(self, window=None):
        """
        初始化 AI 控制器
        
        Args:
            window: pywebview 窗口对象，用于发送事件到前端
        """
        self.window = window
        logger.info("AI 控制器初始化")
        
        # 初始化数据库
        init_database()
        
        # 初始化服务层组件
        self.topic_manager = TopicManager()
        self.message_repository = MessageRepository()
        self.ai_service = AIService()
        self.config_manager = ConfigManager()
        
        # 初始化默认配置管理器
        from backend.src.core.ai.default_config_manager import DefaultConfigManager
        self.default_config_manager = DefaultConfigManager()
        
        # 初始化模型列表缓存（任务 5.3）
        # 使用默认路径（None），由 ModelListCache 自动使用绝对路径
        self.model_cache = ModelListCache(
            cache_dir=None,  # 使用默认路径：<项目根>/cache/ai_models
            default_ttl=3600  # 1 小时
        )
        logger.debug("模型列表缓存已初始化")
        
        # 初始化系统提示词服务
        from backend.src.core.ai.system_prompt_service import SystemPromptService
        from backend.src.utils.paths import get_data_dir
        data_dir = get_data_dir()
        self.system_prompt_service = SystemPromptService(data_dir)
        logger.debug("系统提示词服务已初始化")
    
    # ==================== 话题管理 API ====================
    
    def ai_create_topic(self, name: str = "新对话") -> Dict[str, Any]:
        """
        创建新话题
        
        Args:
            name: 话题名称，默认为"新对话"
            
        Returns:
            {
                "success": bool,
                "topic": {
                    "id": str,
                    "name": str,
                    "created_at": str,
                    "updated_at": str
                },
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"创建话题: {name}")
            topic = self.topic_manager.create_topic(name)
            return {
                "success": True,
                "topic": topic.to_dict()
            }
        except Exception as e:
            logger.error(f"创建话题失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_get_topics(self) -> Dict[str, Any]:
        """
        获取所有话题
        
        Returns:
            {
                "success": bool,
                "topics": [
                    {
                        "id": str,
                        "name": str,
                        "created_at": str,
                        "updated_at": str,
                        "message_count": int
                    }
                ],
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info("获取话题列表")
            topics = self.topic_manager.get_topics()
            return {
                "success": True,
                "topics": [topic.to_dict() for topic in topics]
            }
        except Exception as e:
            logger.error(f"获取话题列表失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_delete_topic(self, topic_id: str) -> Dict[str, Any]:
        """
        删除话题
        
        Args:
            topic_id: 话题 ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"删除话题: {topic_id}")
            success = self.topic_manager.delete_topic(topic_id)
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "话题不存在"
                }
        except Exception as e:
            logger.error(f"删除话题失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_rename_topic(self, topic_id: str, name: str) -> Dict[str, Any]:
        """
        重命名话题
        
        Args:
            topic_id: 话题 ID
            name: 新名称
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"重命名话题: {topic_id} -> {name}")
            success = self.topic_manager.rename_topic(topic_id, name)
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "话题不存在"
                }
        except Exception as e:
            logger.error(f"重命名话题失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 消息管理 API ====================
    
    def ai_send_message_with_config(
        self, 
        topic_id: str, 
        content: str, 
        config_id: str,
        deep_thinking: bool = False,
        web_search_enabled: bool = False,
        system_prompt: str = None,
        files: list = None
    ) -> Dict[str, Any]:
        """
        使用指定的 API 配置发送消息并开始流式响应

        Args:
            topic_id: 话题 ID（如果是 temp_ 开头的临时 ID，会先创建话题）
            content: 用户消息内容
            config_id: API 配置 ID
            deep_thinking: 是否启用深度思考（默认 False）
            web_search_enabled: 是否启用联网搜索（默认 False）
            system_prompt: 系统提示词（可选）
            files: 文件列表（可选），格式：[{
                "file_id": str,
                "type": "image" | "document",
                "content": str,
                "content_type": "base64" | "text",
                "metadata": dict
            }]

        Returns:
            {
                "success": bool,
                "message_id": str,  # 用户消息 ID
                "ai_message_id": str,  # AI 消息 ID（占位）
                "topic_id": str,  # 实际的话题 ID（如果是临时 ID，返回新创建的 ID）
                "error_message": str  # 仅在失败时
            }
        """
        try:
            # 强制输出日志到控制台
            logger.info(f"[AI Controller] 发送消息到话题 {topic_id}, 使用配置 {config_id}, 深度思考={deep_thinking}, 联网搜索={web_search_enabled}, 系统提示词={'已设置' if system_prompt else '无'}, 文件数量={len(files) if files else 0}")
            
            if system_prompt:
                logger.debug(f"[AI Controller] 系统提示词内容（前100字符）: {system_prompt[:100]}")
            
            if files:
                logger.debug(f"[AI Controller] 文件列表: {[f.get('metadata', {}).get('name', 'unknown') for f in files]}")

            actual_topic_id = topic_id

            # 从配置管理器获取指定的配置
            config = self.config_manager.get_config_by_id(config_id)
            if not config:
                logger.error(f"[AI Controller] 配置不存在: {config_id}")
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }

            # 记录配置详情（脱敏 API Key）
            from backend.src.core.ai.security_utils import mask_api_key
            logger.info(
                f"[AI Controller] 使用配置: provider={config.provider}, "
                f"model={config.model}, "
                f"base_url={config.base_url}, "
                f"api_key={mask_api_key(config.api_key)}, "
                f"status={config.status}"
            )

            # 验证配置状态
            if config.status == "unavailable":
                logger.warning(f"配置 {config_id} 状态为不可用，但仍尝试发送")

            # 构建 Provider 配置
            provider_config = {
                "api_key": config.api_key,
                "base_url": config.base_url,
                "temperature": 0.7,  # 使用默认值
                # 不设置 max_tokens，让模型使用其支持的最大值
                "deep_thinking": deep_thinking,  # 传递深度思考标志
                "use_system_proxy": config.use_system_proxy,  # 传递代理设置
            }

            # 如果配置中有额外参数，合并进去
            if config.extra:
                provider_config.update(config.extra)

            safe_config = {
                **provider_config,
                "api_key": mask_api_key(provider_config.get("api_key", "")),
            }
            logger.debug(f"Provider 配置: {safe_config}")
            logger.info(f"[AI Controller] 使用系统代理: {config.use_system_proxy}")

            # 定义异步函数来处理流式响应
            async def process_streaming():
                import json
                
                logger.info(f"[AI Controller] 开始处理流式响应: topic_id={actual_topic_id}")
                logger.info(f"[AI Controller] 文件数量: {len(files) if files else 0}")
                
                events = []
                total_content_length = 0  # 统计总内容长度
                
                try:
                    logger.info(f"[AI Controller] 准备调用 ai_service.send_message()")
                    
                    # 创建异步生成器
                    logger.info(f"[AI Controller] 创建异步生成器")
                    generator = self.ai_service.send_message(
                        actual_topic_id, content, config.provider, config.model, provider_config, web_search_enabled, system_prompt, files
                    )
                    
                    logger.info(f"[AI Controller] 异步生成器已创建: {type(generator)}")
                    
                    logger.info(f"[AI Controller] 开始迭代异步生成器")
                    
                    # 手动调用第一次迭代，捕获可能的异常
                    try:
                        first_event = await generator.__anext__()
                        logger.info(f"[AI Controller] 成功获取第一个事件: type={first_event.get('type')}")
                        events.append(first_event)
                        
                        # 如果第一个事件是 chunk，立即发送到前端
                        if self.window and first_event.get("type") == "chunk":
                            first_chunk = first_event.get('chunk', '')
                            if first_chunk:
                                chunk_json = json.dumps(first_chunk)
                                total_content_length += len(first_chunk)
                                
                                try:
                                    self.window.evaluate_js(f"""
                                        window.dispatchEvent(new CustomEvent('ai_message_chunk', {{
                                            detail: {{
                                                topic_id: '{actual_topic_id}',
                                                chunk: {chunk_json},
                                                done: false
                                            }}
                                        }}))
                                    """)
                                except Exception as e:
                                    logger.error(f"[AI Controller] 发送第一个事件失败: {e}")
                        
                    except StopAsyncIteration:
                        logger.warning(f"[AI Controller] 生成器立即结束，没有产生任何事件")
                        return events
                    except Exception as e:
                        logger.error(f"[AI Controller] 获取第一个事件时出错: {type(e).__name__}: {e}", exc_info=True)
                        raise
                    
                    # 继续迭代剩余事件，每个 chunk 立即发送到前端（打字机效果）
                    async for event in generator:
                        logger.info(f"[AI Controller] 收到事件: type={event['type']}")
                        events.append(event)

                        # 如果有窗口，每个 chunk 立即发送
                        if self.window and event["type"] == "chunk":
                            chunk_content = event['chunk']
                            if chunk_content:
                                chunk_json = json.dumps(chunk_content)
                                total_content_length += len(chunk_content)
                                
                                try:
                                    self.window.evaluate_js(f"""
                                        window.dispatchEvent(new CustomEvent('ai_message_chunk', {{
                                            detail: {{
                                                topic_id: '{actual_topic_id}',
                                                chunk: {chunk_json},
                                                done: false
                                            }}
                                        }}))
                                    """)
                                except Exception as e:
                                    logger.error(f"[AI Controller] 发送 chunk 失败: {e}")
                    
                    logger.info(f"[AI Controller] 流式响应处理完成，共收到 {len(events)} 个事件，总内容长度: {total_content_length}")
                    return events
                except Exception as e:
                    logger.error(f"[AI Controller] 流式响应处理异常: {type(e).__name__}: {e}", exc_info=True)
                    import traceback
                    raise

            # 使用 asyncio 运行异步方法
            logger.info("[AI Controller] 创建事件循环并开始执行流式响应")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 收集所有流式响应事件
                logger.debug("[AI Controller] 调用 process_streaming()")
                events = loop.run_until_complete(process_streaming())
                logger.info(f"[AI Controller] process_streaming() 完成，events 数量: {len(events)}")

                # 查找最终结果
                start_event = next((e for e in events if e["type"] == "start"), None)
                done_event = next((e for e in events if e["type"] == "done"), None)
                error_event = next((e for e in events if e["type"] == "error"), None)

                logger.debug(
                    f"事件统计: start={start_event is not None}, "
                    f"done={done_event is not None}, error={error_event is not None}"
                )

                if error_event:
                    error_msg = error_event.get("error", "未知错误")
                    logger.error(f"收到错误事件: {error_msg}")
                    
                    # 发送错误事件到前端
                    if self.window:
                        import json
                        self.window.evaluate_js(f"""
                            window.dispatchEvent(new CustomEvent('ai_message_error', {{
                                detail: {{
                                    topic_id: '{actual_topic_id}',
                                    error: {json.dumps(error_msg, ensure_ascii=False)}
                                }}
                            }}))
                        """)
                    
                    return {
                        "success": False,
                        "error_message": error_msg
                    }
                elif done_event:
                    # 增加配置使用次数
                    logger.info(f"[AI Controller] 准备增加配置 {config_id} 的使用次数")
                    
                    increment_result = self.config_manager.increment_usage_count(config_id)
                    
                    logger.info(f"[AI Controller] 配置 {config_id} 使用次数增加结果: {increment_result}")
                    
                    # 验证使用次数是否真的增加了
                    updated_config = self.config_manager.get_config_by_id(config_id)
                    if updated_config:
                        logger.info(f"[AI Controller] 更新后的配置使用次数: {updated_config.usage_count}")
                    
                    # 发送完成事件到前端（使用实际的 topic_id）
                    if self.window:
                        logger.debug("发送完成事件到前端")
                        self.window.evaluate_js(f"""
                            window.dispatchEvent(new CustomEvent('ai_message_chunk', {{
                                detail: {{
                                    topic_id: '{actual_topic_id}',
                                    chunk: '',
                                    done: true
                                }}
                            }}))
                        """)
                        
                        # 发送配置使用次数更新事件到前端
                        logger.debug(f"发送配置使用次数更新事件: config_id={config_id}")
                        self.window.evaluate_js(f"""
                            window.dispatchEvent(new CustomEvent('api_config_usage_updated', {{
                                detail: {{
                                    config_id: '{config_id}',
                                    usage_count: {updated_config.usage_count if updated_config else 0}
                                }}
                            }}))
                        """)

                    # 检查是否是第一条消息（消息数量为 2：1 条用户消息 + 1 条 AI 回复）
                    message_count = self.message_repository.get_message_count(actual_topic_id)
                    logger.info(f"[AI Controller] 话题 {actual_topic_id} 当前消息数量: {message_count}")
                    
                    if message_count == 2:
                        # 这是第一条对话，异步生成并更新标题
                        logger.info(f"[AI Controller] 检测到第一条对话，准备生成标题")
                        try:
                            # 在后台线程中生成标题，不阻塞返回
                            import threading
                            def generate_and_update_title():
                                try:
                                    logger.info(f"[AI Controller] 开始生成标题，用户消息: {content[:50]}...")
                                    new_title = self._generate_topic_title(content, config.provider, config.model, provider_config, config.use_system_proxy)
                                    if new_title:
                                        logger.info(f"[AI Controller] 生成的标题: {new_title}")
                                        # 更新话题标题
                                        success = self.topic_manager.rename_topic(actual_topic_id, new_title)
                                        if success:
                                            logger.info(f"[AI Controller] 话题标题更新成功: {actual_topic_id} -> {new_title}")
                                            # 通知前端刷新话题列表
                                            if self.window:
                                                self.window.evaluate_js(f"""
                                                    window.dispatchEvent(new CustomEvent('topic_title_updated', {{
                                                        detail: {{
                                                            topic_id: '{actual_topic_id}',
                                                            new_title: {repr(new_title)}
                                                        }}
                                                    }}))
                                                """)
                                        else:
                                            logger.warning(f"[AI Controller] 话题标题更新失败")
                                    else:
                                        logger.warning(f"[AI Controller] 未能生成标题")
                                except Exception as e:
                                    logger.error(f"[AI Controller] 生成标题异常: {e}", exc_info=True)
                            
                            # 启动后台线程
                            thread = threading.Thread(target=generate_and_update_title, daemon=True)
                            thread.start()
                            logger.info(f"[AI Controller] 标题生成线程已启动")
                        except Exception as e:
                            logger.error(f"[AI Controller] 启动标题生成线程失败: {e}", exc_info=True)

                    logger.info("消息发送成功")
                    return {
                        "success": True,
                        "message_id": start_event["user_message_id"] if start_event else "",
                        "ai_message_id": done_event["ai_message_id"]
                    }
                else:
                    logger.warning("未收到完成事件")
                    return {
                        "success": False,
                        "error_message": "未收到完成事件"
                    }
            except Exception as e:
                logger.error(f"执行流式响应时发生异常: {e}", exc_info=True)
                return {
                    "success": False,
                    "error_message": f"执行异常: {str(e)}"
                }
            finally:
                logger.debug("关闭事件循环")
                loop.close()

        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }


    
    def ai_get_messages(
        self, 
        topic_id: str, 
        limit: int = 100, 
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        获取话题的消息列表
        
        Args:
            topic_id: 话题 ID
            limit: 返回的最大消息数
            offset: 偏移量（用于分页）
            
        Returns:
            {
                "success": bool,
                "messages": [
                    {
                        "id": str,
                        "role": str,  # "user" | "assistant"
                        "content": str,
                        "timestamp": str,
                        "model": str  # 仅 assistant 消息
                    }
                ],
                "total": int,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"获取话题 {topic_id} 的消息列表")
            messages = self.message_repository.get_messages(topic_id, limit, offset)
            total = self.message_repository.get_message_count(topic_id)
            return {
                "success": True,
                "messages": [message.to_dict() for message in messages],
                "total": total
            }
        except Exception as e:
            logger.error(f"获取消息列表失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_clear_messages(self, topic_id: str) -> Dict[str, Any]:
        """
        清空话题的所有消息
        
        Args:
            topic_id: 话题 ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"清空话题 {topic_id} 的消息")
            self.message_repository.clear_messages(topic_id)
            return {"success": True}
        except Exception as e:
            logger.error(f"清空消息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 文件处理 API ====================
    
    def ai_process_file(
        self, 
        file_data: str, 
        file_name: str, 
        file_type: str, 
        file_size: int
    ) -> Dict[str, Any]:
        """
        处理上传的文件
        
        Args:
            file_data: Base64编码的文件数据
            file_name: 文件名
            file_type: MIME类型
            file_size: 文件大小（字节）
            
        Returns:
            {
                "success": bool,
                "file_id": str,  # 文件唯一标识
                "processed_data": {
                    "type": "image" | "document",
                    "content": str,  # Base64或提取的文本
                    "content_type": "base64" | "text",
                    "thumbnail": str,  # 缩略图Base64（仅图片）
                    "metadata": {
                        "name": str,
                        "size": int,
                        "mime_type": str,
                        "extracted_text_length": int  # 仅文档
                    }
                },
                "error_message": str  # 仅在失败时
            }
        """
        try:
            import base64
            import uuid
            from backend.src.core.ai.file_processor import get_file_processor_factory
            
            logger.info(f"处理文件: {file_name}, 类型: {file_type}, 大小: {file_size}")
            
            # 验证文件大小（20MB限制）
            max_size = 20 * 1024 * 1024  # 20MB
            if file_size > max_size:
                logger.warning(f"文件大小超过限制: {file_size} > {max_size}")
                return {
                    "success": False,
                    "error_message": f"文件大小超过限制（最大20MB），当前文件大小: {file_size / 1024 / 1024:.2f}MB"
                }
            
            # 解码Base64数据
            try:
                # 移除可能的data URI前缀
                if ',' in file_data:
                    file_data = file_data.split(',', 1)[1]
                
                file_bytes = base64.b64decode(file_data)
                logger.debug(f"成功解码文件数据，大小: {len(file_bytes)} 字节")
            except Exception as e:
                logger.error(f"Base64解码失败: {e}")
                return {
                    "success": False,
                    "error_message": f"文件数据解码失败: {str(e)}"
                }
            
            # 获取文件处理器工厂
            factory = get_file_processor_factory()
            
            # 处理文件
            try:
                processed_result = factory.process_file(file_bytes, file_name, file_type)
                logger.info(f"文件处理成功: type={processed_result['type']}, content_type={processed_result['content_type']}")
            except ValueError as e:
                logger.error(f"文件处理失败: {e}")
                return {
                    "success": False,
                    "error_message": str(e)
                }
            
            # 生成文件ID
            file_id = str(uuid.uuid4())
            
            # 构建返回结果
            return {
                "success": True,
                "file_id": file_id,
                "processed_data": processed_result
            }
            
        except Exception as e:
            logger.error(f"处理文件失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": f"处理文件时发生错误: {str(e)}"
            }
    
    def ai_get_model_capabilities(
        self, 
        provider: str, 
        model: str
    ) -> Dict[str, Any]:
        """
        获取模型能力
        
        Args:
            provider: AI服务商名称
            model: 模型名称
            
        Returns:
            {
                "success": bool,
                "capabilities": {
                    "supports_images": bool,
                    "supports_documents": bool,
                    "supported_image_formats": list[str],
                    "supported_document_formats": list[str],
                    "max_file_size": int,  # 字节
                    "max_files_per_message": int
                },
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"获取模型能力: provider={provider}, model={model}")
            
            # 定义各服务商的模型能力配置
            capabilities_config = {
                "openai": {
                    # OpenAI Vision 模型
                    "gpt-4-vision-preview": {
                        "supports_images": True,
                        "supports_documents": False,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": [],
                        "max_file_size": 20 * 1024 * 1024,  # 20MB
                        "max_files_per_message": 10
                    },
                    "gpt-4o": {
                        "supports_images": True,
                        "supports_documents": False,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": [],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "gpt-4o-mini": {
                        "supports_images": True,
                        "supports_documents": False,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": [],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    # 默认配置（不支持文件）
                    "default": {
                        "supports_images": False,
                        "supports_documents": False,
                        "supported_image_formats": [],
                        "supported_document_formats": [],
                        "max_file_size": 0,
                        "max_files_per_message": 0
                    }
                },
                "anthropic": {
                    # Claude 3 系列支持图片和文档
                    "claude-3-opus": {
                        "supports_images": True,
                        "supports_documents": True,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": ["pdf", "txt", "md", "json", "xml", "csv"],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "claude-3-sonnet": {
                        "supports_images": True,
                        "supports_documents": True,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": ["pdf", "txt", "md", "json", "xml", "csv"],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "claude-3-haiku": {
                        "supports_images": True,
                        "supports_documents": True,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": ["pdf", "txt", "md", "json", "xml", "csv"],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "default": {
                        "supports_images": False,
                        "supports_documents": False,
                        "supported_image_formats": [],
                        "supported_document_formats": [],
                        "max_file_size": 0,
                        "max_files_per_message": 0
                    }
                }
            }
            
            # 获取服务商配置
            provider_config = capabilities_config.get(provider.lower())
            if provider_config is None:
                # 未知服务商，返回不支持
                logger.warning(f"未知服务商: {provider}")
                return {
                    "success": True,
                    "capabilities": {
                        "supports_images": False,
                        "supports_documents": False,
                        "supported_image_formats": [],
                        "supported_document_formats": [],
                        "max_file_size": 0,
                        "max_files_per_message": 0
                    }
                }
            
            # 获取模型配置（如果没有找到，使用默认配置）
            model_key = model.lower()
            capabilities = provider_config.get(model_key, provider_config.get("default"))
            
            logger.info(
                f"模型能力: supports_images={capabilities['supports_images']}, "
                f"supports_documents={capabilities['supports_documents']}"
            )
            
            return {
                "success": True,
                "capabilities": capabilities
            }
            
        except Exception as e:
            logger.error(f"获取模型能力失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 模型列表获取 API ====================
    
    def ai_get_available_models(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        获取服务商的可用模型列表（任务 5.1, 5.2）
        
        从服务商 API 动态获取可用模型列表，支持缓存机制以提升性能。
        如果 API 调用失败，将降级到静态模型列表。
        
        Args:
            provider: 服务商名称（openai/xflow/iflow/custom-openai）
            config: 服务商配置
                {
                    "api_key": str,       # 新建/未保存时传明文；已保存配置可省略
                    "config_id": str,     # 可选：已保存配置的 ID，掩码/空密钥时由后端补齐真实密钥
                    "base_url": str,      # 可选
                    "model": str,         # 当前选择的模型（用于测试）
                    "temperature": float,
                    "max_tokens": int
                }
        
        Returns:
            {
                "success": bool,
                "models": List[str],  # 模型名称列表
                "from_cache": bool,   # 是否来自缓存
                "error_message": str  # 仅在失败时
            }
        
        Example:
            result = controller.ai_get_available_models("openai", {
                "api_key": "sk-xxx",
                "base_url": "https://api.openai.com/v1"
            })
            # {
            #     "success": True,
            #     "models": ["gpt-4", "gpt-3.5-turbo"],
            #     "from_cache": False
            # }
        """
        try:
            # 掩码合同：已保存配置的真实密钥由后端补齐，前端不再经手明文
            config = self._hydrate_api_key_from_store(config)

            # 获取 base_url（如果未提供，使用默认值）
            base_url = config.get("base_url", "https://api.openai.com/v1")
            
            # 生成缓存键
            cache_key = self.model_cache.generate_cache_key(provider, base_url)
            
            logger.debug(
                f"请求获取模型列表: provider={provider}, "
                f"base_url={base_url}, cache_key={cache_key}"
            )
            
            # 检查缓存是否存在且有效
            cached_models = self.model_cache.get(cache_key)
            
            if cached_models is not None:
                # 缓存命中
                logger.info(
                    f"缓存命中: provider={provider}, models_count={len(cached_models)}"
                )
                return {
                    "success": True,
                    "models": cached_models,
                    "from_cache": True
                }
            
            # 缓存未命中，从 API 获取
            logger.info(
                f"缓存未命中，从 API 获取模型列表: provider={provider}, "
                f"base_url={base_url}"
            )
            
            # Debug 日志：输出完整的请求配置
            logger.debug(
                f"[获取模型列表] 请求配置: provider={provider}, "
                f"base_url={base_url}, "
                f"完整URL={base_url.rstrip('/')}/models"
            )
            
            # 从 config 中提取 use_proxy 参数（如果存在）
            use_proxy = config.get("use_system_proxy", False)
            logger.debug(f"[获取模型列表] 使用系统代理: {use_proxy}")
            
            # 使用 ProviderFactory 创建 Provider 实例
            provider_instance = ProviderFactory.create(provider, config, use_proxy=use_proxy)
            
            # 调用 Provider 的 get_available_models_async() 方法
            # 使用 asyncio.run 在同步上下文中运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                models = loop.run_until_complete(
                    provider_instance.get_available_models_async()
                )
                
                # 将结果存入缓存
                self.model_cache.set(cache_key, models, ttl=3600)
                
                logger.info(
                    f"成功获取模型列表: provider={provider}, "
                    f"models_count={len(models)}, from_cache=False"
                )
                
                return {
                    "success": True,
                    "models": models,
                    "from_cache": False
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            # 错误处理和日志记录
            # 脱敏 API Key
            masked_key = mask_api_key(config.get("api_key", ""))
            
            # 记录详细的错误日志
            logger.error(
                f"获取模型列表失败: provider={provider}, "
                f"base_url={config.get('base_url', 'default')}, "
                f"api_key={masked_key}, "
                f"error_type={type(e).__name__}, "
                f"error_message={str(e)}",
                exc_info=True  # 记录堆栈信息
            )
            
            # 返回错误响应（不缓存错误结果，不使用降级逻辑）
            return {
                "success": False,
                "error_message": str(e),
                "models": []
            }
    
    # ==================== 配置管理 API ====================
    
    def ai_test_connection(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        测试服务商连接
        
        Args:
            provider: 服务商名称
            config: 服务商配置。对已保存的配置，`api_key` 可以是掩码或留空，
                    同时传入 `config_id` 后真实密钥由后端从数据库补齐。

        Returns:
            {
                "success": bool,
                "message": str,
                "latency": float,  # 延迟（毫秒）
                "error_message": str  # 仅在失败时
            }
        """
        try:
            # 掩码合同：已保存配置的真实密钥由后端补齐
            config = self._hydrate_api_key_from_store(config)

            logger.info(f"测试 {provider} 连接")
            logger.debug(f"[ai_test_connection] 收到的配置参数: {list(config.keys())}")
            
            # 使用 asyncio 运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                import time
                from backend.src.core.ai.providers.factory import ProviderFactory
                
                # 提取 use_system_proxy 参数
                use_proxy = config.get('use_system_proxy', False)
                logger.info(f"[ai_test_connection] use_system_proxy={use_proxy} (类型: {type(use_proxy)})")
                
                # 创建 Provider 实例（传递 use_proxy 参数）
                logger.debug(f"[ai_test_connection] 创建 Provider: provider={provider}, use_proxy={use_proxy}")
                provider_instance = ProviderFactory.create(provider, config, use_proxy=use_proxy)
                
                # 测试连接
                start_time = time.time()
                success, message, latency = loop.run_until_complete(
                    provider_instance.test_connection()
                )
                
                if success:
                    return {
                        "success": True,
                        "message": message,
                        "latency": latency
                    }
                else:
                    return {
                        "success": False,
                        "error_message": message
                    }
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"测试连接失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 搜索配置 API ====================
    
    def ai_get_search_config(self) -> Dict[str, Any]:
        """
        获取搜索配置
        
        Returns:
            {
                "success": bool,
                "config": dict,  # 搜索配置
                "error": str  # 仅在失败时
            }
        """
        try:
            from backend.src.core.ai.search.search_manager import SearchManager
            search_manager = SearchManager()
            config = search_manager.get_config()
            
            return {
                "success": True,
                "config": config
            }
        except Exception as e:
            logger.error(f"获取搜索配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def ai_update_search_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新搜索配置
        
        Args:
            config: 搜索配置
            
        Returns:
            {
                "success": bool,
                "error": str  # 仅在失败时
            }
        """
        try:
            from backend.src.core.ai.search.search_manager import SearchManager
            search_manager = SearchManager()
            success, message = search_manager.update_config(config)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": message
                }
        except Exception as e:
            logger.error(f"更新搜索配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def ai_test_search_connection(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        测试搜索引擎连接
        
        Args:
            provider: 搜索引擎名称（duckduckgo/google）
            config: 搜索引擎配置
            
        Returns:
            {
                "success": bool,
                "message": str,
                "latency": float  # 延迟（毫秒）
            }
        """
        try:
            from backend.src.core.ai.search.search_manager import SearchManager
            
            # 使用 asyncio 运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                search_manager = SearchManager()
                success, message, latency = loop.run_until_complete(
                    search_manager.test_provider(provider, config)
                )
                
                return {
                    "success": success,
                    "message": message,
                    "latency": latency
                }
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"测试搜索连接失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "latency": 0
            }
    
    # ==================== 多配置管理 API ====================

    def _hydrate_api_key_from_store(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        当前端只持有掩码时，按 `config_id` 从数据库补齐真实 API Key。

        背景：`ai_list_configs` / `ai_get_config_detail` 不再回传明文密钥，
        "测试连接""获取模型列表"这类需要真实密钥的操作如果针对**已保存的配置**发起，
        必须由后端自己取出密钥，前端不再经手明文。

        Args:
            config: 请求携带的配置（可能含 config_id / api_key / base_url 等）

        Returns:
            Dict: 补齐后的配置副本；未提供 config_id 或已带真实密钥时原样返回
        """
        config_id = config.get("config_id")
        if not config_id:
            return config

        incoming = config.get("api_key", "") or ""
        has_real_key = bool(incoming) and not secret_store.is_masked_value(incoming, "")
        if has_real_key:
            return config

        stored = self.config_manager.get_config_by_id(config_id)
        if stored is None:
            logger.warning(f"补齐 API Key 失败：配置不存在 {config_id}")
            return config

        hydrated = dict(config)
        hydrated["api_key"] = stored.api_key
        if not hydrated.get("base_url"):
            hydrated["base_url"] = stored.base_url
        return hydrated

    def ai_list_configs(self) -> Dict[str, Any]:
        """
        获取所有 API 配置列表
        
        Returns:
            {
                "success": bool,
                "configs": [
                    {
                        "id": str,
                        "alias": str,
                        "provider": str,
                        "model": str,
                        "is_default": bool,
                        "status": str,  # "available" | "unavailable" | "untested"
                        "last_tested_at": str,
                        "usage_count": int,
                        "created_at": str,
                        "updated_at": str,
                        "api_key_masked": str,  # 掩码，形如 sk-******XjX9
                        "has_api_key": bool     # 是否已保存密钥
                    }
                ],
                "error_message": str  # 仅在失败时
            }
        
        Note:
            **不回传明文 api_key**（含掩码字段代替）。需要以已保存配置的身份测试连接/拉取模型时，
            在 config 里带 `config_id`，由后端补齐密钥。
        """
        try:
            logger.info("获取 API 配置列表")
            configs = self.config_manager.list_configs()
            return {
                "success": True,
                "configs": [config.to_masked_dict() for config in configs]
            }
        except Exception as e:
            logger.error(f"获取配置列表失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_get_config_detail(self, config_id: str) -> Dict[str, Any]:
        """
        获取配置详情
        
        Args:
            config_id: 配置 ID
            
        Returns:
            {
                "success": bool,
                "config": {
                    "id": str,
                    "alias": str,
                    "provider": str,
                    "base_url": str,
                    "model": str,
                    "models": List[str],
                    "extra": Dict,  # 服务商特定配置
                    "is_default": bool,
                    "status": str,
                    "last_tested_at": str,
                    "usage_count": int,
                    "created_at": str,
                    "updated_at": str,
                    "api_key_masked": str,  # 掩码（替代明文 api_key）
                    "has_api_key": bool
                },
                "error_message": str  # 仅在失败时
            }
        
        Note:
            不再返回明文 `api_key`。编辑时前端把该字段留空即表示"保持原密钥不变"；
            `ai_update_config` 也会忽略掩码值。
        """
        try:
            logger.info(f"获取配置详情: {config_id}")
            config = self.config_manager.get_config_by_id(config_id)
            if config is None:
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
            return {
                "success": True,
                "config": config.to_masked_dict()
            }
        except Exception as e:
            logger.error(f"获取配置详情失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_create_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新配置
        
        Args:
            config: 配置数据
                {
                    "alias": str,
                    "provider": str,
                    "api_key": str,
                    "base_url": str,  # 可选
                    "model": str,
                    "models": List[str],  # 可选
                    "extra": Dict  # 可选，服务商特定配置
                }
            
        Returns:
            {
                "success": bool,
                "config_id": str,  # 新创建的配置 ID
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"创建新配置: {config.get('alias', 'Unknown')}")
            
            # 导入 APIConfigEntity
            from backend.src.core.ai.models import APIConfigEntity
            
            # 创建配置实体
            config_entity = APIConfigEntity.create(
                alias=config.get("alias", ""),
                provider=config.get("provider", ""),
                api_key=config.get("api_key", ""),
                model=config.get("model", ""),
                base_url=config.get("base_url"),
                models=config.get("models"),
                extra=config.get("extra")
            )
            
            # 验证配置
            config_entity.validate()
            
            # 保存配置
            config_id = self.config_manager.create_config(config_entity)
            
            logger.info(f"配置创建成功: {config_id}")
            return {
                "success": True,
                "config_id": config_id
            }
        except ValueError as e:
            # 验证错误
            logger.warning(f"配置验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"创建配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_update_config(self, config_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新配置
        
        Args:
            config_id: 配置 ID
            config: 配置数据（同 ai_create_config）
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"更新配置: {config_id}")
            
            # 导入 APIConfigEntity
            from backend.src.core.ai.models import APIConfigEntity
            
            # 获取现有配置
            existing_config = self.config_manager.get_config_by_id(config_id)
            if existing_config is None:
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
            
            # 更新配置字段
            if "alias" in config:
                existing_config.alias = config["alias"]
            if "provider" in config:
                existing_config.provider = config["provider"]
            if "api_key" in config:
                # 空值或掩码值 = 用户没有改动密钥，保留数据库里已保存的密钥。
                # 详情接口现在只回掩码，若不这样判断，掩码会被当成新密钥写库、原密钥丢失。
                incoming_key = config["api_key"] or ""
                if secret_store.is_masked_value(incoming_key, existing_config.api_key):
                    logger.info(f"更新配置 {config_id}：收到掩码值，保持原 API Key 不变")
                elif not incoming_key.strip():
                    logger.info(f"更新配置 {config_id}：API Key 留空，保持原 API Key 不变")
                else:
                    existing_config.api_key = incoming_key.strip()
            if "base_url" in config:
                existing_config.base_url = config["base_url"]
            if "model" in config:
                existing_config.model = config["model"]
            if "models" in config:
                existing_config.models = config["models"]
            if "extra" in config:
                existing_config.extra = config["extra"]
            if "use_system_proxy" in config:
                existing_config.use_system_proxy = config["use_system_proxy"]
            
            # 验证配置
            existing_config.validate()
            
            # 保存配置
            success = self.config_manager.update_config(config_id, existing_config)
            
            if success:
                logger.info(f"配置更新成功: {config_id}")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "更新配置失败"
                }
        except ValueError as e:
            # 验证错误
            logger.warning(f"配置验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"更新配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_delete_config(self, config_id: str) -> Dict[str, Any]:
        """
        删除配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"删除配置: {config_id}")
            
            # 检查被删除的配置是否为默认配置
            default_config_id = self.default_config_manager.get_default_config_id()
            if default_config_id == config_id:
                logger.info(f"配置 {config_id} 是默认配置，清除默认配置标记")
                self.default_config_manager.clear_default_config_id()
            
            # 检查是否有对话正在使用该配置
            topics = self.topic_manager.get_topics()
            using_topics = [t for t in topics if t.active_config_id == config_id]
            if using_topics:
                logger.warning(
                    f"配置 {config_id} 正在被 {len(using_topics)} 个对话使用，"
                    f"这些对话将在下次打开时使用默认配置"
                )
            
            # 删除配置
            success = self.config_manager.delete_config(config_id)
            if success:
                logger.info(f"配置删除成功: {config_id}")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
        except Exception as e:
            logger.error(f"删除配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_set_default_config(self, config_id: str) -> Dict[str, Any]:
        """
        设置默认配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"设置默认配置: {config_id}")
            
            # 验证配置是否存在
            config = self.config_manager.get_config_by_id(config_id)
            if config is None:
                logger.warning(f"配置不存在: {config_id}")
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
            
            # 在数据库中设置默认配置（is_default 字段）
            success = self.config_manager.set_default_config(config_id)
            if not success:
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
            
            # 同时更新全局配置文件
            self.default_config_manager.set_default_config_id(config_id)
            
            logger.info(f"默认配置设置成功: {config_id}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"设置默认配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_test_config(self, config_id: str) -> Dict[str, Any]:
        """
        测试配置连接
        
        Args:
            config_id: 配置 ID
            
        Returns:
            {
                "success": bool,
                "available": bool,
                "latency": float,  # 响应延迟（毫秒）
                "message": str,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"测试配置连接: {config_id}")
            
            # 获取配置
            config = self.config_manager.get_config_by_id(config_id)
            if config is None:
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
            
            # 构建 Provider 配置
            provider_config = {
                "api_key": config.api_key,
                "base_url": config.base_url,
                "model": config.model
            }
            
            # 添加服务商特定配置
            if config.extra:
                provider_config.update(config.extra)
            
            # 使用 asyncio 运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                from backend.src.core.ai.providers.factory import ProviderFactory
                
                # 创建 Provider 实例（传递代理参数）
                provider_instance = ProviderFactory.create(
                    config.provider, 
                    provider_config,
                    use_proxy=config.use_system_proxy  # 传递代理设置
                )
                
                logger.info(f"[AI Controller] 测试连接使用系统代理: {config.use_system_proxy}")
                
                # 测试连接
                success, message, latency = loop.run_until_complete(
                    provider_instance.test_connection()
                )
                
                # 更新配置测试状态
                if success:
                    self.config_manager.update_test_status(
                        config_id, 
                        "available", 
                        latency
                    )
                else:
                    self.config_manager.update_test_status(
                        config_id, 
                        "unavailable"
                    )
                
                logger.info(
                    f"配置测试完成: {config_id}, "
                    f"available={success}, latency={latency}"
                )
                
                return {
                    "success": True,
                    "available": success,
                    "latency": latency if success else None,
                    "message": message
                }
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"测试配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 停止生成 API ====================
    
    def ai_stop_generation(self, topic_id: str) -> Dict[str, Any]:
        """
        停止当前话题的 AI 生成
        
        Args:
            topic_id: 话题 ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"停止话题 {topic_id} 的生成")
            self.ai_service.stop_generation(topic_id)
            return {"success": True}
        except Exception as e:
            logger.error(f"停止生成失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 导出功能 API ====================
    
    def ai_export_chat(self, topic_id: str, format: str = "json") -> Dict[str, Any]:
        """
        导出聊天记录
        
        Args:
            topic_id: 话题 ID
            format: 导出格式，支持 "json" 或 "markdown"
            
        Returns:
            {
                "success": bool,
                "content": str,  # 导出的内容字符串
                "format": str,   # 导出格式
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"导出话题 {topic_id} 的聊天记录，格式: {format}")
            
            # 验证格式参数
            if format not in ("json", "markdown"):
                return {
                    "success": False,
                    "error_message": f"不支持的导出格式: {format}，仅支持 'json' 或 'markdown'"
                }
            
            # 获取话题信息
            topic = self.topic_manager.get_topic(topic_id)
            if not topic:
                return {
                    "success": False,
                    "error_message": f"话题不存在: {topic_id}"
                }
            
            # 获取所有消息（不限制数量）
            messages = self.message_repository.get_messages(topic_id, limit=999999)
            
            if not messages:
                return {
                    "success": False,
                    "error_message": "该话题没有消息可导出"
                }
            
            # 根据格式生成导出内容
            if format == "json":
                content = self._export_as_json(topic, messages)
            else:  # markdown
                content = self._export_as_markdown(topic, messages)
            
            logger.info(f"导出成功，共 {len(messages)} 条消息")
            return {
                "success": True,
                "content": content,
                "format": format
            }
            
        except Exception as e:
            logger.error(f"导出聊天记录失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def _export_as_json(self, topic, messages) -> str:
        """
        导出为 JSON 格式
        
        Args:
            topic: 话题对象
            messages: 消息列表
            
        Returns:
            str: JSON 格式的字符串
        """
        import json
        from datetime import datetime
        
        export_data = {
            "export_info": {
                "export_time": datetime.now().isoformat(),
                "format": "json",
                "version": "1.0"
            },
            "topic": topic.to_dict(),
            "messages": [message.to_dict() for message in messages],
            "statistics": {
                "total_messages": len(messages),
                "user_messages": sum(1 for m in messages if m.role == "user"),
                "assistant_messages": sum(1 for m in messages if m.role == "assistant")
            }
        }
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    
    def _export_as_markdown(self, topic, messages) -> str:
        """
        导出为 Markdown 格式
        
        Args:
            topic: 话题对象
            messages: 消息列表
            
        Returns:
            str: Markdown 格式的字符串
        """
        from datetime import datetime
        
        lines = []
        
        # 标题和元数据
        lines.append(f"# {topic.name}")
        lines.append("")
        lines.append("## 对话信息")
        lines.append("")
        lines.append(f"- **话题 ID**: {topic.id}")
        lines.append(f"- **创建时间**: {topic.created_at}")
        lines.append(f"- **更新时间**: {topic.updated_at}")
        lines.append(f"- **消息数量**: {len(messages)}")
        lines.append(f"- **导出时间**: {datetime.now().isoformat()}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 对话内容
        lines.append("## 对话内容")
        lines.append("")
        
        for message in messages:
            # 角色标识
            if message.role == "user":
                role_label = "👤 **用户**"
            else:
                role_label = f"🤖 **AI 助手** ({message.model})"
            
            lines.append(f"### {role_label}")
            lines.append("")
            lines.append(f"*时间: {message.timestamp}*")
            lines.append("")
            lines.append(message.content)
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # 统计信息
        user_count = sum(1 for m in messages if m.role == "user")
        assistant_count = sum(1 for m in messages if m.role == "assistant")
        
        lines.append("## 统计信息")
        lines.append("")
        lines.append(f"- 用户消息: {user_count} 条")
        lines.append(f"- AI 消息: {assistant_count} 条")
        lines.append(f"- 总计: {len(messages)} 条")
        lines.append("")
        
        return "\n".join(lines)

    # ==================== 对话配置管理 API ====================
    
    def ai_set_topic_config(self, topic_id: str, config_id: str) -> Dict[str, Any]:
        """
        设置对话的激活配置
        
        Args:
            topic_id: 对话 ID
            config_id: API 配置 ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"设置对话 {topic_id} 的激活配置: {config_id}")
            
            # 验证配置是否存在
            config = self.config_manager.get_config_by_id(config_id)
            if config is None:
                logger.warning(f"配置不存在: {config_id}")
                return {
                    "success": False,
                    "error_message": f"配置不存在: {config_id}"
                }
            
            # 更新对话的激活配置
            success = self.topic_manager.update_active_config(topic_id, config_id)
            
            if success:
                logger.info(f"对话配置设置成功: {topic_id} -> {config_id}")
                return {"success": True}
            else:
                logger.warning(f"对话不存在: {topic_id}")
                return {
                    "success": False,
                    "error_message": f"对话不存在: {topic_id}"
                }
                
        except Exception as e:
            logger.error(f"设置对话配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_get_topic_config(self, topic_id: str) -> Dict[str, Any]:
        """
        获取对话的激活配置
        
        Args:
            topic_id: 对话 ID
            
        Returns:
            {
                "success": bool,
                "config_id": str | None,  # 配置 ID，可能为 None
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"获取对话 {topic_id} 的激活配置")
            
            # 获取对话的激活配置 ID
            config_id = self.topic_manager.get_active_config_id(topic_id)
            
            # 如果配置 ID 不存在，返回 None
            if config_id is None:
                logger.debug(f"对话 {topic_id} 未设置激活配置")
                return {
                    "success": True,
                    "config_id": None
                }
            
            # 验证配置是否存在（处理配置被删除的情况）
            config = self.config_manager.get_config_by_id(config_id)
            if config is None:
                logger.warning(f"对话 {topic_id} 的配置 {config_id} 不存在，尝试使用默认配置")
                
                # 尝试使用默认配置
                default_config_id = self.default_config_manager.get_default_config_id()
                if default_config_id and self.config_manager.get_config_by_id(default_config_id):
                    logger.info(f"使用默认配置: {default_config_id}")
                    return {
                        "success": True,
                        "config_id": default_config_id
                    }
                
                # 默认配置也不存在，返回 None
                logger.warning("默认配置也不存在")
                return {
                    "success": True,
                    "config_id": None
                }
            
            # 配置存在，返回配置 ID
            logger.debug(f"对话 {topic_id} 的激活配置: {config_id}")
            return {
                "success": True,
                "config_id": config_id
            }
            
        except Exception as e:
            logger.error(f"获取对话配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 默认配置管理 API ====================
    
    def ai_get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置 ID
        
        Returns:
            {
                "success": bool,
                "config_id": str | None,  # 默认配置 ID，可能为 None
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info("获取默认配置 ID")
            
            # 获取默认配置 ID
            config_id = self.default_config_manager.get_default_config_id()
            
            # 如果配置 ID 不存在，返回 None
            if config_id is None:
                logger.debug("未设置默认配置")
                return {
                    "success": True,
                    "config_id": None
                }
            
            # 验证默认配置是否有效（配置是否存在）
            config = self.config_manager.get_config_by_id(config_id)
            if config is None:
                logger.warning(f"默认配置 {config_id} 不存在，自动清除")
                self.default_config_manager.clear_default_config_id()
                return {
                    "success": True,
                    "config_id": None
                }
            
            # 配置有效，返回配置 ID
            logger.debug(f"默认配置: {config_id}")
            return {
                "success": True,
                "config_id": config_id
            }
            
        except Exception as e:
            logger.error(f"获取默认配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }

    # ==================== 私有辅助方法 ====================
    
    def _generate_topic_title(
        self, 
        user_message: str, 
        provider: str, 
        model: str, 
        provider_config: Dict[str, Any],
        use_system_proxy: bool = False
    ) -> Optional[str]:
        """
        根据用户消息内容生成对话标题
        
        使用 AI 模型提取用户消息的主题，生成简洁的标题（5-10个字）
        
        Args:
            user_message: 用户的第一条消息
            provider: AI 服务商名称
            model: 模型名称
            provider_config: Provider 配置
            use_system_proxy: 是否使用系统代理（默认 False）
            
        Returns:
            生成的标题，失败返回 None
        """
        try:
            logger.info(f"[AI Controller] 开始生成对话标题")
            
            # 构建提示词，要求 AI 提取主题
            system_prompt = """你是一个专业的对话标题生成助手。你的任务是根据用户的第一条消息，提取核心主题并生成一个简洁、准确、有信息量的对话标题。

## 标题生成原则

1. **长度要求**：8-15个汉字（不包括标点符号）
2. **信息密度**：标题应包含关键信息，让人一眼就能理解对话主题
3. **具体性**：避免过于宽泛的词汇，尽量具体化
4. **专业性**：使用准确的技术术语或领域词汇
5. **可读性**：标题应该自然流畅，易于理解

## 标题结构建议

根据消息类型选择合适的结构：

- **技术问题**：[技术栈/工具] + [具体问题/操作]
  例如："Python实现异步文件读取"、"React组件状态管理方案"

- **错误排查**：[系统/工具] + [错误类型] + 排查/修复
  例如："Docker容器启动失败排查"、"MySQL连接超时问题"

- **功能实现**：实现 + [具体功能描述]
  例如："实现用户登录验证功能"、"开发实时聊天系统"

- **学习咨询**：[技术/概念] + 学习/入门/原理
  例如："Kubernetes核心概念学习"、"机器学习算法原理"

- **方案设计**：[项目/系统] + 架构/设计/方案
  例如："微服务架构设计方案"、"数据库分库分表策略"

- **工具使用**：[工具名称] + [具体用途/操作]
  例如："Git分支管理最佳实践"、"Nginx反向代理配置"

## 注意事项

- 不要使用标点符号（句号、逗号、问号等）
- 不要使用"如何"、"怎么"等疑问词开头
- 不要使用"帮我"、"请问"等客套语
- 避免使用"问题"、"咨询"等冗余词汇
- 如果消息包含多个主题，提取最核心的一个

## 示例

用户消息："如何在 Python 中使用 asyncio 实现异步文件读取？"
标题：Python asyncio异步文件读取

用户消息："我的 Docker 容器启动后立即退出，日志显示端口被占用"
标题：Docker容器端口占用问题

用户消息："帮我设计一个电商系统的订单模块，需要支持秒杀和库存扣减"
标题：电商订单模块秒杀库存设计

用户消息："想学习一下 Kubernetes 的核心概念，比如 Pod、Service 这些"
标题：Kubernetes核心概念学习

用户消息："React 项目中如何优雅地管理全局状态？Redux 还是 Context API？"
标题：React全局状态管理方案选择

用户消息："MySQL 查询很慢，explain 显示没有使用索引"
标题：MySQL查询性能索引优化

## 输出要求

直接输出标题文本，不要有任何解释、引号或其他额外内容。"""

            user_prompt = f"用户消息：\n{user_message}\n\n请生成标题："
            
            # 创建 Provider 实例
            from backend.src.core.ai.providers.factory import ProviderFactory
            
            # 使用较小的 max_tokens 和较低的 temperature
            title_config = provider_config.copy()
            title_config['model'] = model  # 添加 model 参数
            title_config['max_tokens'] = 100  # 增加 tokens 以支持更详细的标题
            title_config['temperature'] = 0.3  # 降低随机性，使标题更稳定
            title_config['deep_thinking'] = False  # 不需要深度思考
            
            provider_instance = ProviderFactory.create(
                provider, 
                title_config,
                use_proxy=use_system_proxy
            )
            
            # 构建消息列表
            messages = [
                {"role": "user", "content": user_prompt}
            ]
            
            # 调用 AI 生成标题（同步方式）
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 收集流式响应
                title_chunks = []
                
                async def collect_title():
                    async for chunk in provider_instance.chat_stream(messages, system_prompt):
                        if chunk.content:
                            title_chunks.append(chunk.content)
                
                loop.run_until_complete(collect_title())
                
                # 拼接标题
                title = ''.join(title_chunks).strip()
                
                # 验证标题
                if title and len(title) > 0:
                    # 移除可能的标点符号和引号
                    title = title.replace('。', '').replace('，', '').replace('、', '').replace('：', '').replace(':', '')
                    title = title.replace('"', '').replace('"', '').replace('"', '').replace(''', '').replace(''', '').replace("'", '')
                    title = title.replace('？', '').replace('?', '').replace('！', '').replace('!', '')
                    title = title.replace('《', '').replace('》', '').replace('【', '').replace('】', '')
                    title = title.strip()
                    
                    # 限制长度（最多20个字符，支持更详细的标题）
                    if len(title) > 20:
                        title = title[:20]
                    
                    logger.info(f"[AI Controller] 成功生成标题: {title}")
                    return title
                else:
                    logger.warning(f"[AI Controller] 生成的标题为空")
                    return None
                    
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"[AI Controller] 生成标题失败: {e}", exc_info=True)
            return None
    # ==================== 文件处理 API ====================

    def ai_process_file(
        self,
        file_data: str,
        file_name: str,
        file_type: str,
        file_size: int
    ) -> Dict[str, Any]:
        """
        处理上传的文件

        Args:
            file_data: Base64编码的文件数据
            file_name: 文件名
            file_type: MIME类型
            file_size: 文件大小（字节）

        Returns:
            {
                "success": bool,
                "file_id": str,  # 文件唯一标识
                "processed_data": {
                    "type": "image" | "document",
                    "content": str,  # Base64或提取的文本
                    "content_type": "base64" | "text",
                    "thumbnail": str,  # 缩略图Base64（仅图片）
                    "metadata": {
                        "name": str,
                        "size": int,
                        "mime_type": str,
                        "extracted_text_length": int  # 仅文档
                    }
                },
                "error_message": str  # 仅在失败时
            }
        """
        try:
            import base64
            import uuid
            from backend.src.core.ai.file_processor import get_file_processor_factory

            logger.info(f"处理文件: {file_name}, 类型: {file_type}, 大小: {file_size}")

            # 验证文件大小（20MB限制）
            max_size = 20 * 1024 * 1024  # 20MB
            if file_size > max_size:
                logger.warning(f"文件大小超过限制: {file_size} > {max_size}")
                return {
                    "success": False,
                    "error_message": f"文件大小超过限制（最大20MB），当前文件大小: {file_size / 1024 / 1024:.2f}MB"
                }

            # 解码Base64数据
            try:
                # 移除可能的data URI前缀
                if ',' in file_data:
                    file_data = file_data.split(',', 1)[1]

                file_bytes = base64.b64decode(file_data)
                logger.debug(f"成功解码文件数据，大小: {len(file_bytes)} 字节")
            except Exception as e:
                logger.error(f"Base64解码失败: {e}")
                return {
                    "success": False,
                    "error_message": f"文件数据解码失败: {str(e)}"
                }

            # 获取文件处理器工厂
            factory = get_file_processor_factory()

            # 处理文件
            try:
                processed_result = factory.process_file(file_bytes, file_name, file_type)
                logger.info(f"文件处理成功: type={processed_result['type']}, content_type={processed_result['content_type']}")
            except ValueError as e:
                logger.error(f"文件处理失败: {e}")
                return {
                    "success": False,
                    "error_message": str(e)
                }

            # 生成文件ID
            file_id = str(uuid.uuid4())

            # 构建返回结果
            return {
                "success": True,
                "file_id": file_id,
                "processed_data": processed_result
            }

        except Exception as e:
            logger.error(f"处理文件失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": f"处理文件时发生错误: {str(e)}"
            }

    def ai_get_model_capabilities(
        self,
        provider: str,
        model: str
    ) -> Dict[str, Any]:
        """
        获取模型能力

        Args:
            provider: AI服务商名称
            model: 模型名称

        Returns:
            {
                "success": bool,
                "capabilities": {
                    "supports_images": bool,
                    "supports_documents": bool,
                    "supported_image_formats": list[str],
                    "supported_document_formats": list[str],
                    "max_file_size": int,  # 字节
                    "max_files_per_message": int
                },
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"获取模型能力: provider={provider}, model={model}")

            # 定义各服务商的模型能力配置
            capabilities_config = {
                "openai": {
                    # OpenAI Vision 模型
                    "gpt-4-vision-preview": {
                        "supports_images": True,
                        "supports_documents": False,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": [],
                        "max_file_size": 20 * 1024 * 1024,  # 20MB
                        "max_files_per_message": 10
                    },
                    "gpt-4o": {
                        "supports_images": True,
                        "supports_documents": False,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": [],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "gpt-4o-mini": {
                        "supports_images": True,
                        "supports_documents": False,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": [],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    # 默认配置（不支持文件）
                    "default": {
                        "supports_images": False,
                        "supports_documents": False,
                        "supported_image_formats": [],
                        "supported_document_formats": [],
                        "max_file_size": 0,
                        "max_files_per_message": 0
                    }
                },
                "anthropic": {
                    # Claude 3 系列支持图片和文档
                    "claude-3-opus": {
                        "supports_images": True,
                        "supports_documents": True,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": ["pdf", "txt", "md", "json", "xml", "csv"],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "claude-3-sonnet": {
                        "supports_images": True,
                        "supports_documents": True,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": ["pdf", "txt", "md", "json", "xml", "csv"],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "claude-3-haiku": {
                        "supports_images": True,
                        "supports_documents": True,
                        "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
                        "supported_document_formats": ["pdf", "txt", "md", "json", "xml", "csv"],
                        "max_file_size": 20 * 1024 * 1024,
                        "max_files_per_message": 10
                    },
                    "default": {
                        "supports_images": False,
                        "supports_documents": False,
                        "supported_image_formats": [],
                        "supported_document_formats": [],
                        "max_file_size": 0,
                        "max_files_per_message": 0
                    }
                }
            }

            # 获取服务商配置
            provider_config = capabilities_config.get(provider.lower())
            if provider_config is None:
                # 未知服务商，返回不支持
                logger.warning(f"未知服务商: {provider}")
                return {
                    "success": True,
                    "capabilities": {
                        "supports_images": False,
                        "supports_documents": False,
                        "supported_image_formats": [],
                        "supported_document_formats": [],
                        "max_file_size": 0,
                        "max_files_per_message": 0
                    }
                }

            # 获取模型配置（如果没有找到，使用默认配置）
            model_key = model.lower()
            capabilities = provider_config.get(model_key, provider_config.get("default"))

            logger.info(
                f"模型能力: supports_images={capabilities['supports_images']}, "
                f"supports_documents={capabilities['supports_documents']}"
            )

            return {
                "success": True,
                "capabilities": capabilities
            }

        except Exception as e:
            logger.error(f"获取模型能力失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }


    
    # ==================== 搜索功能 API ====================
    
    def ai_search(self, query: str, max_results: int = None) -> Dict[str, Any]:
        """执行搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数（可选）
            
        Returns:
            {
                "success": bool,
                "results": List[{
                    "title": str,
                    "url": str,
                    "snippet": str,
                    "source": str
                }],
                "count": int,
                "query": str,
                "provider": str
            }
        """
        try:
            from backend.src.core.ai.search import SearchManager
            
            search_manager = SearchManager()
            
            # 执行搜索（同步包装异步调用）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    search_manager.search(query, max_results=max_results)
                )
            finally:
                loop.close()
            
            # 获取配置以返回provider信息
            config = search_manager.get_config()
            
            return {
                "success": True,
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "source": r.source
                    }
                    for r in results
                ],
                "count": len(results),
                "query": query,
                "provider": config.get("provider", "unknown")
            }
            
        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def ai_get_search_config(self) -> Dict[str, Any]:
        """获取搜索配置
        
        Returns:
            {
                "success": bool,
                "config": {
                    "enabled": bool,
                    "provider": str,
                    "max_results": int,
                    "timeout": int,
                    "providers": {...}
                }
            }
        """
        try:
            from backend.src.core.ai.search import SearchManager
            
            search_manager = SearchManager()
            config = search_manager.get_config()
            
            return {
                "success": True,
                "config": config
            }
            
        except Exception as e:
            logger.error(f"获取搜索配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def ai_update_search_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """更新搜索配置
        
        Args:
            config: 新配置
            
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            from backend.src.core.ai.search import SearchManager
            
            search_manager = SearchManager()
            success, message = search_manager.update_config(config)
            
            return {
                "success": success,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"更新搜索配置失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def ai_test_search_connection(self, provider: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """测试搜索引擎连接
        
        Args:
            provider: 搜索引擎名称
            config: 搜索引擎配置（可选）
            
        Returns:
            {
                "success": bool,
                "message": str,
                "latency": float
            }
        """
        try:
            from backend.src.core.ai.search import SearchManager
            
            search_manager = SearchManager()
            
            # 执行测试（同步包装异步调用）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success, message, latency = loop.run_until_complete(
                    search_manager.test_provider(provider, config)
                )
            finally:
                loop.close()
            
            return {
                "success": success,
                "message": message,
                "latency": latency
            }
            
        except Exception as e:
            logger.error(f"测试搜索连接失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "latency": 0.0
            }

    # ==================== 系统提示词管理 API ====================
    
    def ai_get_system_prompts(self) -> Dict[str, Any]:
        """
        获取所有系统提示词预设
        
        Returns:
            {
                "success": bool,
                "presets": [
                    {
                        "id": str,
                        "name": str,
                        "content": str,
                        "created_at": str,
                        "updated_at": str
                    }
                ],
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info("获取所有系统提示词预设")
            presets = self.system_prompt_service.get_all_presets()
            return {
                "success": True,
                "presets": presets
            }
        except Exception as e:
            logger.error(f"获取系统提示词预设失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_create_system_prompt(self, name: str, content: str) -> Dict[str, Any]:
        """
        创建新的系统提示词预设
        
        Args:
            name: 预设名称
            content: 提示词内容
            
        Returns:
            {
                "success": bool,
                "preset": {
                    "id": str,
                    "name": str,
                    "content": str,
                    "created_at": str,
                    "updated_at": str
                } | None,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"创建系统提示词预设: {name}")
            preset = self.system_prompt_service.create_preset(name, content)
            return {
                "success": True,
                "preset": preset
            }
        except ValueError as e:
            # 验证错误（名称为空、内容为空、名称重复）
            logger.warning(f"创建系统提示词预设验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"创建系统提示词预设失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_update_system_prompt(
        self, 
        preset_id: str, 
        name: str = None, 
        content: str = None
    ) -> Dict[str, Any]:
        """
        更新现有系统提示词预设
        
        Args:
            preset_id: 预设ID
            name: 新名称（可选）
            content: 新内容（可选）
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"更新系统提示词预设: {preset_id}")
            success = self.system_prompt_service.update_preset(preset_id, name, content)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "预设不存在"
                }
        except ValueError as e:
            # 验证错误
            logger.warning(f"更新系统提示词预设验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"更新系统提示词预设失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_delete_system_prompt(self, preset_id: str) -> Dict[str, Any]:
        """
        删除系统提示词预设
        
        Args:
            preset_id: 预设ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"删除系统提示词预设: {preset_id}")
            success = self.system_prompt_service.delete_preset(preset_id)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "预设不存在"
                }
        except Exception as e:
            logger.error(f"删除系统提示词预设失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_set_active_system_prompt(
        self, 
        topic_id: str, 
        preset_id: str = None
    ) -> Dict[str, Any]:
        """
        设置对话的激活系统提示词预设
        
        Args:
            topic_id: 对话ID
            preset_id: 预设ID（None表示"无"）
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"设置对话 {topic_id} 的激活系统提示词: {preset_id}")
            success = self.system_prompt_service.set_active_preset(topic_id, preset_id)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "设置失败，预设可能不存在"
                }
        except Exception as e:
            logger.error(f"设置激活系统提示词失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def ai_get_active_system_prompt(self, topic_id: str) -> Dict[str, Any]:
        """
        获取对话的激活系统提示词预设
        
        Args:
            topic_id: 对话ID
            
        Returns:
            {
                "success": bool,
                "preset_id": str | None,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"获取对话 {topic_id} 的激活系统提示词")
            preset_id = self.system_prompt_service.get_active_preset(topic_id)
            
            return {
                "success": True,
                "preset_id": preset_id
            }
        except Exception as e:
            logger.error(f"获取激活系统提示词失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
