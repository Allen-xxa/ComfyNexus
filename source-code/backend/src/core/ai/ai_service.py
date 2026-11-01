"""
AIService 服务层

AI 助手的核心服务，负责：
- 消息发送和流式响应
- 集成 TopicManager、MessageRepository、ProviderFactory
- 管理生成任务（用于停止生成）
"""

import asyncio
import logging
from typing import Dict, Any, AsyncIterator, Optional
from datetime import datetime

from .topic_manager import TopicManager
from .message_repository import MessageRepository
from .models import Message
from .providers.factory import ProviderFactory
from .providers.base_provider import StreamChunk
from .security_utils import mask_api_key

logger = logging.getLogger(__name__)


class AIService:
    """AI 服务核心类
    
    负责协调各个组件，实现完整的 AI 对话功能。
    """
    
    def __init__(self):
        """初始化 AI 服务"""
        self.topic_manager = TopicManager()
        self.message_repository = MessageRepository()
        
        # 生成任务管理：topic_id -> asyncio.Task
        self._generation_tasks: Dict[str, asyncio.Task] = {}
        
        # 取消标志：topic_id -> bool
        self._cancel_flags: Dict[str, bool] = {}
        
        # 活跃的 HTTP sessions：topic_id -> aiohttp.ClientSession
        self._active_sessions: Dict[str, Any] = {}
    
    async def send_message(
        self,
        topic_id: str,
        content: str,
        provider_name: str,
        model: str,
        config: Dict[str, Any],
        web_search_enabled: bool = False,
        system_prompt: str = None,
        files: list = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """发送消息并返回流式响应
        
        Args:
            topic_id: 话题 ID
            content: 用户消息内容
            provider_name: Provider 名称（openai/spark/volcengine/zhipu/ollama）
            model: 模型名称
            config: Provider 配置
                {
                    "api_key": str,
                    "base_url": str,  # 可选
                    "temperature": float,
                    "max_tokens": int,
                    "deep_thinking": bool,  # 是否启用深度思考
                    ...
                }
            web_search_enabled: 是否启用联网搜索
            system_prompt: 用户自定义的系统提示词（可选）
            files: 文件列表（可选）
        
        Yields:
            Dict[str, Any]: 流式响应事件
                {
                    "type": "start" | "chunk" | "done" | "error",
                    "user_message_id": str,  # 用户消息 ID
                    "ai_message_id": str,    # AI 消息 ID
                    "chunk": str,            # 文本片段（仅 type="chunk" 时）
                    "error": str             # 错误信息（仅 type="error" 时）
                }
        
        Raises:
            ValueError: 当话题不存在或参数无效时抛出
        """
        logger.info(f"[AI Service] send_message() 被调用: topic_id={topic_id}, provider={provider_name}, model={model}, files={len(files) if files else 0}个")
        
        # ===== 关键：立即 yield 一个调试事件，确保生成器开始执行 =====
        # 这个 yield 会让生成器真正开始执行，而不是等到第一个真正的事件
        # 注意：这是一个临时的调试 yield，后续可以移除
        if False:  # 永远不会执行，但会让 Python 识别这是一个生成器
            yield {}
        
        # 验证话题是否存在
        topic = self.topic_manager.get_topic(topic_id)
        if not topic:
            raise ValueError(f"话题不存在: {topic_id}")
        
        # 首次对话时用用户的首条消息生成话题标题，替换默认的「新对话」
        self._maybe_auto_title(topic_id, topic.name, content)
        
        # 验证消息内容（允许只有文件而没有文本）
        if (not content or not content.strip()) and (not files or len(files) == 0):
            raise ValueError("消息内容和文件不能同时为空")
        
        # 提取深度思考标志
        deep_thinking = config.get("deep_thinking", False)
        logger.info(f"[AI Service] ========== 开始处理消息 ==========")
        logger.info(f"[AI Service] 话题ID: {topic_id}")
        logger.info(f"[AI Service] 内容长度: {len(content)}")
        logger.info(f"[AI Service] 深度思考模式: {deep_thinking}")
        logger.info(f"[AI Service] 文件数量: {len(files) if files else 0}")
        
        # 记录文件信息
        if files:
            logger.info(f"[AI Service] 收到 {len(files)} 个文件")
            for i, file in enumerate(files):
                logger.debug(f"[AI Service] 文件 {i+1}: type={file.get('type')}, name={file.get('metadata', {}).get('original_name', 'unknown')}")
        
        # 创建用户消息
        logger.info(f"[AI Service] 创建用户消息...")
        try:
            # 如果没有文本内容但有文件，使用默认文本
            message_content = content if content and content.strip() else "[图片]" if files else ""
            
            user_message = Message.create_user_message(
                topic_id=topic_id,
                content=message_content,
                files=files  # 传递文件列表
            )
            logger.info(f"[AI Service] 用户消息创建成功: {user_message.id}")
        except Exception as e:
            logger.error(f"[AI Service] 创建用户消息失败: {e}", exc_info=True)
            raise
        
        # 保存用户消息
        self.message_repository.save_message(user_message)
        
        # 创建 AI 消息（占位）
        ai_message = Message.create_assistant_message(
            topic_id=topic_id,
            content="...",  # 占位符，流式生成时逐步填充
            model=model
        )
        
        # 保存 AI 消息占位
        self.message_repository.save_message(ai_message)
        
        # 发送开始事件
        yield {
            "type": "start",
            "user_message_id": user_message.id,
            "ai_message_id": ai_message.id
        }
        
        # 初始化取消标志
        self._cancel_flags[topic_id] = False
        
        # 搜索上下文（如果启用联网搜索）
        search_context = ""
        search_results_display = ""  # 用于在消息中显示的搜索结果
        logger.debug(f"[AI Service] ========== 联网搜索调试开始 ==========")
        logger.debug(f"[AI Service] web_search_enabled = {web_search_enabled} (类型: {type(web_search_enabled)})")
        logger.debug(f"[AI Service] 用户消息: {content[:100]}")
        logger.info(f"[AI Service] web_search_enabled = {web_search_enabled}")
        
        if web_search_enabled:
            try:
                from backend.src.core.ai.search import SearchManager
                
                logger.debug(f"[AI Service] ✓ 联网搜索已启用，开始搜索")
                logger.info(f"[AI Service] 联网搜索已启用，开始搜索: {content}")
                search_manager = SearchManager()
                search_results = await search_manager.search(content)
                
                logger.debug(f"[AI Service] ✓ 搜索完成，返回 {len(search_results) if search_results else 0} 条结果")
                
                if search_results:
                    search_context = self._format_search_results(search_results)
                    search_results_display = self._format_search_results_for_display(search_results)
                    logger.debug(f"[AI Service] ✓ 搜索上下文已生成，长度: {len(search_context)} 字符")
                    logger.debug(f"[AI Service] 搜索上下文预览（前200字符）:")
                    logger.debug(search_context[:200])
                    logger.info(f"[AI Service] 搜索完成，返回{len(search_results)}条结果")
                else:
                    logger.debug("[AI Service] ✗ 搜索返回空结果")
                    logger.warning("[AI Service] 搜索返回空结果")
                    
            except Exception as e:
                logger.debug(f"[AI Service] ✗ 搜索失败: {e}")
                logger.error(f"[AI Service] 搜索失败: {e}", exc_info=True)
                # 搜索失败不影响对话，继续执行
        else:
            logger.debug(f"[AI Service] ✗ 联网搜索未启用")
        
        logger.debug(f"[AI Service] ========== 联网搜索调试结束 ==========")
        
        try:
            # 创建 Provider
            provider_config = {
                **config,
                "model": model
            }
            logger.info(
                f"[AI Service] 创建 Provider: provider_name={provider_name}, "
                f"model={model}"
            )
            safe_config = {
                **provider_config,
                "api_key": mask_api_key(provider_config.get("api_key", "")),
            }
            logger.debug(f"[AI Service] Provider 配置: {safe_config}")
            
            # 从 config 中提取 use_proxy 参数（如果存在）
            use_proxy = config.get("use_system_proxy", False)
            logger.info(f"[AI Service] 使用系统代理: {use_proxy}")
            
            provider = ProviderFactory.create(provider_name, provider_config, use_proxy=use_proxy)
            logger.info(f"[AI Service] Provider 创建成功: {type(provider).__name__}")
            
            # 获取历史消息（用于上下文）
            history_messages = self.message_repository.get_messages(
                topic_id=topic_id,
                limit=100  # 最多获取 100 条历史消息
            )
            
            # 构建消息列表（排除当前 AI 消息占位）
            messages = []
            
            # 准备最终的系统提示词
            final_system_prompt = None
            
            # 1. 如果用户提供了自定义系统提示词，使用它作为基础
            if system_prompt and system_prompt.strip():
                final_system_prompt = system_prompt.strip()
                logger.info(f"[AI Service] 使用用户自定义系统提示词，长度: {len(final_system_prompt)}")
                logger.debug(f"[AI Service] 用户系统提示词前100字符: {final_system_prompt[:100]}")
            
            # 2. 如果有搜索结果，追加搜索上下文到系统提示词
            if search_context:
                current_date = datetime.now().strftime("%Y年%m月%d日 %H:%M")
                
                search_system_prompt = f"""当前时间是：{current_date}

以下是关于用户问题的最新互联网搜索结果，请基于这些信息回答用户的问题：

{search_context}

请注意：
1. 如果用户询问时间、日期相关问题，优先使用上面提供的当前时间
2. 优先使用搜索结果中的信息回答其他问题
3. 如果搜索结果不相关，可以使用你的知识回答
4. 引用信息时可以提及来源"""
                
                # 如果已经有用户自定义的系统提示词，将搜索上下文追加到后面
                if final_system_prompt:
                    final_system_prompt = f"{final_system_prompt}\n\n---\n\n{search_system_prompt}"
                    logger.info(f"[AI Service] 合并用户系统提示词和搜索上下文，总长度: {len(final_system_prompt)}")
                else:
                    final_system_prompt = search_system_prompt
                    logger.info(f"[AI Service] 使用搜索上下文作为系统提示词，长度: {len(final_system_prompt)}")
                
                logger.debug(f"[AI Service] ========== 系统提示词调试 ==========")
                logger.debug(f"[AI Service] ✓ 最终系统提示词已生成")
                logger.debug(f"[AI Service] 系统提示词长度: {len(final_system_prompt)} 字符")
                logger.debug(f"[AI Service] 系统提示词预览（前300字符）:")
                logger.debug(final_system_prompt[:300])
                logger.debug(f"[AI Service] ========================================")
            else:
                if not final_system_prompt:
                    logger.debug(f"[AI Service] ✗ 没有系统提示词")
            
            # 添加历史消息
            for msg in history_messages:
                if msg.id not in (user_message.id, ai_message.id):  # 排除本轮消息，后面会显式添加当前用户消息
                    try:
                        msg_dict = {
                            "role": msg.role,
                            "content": msg.content
                        }
                        
                        # 如果消息包含文件，添加到消息中
                        if msg.files:
                            logger.info(f"[AI Service] 历史消息 {msg.id} 包含 {len(msg.files)} 个文件")
                            logger.debug(f"[AI Service] 文件数据结构: {msg.files}")
                            
                            # 对于支持多模态的模型，需要将内容转换为特殊格式
                            # 这里我们将文件信息添加到 content 中
                            content_parts = [{"type": "text", "text": msg.content}]
                            
                            for file in msg.files:
                                try:
                                    if file.get("type") == "image":
                                        # 添加图片
                                        # 检查 content 字段是否包含完整的 data URL
                                        content = file.get('content', '')
                                        if content.startswith('data:'):
                                            # 已经是完整的 data URL
                                            image_url = content
                                        else:
                                            # 需要构建 data URL
                                            mime_type = file.get('metadata', {}).get('mime_type', 'image/png')
                                            image_url = f"data:{mime_type};base64,{content}"
                                        
                                        content_parts.append({
                                            "type": "image_url",
                                            "image_url": {
                                                "url": image_url
                                            }
                                        })
                                        file_name = file.get('metadata', {}).get('name', 'unknown')
                                        logger.debug(f"[AI Service] 添加图片到历史消息: {file_name}")
                                    elif file.get("type") == "document":
                                        # 对于文档，将提取的文本添加到消息内容中
                                        if file.get("content_type") == "text":
                                            file_name = file.get('metadata', {}).get('name', 'unknown')
                                            content_parts[0]["text"] += f"\n\n[文档内容: {file_name}]\n{file.get('content')}"
                                            logger.debug(f"[AI Service] 添加文档文本到历史消息: {file_name}")
                                except Exception as file_error:
                                    logger.error(f"[AI Service] 处理历史消息文件失败: {file_error}", exc_info=True)
                                    logger.error(f"[AI Service] 文件数据: {file}")
                                    # 继续处理其他文件
                                    continue
                            
                            # 如果有多个部分（文本+图片），使用多模态格式
                            if len(content_parts) > 1:
                                msg_dict["content"] = content_parts
                            else:
                                msg_dict["content"] = content_parts[0]["text"]
                        
                        messages.append(msg_dict)
                    except Exception as msg_error:
                        logger.error(f"[AI Service] 处理历史消息失败: {msg_error}", exc_info=True)
                        logger.error(f"[AI Service] 消息数据: id={msg.id}, role={msg.role}, files={msg.files}")
                        # 跳过这条消息，继续处理其他消息
                        continue
            
            # 添加当前用户消息（包含文件）
            current_msg_dict = {
                "role": "user",
                "content": message_content  # 使用处理后的内容
            }
            
            # 如果当前消息包含文件
            if files:
                logger.info(f"[AI Service] 当前消息包含 {len(files)} 个文件")
                content_parts = [{"type": "text", "text": message_content}]
                
                for file in files:
                    if file.get("type") == "image":
                        # 添加图片
                        # 注意：file.get('content') 已经是完整的 data URL（data:image/xxx;base64,xxx）
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": file.get('content')  # 直接使用，不要再添加前缀
                            }
                        })
                        logger.info(f"[AI Service] 添加图片到当前消息: {file.get('metadata', {}).get('original_name', 'unknown')}")
                    elif file.get("type") == "document":
                        # 对于文档，将提取的文本添加到消息内容中
                        if file.get("content_type") == "text":
                            content_parts[0]["text"] += f"\n\n[文档内容: {file.get('metadata', {}).get('original_name', 'unknown')}]\n{file.get('content')}"
                            logger.info(f"[AI Service] 添加文档文本到当前消息: {file.get('metadata', {}).get('original_name', 'unknown')}")
                
                # 如果有多个部分（文本+图片），使用多模态格式
                if len(content_parts) > 1:
                    current_msg_dict["content"] = content_parts
                    logger.info(f"[AI Service] 使用多模态格式，包含 {len(content_parts)} 个部分")
                else:
                    current_msg_dict["content"] = content_parts[0]["text"]
            
            messages.append(current_msg_dict)
            
            # 流式生成
            logger.debug(f"[AI Service] 开始流式生成")
            logger.debug(f"[AI Service] - 历史消息数: {len(messages)}")
            logger.debug(f"[AI Service] - 深度思考: {deep_thinking}")
            logger.debug(f"[AI Service] - 联网搜索: {web_search_enabled}")
            logger.debug(f"[AI Service] - final_system_prompt 是否存在: {final_system_prompt is not None}")
            if final_system_prompt:
                logger.debug(f"[AI Service] - final_system_prompt 长度: {len(final_system_prompt)}")
                logger.debug(f"[AI Service] - final_system_prompt 前100字符: {final_system_prompt[:100]}")
            
            # 打印消息结构（用于调试）
            logger.info(f"[AI Service] 消息列表结构:")
            for i, msg in enumerate(messages):
                if isinstance(msg.get("content"), list):
                    logger.info(f"[AI Service]   消息 {i}: role={msg['role']}, content=多模态({len(msg['content'])}部分)")
                    for j, part in enumerate(msg["content"]):
                        if part.get("type") == "text":
                            logger.info(f"[AI Service]     部分 {j}: 文本({len(part['text'])}字符)")
                        elif part.get("type") == "image_url":
                            logger.info(f"[AI Service]     部分 {j}: 图片")
                else:
                    logger.info(f"[AI Service]   消息 {i}: role={msg['role']}, content=文本({len(msg['content'])}字符)")
            
            logger.info(f"[AI Service] 开始流式生成，历史消息数: {len(messages)}, 深度思考: {deep_thinking}, 联网搜索: {web_search_enabled}")
            if final_system_prompt:
                logger.info(f"[AI Service] 系统提示词已设置，长度: {len(final_system_prompt)}")
            
            generated_content = ""
            chunk_count = 0
            final_finish_reason = None
            
            # 如果有搜索结果，先发送搜索结果标记
            if search_results_display:
                yield {
                    "type": "chunk",
                    "user_message_id": user_message.id,
                    "ai_message_id": ai_message.id,
                    "chunk": search_results_display
                }
                generated_content += search_results_display
            
            logger.info(f"[AI Service] 调用 provider.chat_stream()")
            logger.info(f"[AI Service] - messages 数量: {len(messages)}")
            logger.info(f"[AI Service] - system_prompt 长度: {len(final_system_prompt) if final_system_prompt else 0}")
            logger.info(f"[AI Service] - deep_thinking: {deep_thinking}")
            
            try:
                stream_generator = provider.chat_stream(messages, system_prompt=final_system_prompt, deep_thinking=deep_thinking)
                logger.info(f"[AI Service] chat_stream() 生成器已创建: {type(stream_generator)}")
                
                async for stream_chunk in stream_generator:
                    chunk_count += 1
                    
                    # 检查是否被取消
                    if self._cancel_flags.get(topic_id, False):
                        logger.info(f"[AI Service] 生成被取消: topic_id={topic_id}")
                        break
                    
                    if isinstance(stream_chunk, str):
                        stream_chunk = StreamChunk(content=stream_chunk)
                    
                    # 记录 finish_reason
                    if stream_chunk.finish_reason:
                        final_finish_reason = stream_chunk.finish_reason
                        logger.info(f"[AI Service] 检测到 finish_reason: {final_finish_reason}")
                    
                    # 累积生成内容
                    if stream_chunk.content:
                        generated_content += stream_chunk.content
                        
                        # 发送 chunk 事件
                        yield {
                            "type": "chunk",
                            "user_message_id": user_message.id,
                            "ai_message_id": ai_message.id,
                            "chunk": stream_chunk.content
                        }
                
                logger.info(f"[AI Service] chat_stream() 迭代完成")
            except Exception as stream_error:
                logger.error(f"[AI Service] chat_stream() 异常: {type(stream_error).__name__}: {stream_error}", exc_info=True)
                error_text = str(stream_error)
                if generated_content.strip():
                    interruption_notice = f"\n\n⚠️ 生成中断：{error_text}\n\n已保留当前已生成内容。"
                    generated_content += interruption_notice
                    yield {
                        "type": "chunk",
                        "user_message_id": user_message.id,
                        "ai_message_id": ai_message.id,
                        "chunk": interruption_notice
                    }
                else:
                    ai_message.content = f"⚠️ 生成失败：{error_text}"
                    ai_message.timestamp = datetime.now().isoformat()
                    self.message_repository.save_message(ai_message)
                    yield {
                        "type": "error",
                        "user_message_id": user_message.id,
                        "ai_message_id": ai_message.id,
                        "error": error_text
                    }
                    return
            
            logger.info(f"[AI Service] 流式生成完成，共收到 {chunk_count} 个 chunk，总长度: {len(generated_content)}")
            
            # 根据 finish_reason 处理不同情况
            if final_finish_reason == 'content_filter':
                # 内容被过滤，发送错误事件
                yield {
                    "type": "error",
                    "user_message_id": user_message.id,
                    "ai_message_id": ai_message.id,
                    "error": "⚠️ 回答因内容审核被截断。请修改您的问题后重试。"
                }
                return
            elif final_finish_reason == 'length':
                # 达到长度限制，追加提示
                length_warning = "\n\n⚠️ 回答因达到长度限制被截断，请继续提问或增加 max_tokens 设置。"
                generated_content += length_warning
                yield {
                    "type": "chunk",
                    "user_message_id": user_message.id,
                    "ai_message_id": ai_message.id,
                    "chunk": length_warning
                }
            
            # 更新 AI 消息内容
            ai_message.content = generated_content
            ai_message.timestamp = datetime.now().isoformat()
            
            logger.info(f"[AI Service] 准备保存消息到数据库: id={ai_message.id}, 内容长度={len(ai_message.content)}, strip后长度={len(ai_message.content.strip())}")
            
            # 只有在有内容时才保存消息
            if generated_content.strip():
                self.message_repository.save_message(ai_message)
                logger.info(f"[AI Service] 消息已保存到数据库")
            else:
                logger.warning(f"[AI Service] AI 消息内容为空，不保存: topic_id={topic_id}, chunk_count={chunk_count}, generated_content长度={len(generated_content)}")
                logger.warning(f"[AI Service] generated_content repr: {repr(generated_content)}")
                
                # 如果内容为空且没有明确的 finish_reason，发送错误
                if not final_finish_reason:
                    yield {
                        "type": "error",
                        "user_message_id": user_message.id,
                        "ai_message_id": ai_message.id,
                        "error": "AI 返回了空内容。可能原因：网络问题或模型无法响应。"
                    }
                    return
            
            # 发送完成事件
            yield {
                "type": "done",
                "user_message_id": user_message.id,
                "ai_message_id": ai_message.id
            }
        
        except Exception as e:
            logger.error(f"生成失败: {e}", exc_info=True)
            
            try:
                ai_message.content = f"⚠️ 生成失败：{str(e)}"
                ai_message.timestamp = datetime.now().isoformat()
                self.message_repository.save_message(ai_message)
            except Exception as save_error:
                logger.error(f"[AI Service] 保存错误消息失败: {save_error}", exc_info=True)
            
            # 发送错误事件
            yield {
                "type": "error",
                "user_message_id": user_message.id,
                "ai_message_id": ai_message.id,
                "error": str(e)
            }
        
        finally:
            # 清理取消标志
            if topic_id in self._cancel_flags:
                del self._cancel_flags[topic_id]
            
            # 清理生成任务
            if topic_id in self._generation_tasks:
                del self._generation_tasks[topic_id]
            
            # 清理活跃的 session
            if topic_id in self._active_sessions:
                del self._active_sessions[topic_id]
    
    def stop_generation(self, topic_id: str) -> bool:
        """停止指定话题的 AI 生成
        
        此方法会：
        1. 设置取消标志，让流式生成循环检测到并退出
        2. 取消正在运行的 asyncio Task
        3. 关闭活跃的 HTTP session，释放 API 连接
        
        Args:
            topic_id: 话题 ID
        
        Returns:
            是否成功停止（如果没有正在进行的生成，返回 False）
        """
        stopped = False
        
        # 1. 设置取消标志
        if topic_id in self._cancel_flags:
            self._cancel_flags[topic_id] = True
            logger.info(f"[AI Service] 已设置取消标志: topic_id={topic_id}")
            stopped = True
        
        # 2. 取消正在运行的 asyncio Task
        if topic_id in self._generation_tasks:
            task = self._generation_tasks[topic_id]
            if not task.done():
                task.cancel()
                logger.info(f"[AI Service] 已取消生成任务: topic_id={topic_id}")
            stopped = True
        
        # 3. 关闭活跃的 HTTP session
        if topic_id in self._active_sessions:
            session = self._active_sessions[topic_id]
            try:
                # 创建一个异步任务来关闭 session
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，创建一个任务来关闭
                    asyncio.create_task(self._close_session_async(topic_id, session))
                else:
                    # 如果事件循环没有运行，直接运行
                    loop.run_until_complete(session.close())
                logger.info(f"[AI Service] 已关闭 HTTP session: topic_id={topic_id}")
            except Exception as e:
                logger.warning(f"[AI Service] 关闭 session 时出错: {e}")
            stopped = True
        
        if not stopped:
            logger.warning(f"[AI Service] 没有正在进行的生成: topic_id={topic_id}")
        
        return stopped
    
    async def _close_session_async(self, topic_id: str, session: Any):
        """异步关闭 HTTP session"""
        try:
            await session.close()
            if topic_id in self._active_sessions:
                del self._active_sessions[topic_id]
            logger.debug(f"[AI Service] session 已异步关闭: topic_id={topic_id}")
        except Exception as e:
            logger.warning(f"[AI Service] 异步关闭 session 时出错: {e}")
    
    def is_generating(self, topic_id: str) -> bool:
        """检查指定话题是否正在生成
        
        Args:
            topic_id: 话题 ID
        
        Returns:
            是否正在生成
        """
        return topic_id in self._cancel_flags

    
    # 视为「未命名」的话题标题，命中时允许自动改写
    _DEFAULT_TOPIC_NAMES = {"新对话", "新话题", "new chat", "new topic", ""}

    @staticmethod
    def _derive_topic_title(content: str, max_len: int = 20) -> str:
        """从用户首条消息推导话题标题"""
        text = " ".join((content or "").split())
        if not text:
            return ""

        # 去掉常见祈使前缀，让标题更接近主题本身
        for prefix in ("请帮我", "帮我", "麻烦", "请", "你能", "可以", "我想"):
            if text.startswith(prefix) and len(text) > len(prefix) + 4:
                text = text[len(prefix):].lstrip("，,。. ：: ")
                break

        if len(text) > max_len:
            return text[:max_len] + "…"
        return text

    def _maybe_auto_title(self, topic_id: str, current_name: str, content: str) -> None:
        """
        话题仍为默认名称时，用首条用户消息自动命名

        原实现只在创建话题时写入「新对话」，之后永不更新，
        导致左侧话题列表全是同名条目，无法区分。
        """
        try:
            if (current_name or "").strip().lower() not in self._DEFAULT_TOPIC_NAMES:
                return

            title = self._derive_topic_title(content)
            if not title:
                return

            if self.topic_manager.rename_topic(topic_id, title):
                logger.info(f"[AI Service] 已自动命名话题: {title}")
        except Exception as e:
            logger.warning(f"[AI Service] 自动命名话题失败: {e}")

    def _format_search_results(self, results) -> str:
        """格式化搜索结果为文本（用于AI上下文）
        
        Args:
            results: 搜索结果列表
            
        Returns:
            格式化后的文本
        """
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""
【搜索结果 {i}】
标题：{result.title}
来源：{result.url}
摘要：{result.snippet}
""")
        return "\n".join(formatted)
    
    def _format_search_results_for_display(self, results) -> str:
        """格式化搜索结果用于在消息中显示
        
        Args:
            results: 搜索结果列表
            
        Returns:
            格式化后的文本（包含特殊标记）
        """
        formatted_results = []
        for i, result in enumerate(results, 1):
            # 清理标题和摘要中的多余空格和换行
            title = ' '.join(result.title.split())
            snippet = ' '.join(result.snippet.split())
            
            formatted_results.append(f"""**{i}. {title}**

{snippet}

🔗 {result.url}

---""")
        
        search_display = f"""【搜索结果】

{chr(10).join(formatted_results)}

【回答】
"""
        return search_display
