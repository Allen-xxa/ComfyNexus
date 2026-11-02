"""
缓存管理器

负责插件市场数据的本地缓存管理，包括：
- 插件列表缓存
- 推荐列表缓存
- 缓存有效期检查
- 缓存清除
"""

import json
import time
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from .logger import marketplace_logger
from .constants import (
    CACHE_DURATION,
    PLUGINS_CACHE_FILE,
    RECOMMENDED_CACHE_FILE,
    get_cache_dir
)


class CacheManager:
    """
    缓存管理器
    
    管理插件市场数据的本地缓存，提供读写、有效期检查和清除功能。
    缓存文件使用 JSON 格式存储，包含数据和元数据（时间戳）。
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: Optional[int] = None):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径，如果为 None 则使用默认路径
            ttl_seconds: 缓存有效期（秒），None 时使用默认值
        """
        # 使用私有属性存储 Path 对象，避免 pywebview 序列化错误
        self._cache_dir = cache_dir or get_cache_dir()
        self._plugins_cache_file = self._cache_dir / PLUGINS_CACHE_FILE
        self._recommended_cache_file = self._cache_dir / RECOMMENDED_CACHE_FILE
        self._ttl = ttl_seconds if ttl_seconds and ttl_seconds > 0 else CACHE_DURATION
        
        # 确保缓存目录存在
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        marketplace_logger.debug(f"缓存管理器已初始化，缓存目录: {self._cache_dir}, TTL: {self._ttl}s")
    
    def get_plugins_cache(self, allow_stale: bool = False) -> Optional[List[Dict]]:
        """
        获取插件列表缓存
        
        Args:
            allow_stale: True 时忽略有效期，只要文件可解析就返回。
                用于"先把历史缓存渲染出来，再后台拉新数据"的场景——
                插件更新以天为单位，过期几小时的列表依然可用，
                总比让用户对着空白页等网络超时好。
        
        Returns:
            插件列表（字典列表）或 None（缓存不可用）
        """
        return self._read_cache(self._plugins_cache_file, "插件列表", allow_stale=allow_stale)
    
    def get_plugins_cache_meta(self) -> Dict:
        """
        获取插件列表缓存的元信息（不加载完整数据）
        
        Returns:
            {
                'exists': bool,        # 缓存文件是否存在
                'timestamp': float,    # 写入时间戳，不存在时为 0
                'age_seconds': float,  # 距今多少秒
                'is_fresh': bool,      # 是否在有效期内
                'count': int,          # 条目数，读不出来时为 0
            }
        """
        return self._read_cache_meta(self._plugins_cache_file)
    
    def set_plugins_cache(self, plugins: List[Dict]) -> None:
        """
        设置插件列表缓存
        
        将插件列表写入缓存文件，并记录当前时间戳。
        
        Args:
            plugins: 插件列表（字典列表）
        """
        self._write_cache(self._plugins_cache_file, plugins, "插件列表")
    
    def get_recommended_cache(self, allow_stale: bool = False) -> Optional[List[Dict]]:
        """
        获取推荐列表缓存
        
        Args:
            allow_stale: True 时忽略有效期
        
        Returns:
            推荐插件列表（字典列表）或 None
        """
        return self._read_cache(self._recommended_cache_file, "推荐列表", allow_stale=allow_stale)
    
    def set_recommended_cache(self, plugins: List[Dict]) -> None:
        """
        设置推荐列表缓存
        
        将推荐插件列表写入缓存文件，并记录当前时间戳。
        
        Args:
            plugins: 推荐插件列表（字典列表）
        """
        self._write_cache(self._recommended_cache_file, plugins, "推荐列表")
    
    def clear_cache(self) -> None:
        """
        清除所有缓存
        
        删除所有缓存文件（插件列表和推荐列表）。
        """
        try:
            # 删除插件列表缓存
            if self._plugins_cache_file.exists():
                self._plugins_cache_file.unlink()
                marketplace_logger.debug(f"已删除插件列表缓存: {self._plugins_cache_file}")
            
            # 删除推荐列表缓存
            if self._recommended_cache_file.exists():
                self._recommended_cache_file.unlink()
                marketplace_logger.debug(f"已删除推荐列表缓存: {self._recommended_cache_file}")
            
            marketplace_logger.debug("所有缓存已清除")
        except Exception as e:
            marketplace_logger.error(f"清除缓存失败: {e}")
            raise
    
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """
        检查缓存是否有效
        
        缓存有效的条件：
        1. 文件存在
        2. 文件修改时间在有效期内（默认 24 小时，可由设置覆盖）
        3. 文件内容可以正确解析为 JSON
        
        Args:
            cache_file: 缓存文件路径
            
        Returns:
            True 如果缓存有效，否则 False
        """
        # 检查文件是否存在
        if not cache_file.exists():
            marketplace_logger.debug(f"缓存文件不存在: {cache_file}")
            return False
        
        try:
            # 检查文件修改时间
            mtime = cache_file.stat().st_mtime
            age = time.time() - mtime
            
            if age > self._ttl:
                marketplace_logger.debug(
                    f"缓存已过期: {cache_file}, "
                    f"年龄: {age:.0f}秒, "
                    f"有效期: {self._ttl}秒"
                )
                return False
            
            # 尝试解析文件内容
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 验证数据结构
                if not isinstance(data, dict):
                    marketplace_logger.warning(f"缓存文件格式错误（不是字典）: {cache_file}")
                    return False
                
                if 'timestamp' not in data or 'data' not in data:
                    marketplace_logger.warning(f"缓存文件缺少必需字段: {cache_file}")
                    return False
                
                if not isinstance(data['data'], list):
                    marketplace_logger.warning(f"缓存数据不是列表: {cache_file}")
                    return False
            
            marketplace_logger.debug(f"缓存有效: {cache_file}, 年龄: {age:.0f}秒")
            return True
            
        except json.JSONDecodeError as e:
            marketplace_logger.warning(f"缓存文件 JSON 解析失败: {cache_file}, 错误: {e}")
            return False
        except Exception as e:
            marketplace_logger.error(f"检查缓存有效性时发生错误: {cache_file}, 错误: {e}")
            return False
    
    def _read_cache_meta(self, cache_file: Path) -> Dict:
        """
        读取缓存元信息（只解析顶层，用于判断是否新鲜）
        
        Args:
            cache_file: 缓存文件路径
            
        Returns:
            {'exists', 'timestamp', 'age_seconds', 'is_fresh', 'count'}
        """
        meta = {
            'exists': cache_file.exists(),
            'timestamp': 0.0,
            'age_seconds': 0.0,
            'is_fresh': False,
            'count': 0,
        }
        if not meta['exists']:
            return meta

        try:
            mtime = cache_file.stat().st_mtime
            meta['timestamp'] = mtime
            meta['age_seconds'] = max(0.0, time.time() - mtime)
            meta['is_fresh'] = meta['age_seconds'] <= self._ttl

            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                meta['timestamp'] = float(data.get('timestamp') or mtime)
                payload = data.get('data')
                if isinstance(payload, list):
                    meta['count'] = len(payload)
        except Exception as e:
            marketplace_logger.warning(f"读取缓存元信息失败: {cache_file}, 错误: {e}")

        return meta

    def _read_cache(
        self,
        cache_file: Path,
        cache_name: str,
        allow_stale: bool = False,
    ) -> Optional[List[Dict]]:
        """
        读取缓存文件
        
        Args:
            cache_file: 缓存文件路径
            cache_name: 缓存名称（用于日志）
            allow_stale: True 时跳过有效期检查，只要结构合法就返回
            
        Returns:
            缓存数据（字典列表）或 None
        """
        if not allow_stale and not self._is_cache_valid(cache_file):
            return None
        if allow_stale and not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            data = cache_data['data']
            timestamp = cache_data['timestamp']
            
            age = max(0.0, time.time() - float(timestamp))
            expired_note = "（已过期，先展示）" if age > self._ttl else ""
            
            marketplace_logger.info(
                f"从缓存加载{cache_name}: {len(data)} 项, "
                f"缓存时间: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
                f"{expired_note}"
            )
            
            return data
            
        except json.JSONDecodeError as e:
            marketplace_logger.error(
                f"读取{cache_name}缓存失败: JSON 解析错误, "
                f"文件: {cache_file}, 错误: {str(e)}"
            )
            self._try_remove_corrupted_cache(cache_file, cache_name)
            return None
        except KeyError as e:
            marketplace_logger.error(
                f"读取{cache_name}缓存失败: 缓存结构不完整, "
                f"文件: {cache_file}, 缺少字段: {str(e)}"
            )
            self._try_remove_corrupted_cache(cache_file, cache_name)
            return None
        except PermissionError as e:
            marketplace_logger.error(
                f"读取{cache_name}缓存失败: 权限被拒绝, "
                f"文件: {cache_file}, 错误: {str(e)}"
            )
            return None
        except Exception as e:
            marketplace_logger.error(
                f"读取{cache_name}缓存失败: 未知错误, "
                f"文件: {cache_file}, 错误类型: {type(e).__name__}, 错误: {str(e)}"
            )
            return None
    
    def _try_remove_corrupted_cache(self, cache_file: Path, cache_name: str) -> None:
        """
        尝试删除损坏的缓存文件
        
        Args:
            cache_file: 缓存文件路径
            cache_name: 缓存名称（用于日志）
        """
        try:
            if cache_file.exists():
                cache_file.unlink()
                marketplace_logger.info(f"已删除损坏的{cache_name}缓存文件: {cache_file}")
        except Exception as delete_error:
            marketplace_logger.warning(
                f"删除损坏的{cache_name}缓存文件失败: "
                f"文件: {cache_file}, 错误: {str(delete_error)}"
            )
    
    def _write_cache(self, cache_file: Path, data: List[Dict], cache_name: str) -> None:
        """
        写入缓存文件
        
        Args:
            cache_file: 缓存文件路径
            data: 要缓存的数据（字典列表）
            cache_name: 缓存名称（用于日志）
        """
        try:
            cache_data = {
                'timestamp': time.time(),
                'data': data
            }
            
            temp_file = cache_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            if cache_file.exists():
                cache_file.unlink()
            
            temp_file.rename(cache_file)
            
            marketplace_logger.info(
                f"{cache_name}已缓存: {len(data)} 项, "
                f"文件: {cache_file}"
            )
            
        except PermissionError as e:
            marketplace_logger.error(
                f"写入{cache_name}缓存失败: 权限被拒绝, "
                f"文件: {cache_file}, 错误: {str(e)}"
            )
            raise
        except OSError as e:
            marketplace_logger.error(
                f"写入{cache_name}缓存失败: 系统错误, "
                f"文件: {cache_file}, 错误: {str(e)}"
            )
            raise
        except Exception as e:
            marketplace_logger.error(
                f"写入{cache_name}缓存失败: 未知错误, "
                f"文件: {cache_file}, 错误类型: {type(e).__name__}, 错误: {str(e)}"
            )
            raise
