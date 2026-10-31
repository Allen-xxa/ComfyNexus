"""
工作流 JSON 解析器

解析 ComfyUI 工作流 JSON 文件，提取节点、连接、插件依赖等信息
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from backend.src.core.workflow.models import (
    PluginDependency,
    get_plugin_color,
    get_plugin_name,
    COMFY_CORE_URL,
)
from backend.src.utils.logger import app_logger as logger


VIRTUAL_NODE_TYPES = {'Reroute', 'Note'}


def is_virtual_node(node_type: str) -> bool:
    """
    检查是否是虚拟节点
    
    虚拟节点包括：
    - Reroute: 连线重定向节点
    - Note: 注释节点
    - workflow/ 或 workflow> 前缀的节点
    
    Args:
        node_type: 节点类型
        
    Returns:
        是否是虚拟节点
    """
    if node_type in VIRTUAL_NODE_TYPES:
        return True
    if node_type.startswith('workflow/') or node_type.startswith('workflow>'):
        return True
    return False


@dataclass
class ParsedNode:
    """解析后的节点信息"""
    id: int
    type: str
    github_url: str
    plugin_name: str
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    pos: Tuple[int, int] = (0, 0)


@dataclass
class ParsedLink:
    """解析后的连接信息"""
    id: int
    source_node_id: int
    source_slot: int
    target_node_id: int
    target_slot: int
    data_type: str


@dataclass
class ParsedWorkflow:
    """解析后的工作流信息"""
    nodes: List[ParsedNode]
    links: List[ParsedLink]
    plugins: List[PluginDependency]
    raw_data: Dict[str, Any]


class WorkflowParser:
    """工作流 JSON 解析器"""

    @staticmethod
    def parse(content: str) -> Optional[ParsedWorkflow]:
        """
        解析工作流 JSON 内容
        
        Args:
            content: JSON 字符串内容
            
        Returns:
            ParsedWorkflow 对象，解析失败返回 None
        """
        try:
            data = json.loads(content)
            return WorkflowParser.parse_data(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"工作流解析失败: {e}")
            return None

    @staticmethod
    def parse_data(data: Dict[str, Any]) -> ParsedWorkflow:
        """
        解析工作流数据字典
        
        Args:
            data: 工作流数据字典
            
        Returns:
            ParsedWorkflow 对象
        """
        nodes_data = data.get("nodes", [])
        links_data = data.get("links", [])
        
        parsed_nodes = []
        plugin_map: Dict[str, PluginDependency] = {}
        
        for node_data in nodes_data:
            node_type = node_data.get("type", "Unknown")
            
            if is_virtual_node(node_type):
                continue
            
            parsed_node = WorkflowParser._parse_node(node_data)
            parsed_nodes.append(parsed_node)
            
            github_url = parsed_node.github_url
            if github_url not in plugin_map:
                plugin_map[github_url] = PluginDependency(
                    github_url=github_url,
                    name=parsed_node.plugin_name,
                    color=get_plugin_color(github_url),
                    node_count=0,
                    nodes=[],
                )
            plugin_map[github_url].node_count += 1
            plugin_map[github_url].nodes.append(parsed_node.type)
        
        if 'extra' in data and 'groupNodes' in data['extra']:
            for group_name, group_data in data['extra']['groupNodes'].items():
                group_nodes = group_data.get('nodes', [])
                for node_data in group_nodes:
                    node_type = node_data.get("type", "Unknown")
                    
                    if is_virtual_node(node_type):
                        continue
                    
                    properties = node_data.get("properties", {})
                    github_url = WorkflowParser._resolve_github_url(node_type, properties)
                    plugin_name = WorkflowParser._get_plugin_name(github_url, node_type)
                    
                    if github_url not in plugin_map:
                        plugin_map[github_url] = PluginDependency(
                            github_url=github_url,
                            name=plugin_name,
                            color=get_plugin_color(github_url),
                            node_count=0,
                            nodes=[],
                        )
                    plugin_map[github_url].node_count += 1
                    if node_type not in plugin_map[github_url].nodes:
                        plugin_map[github_url].nodes.append(node_type)
        
        parsed_links = []
        for link_data in links_data or []:
            parsed_link = WorkflowParser._parse_link(link_data)
            if parsed_link:
                parsed_links.append(parsed_link)
        
        return ParsedWorkflow(
            nodes=parsed_nodes,
            links=parsed_links,
            plugins=list(plugin_map.values()),
            raw_data=data,
        )

    @staticmethod
    def _parse_node(node_data: Dict[str, Any]) -> ParsedNode:
        """
        解析单个节点
        
        Args:
            node_data: 节点数据字典
            
        Returns:
            ParsedNode 对象
        """
        node_id = node_data.get("id", 0)
        node_type = node_data.get("type", "Unknown")
        properties = node_data.get("properties", {})
        
        github_url = WorkflowParser._resolve_github_url(node_type, properties)
        plugin_name = WorkflowParser._get_plugin_name(github_url, node_type)
        
        return ParsedNode(
            id=node_id,
            type=node_type,
            github_url=github_url,
            plugin_name=plugin_name,
            inputs=node_data.get("inputs", []),
            outputs=node_data.get("outputs", []),
            pos=tuple(node_data.get("pos", [0, 0])),
        )

    @staticmethod
    def _resolve_github_url(node_type: str, properties: Dict[str, Any]) -> str:
        """
        解析节点的 GitHub URL
        
        采用 ComfyUI-Manager 的匹配策略：
        1. cnr_id 直接匹配（如果是完整 URL）
        2. preemption_map 优先匹配（内置节点和优先级覆盖）
        3. rext_map 精确匹配（节点到插件列表）
        4. nodename_pattern 正则匹配
        
        Args:
            node_type: 节点类型
            properties: 节点属性
            
        Returns:
            GitHub URL 字符串
        """
        from backend.src.utils.node_mapper import node_mapper, normalize_github_url, COMFY_CORE_URL
        
        if not node_mapper._plugin_info:
            node_mapper.initialize()
        
        cnr_id = properties.get("cnr_id")
        if cnr_id:
            # 特殊处理 comfy-core
            if cnr_id == "comfy-core":
                return COMFY_CORE_URL
            
            # 尝试标准化为完整 URL
            normalized = normalize_github_url(cnr_id)
            if normalized:
                return normalized
            
            # cnr_id 是简短名称，尝试在 plugin_info 中查找匹配
            # 例如 "comfyui-custom-scripts" -> "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"
            cnr_id_lower = cnr_id.lower().replace('-', '').replace('_', '')
            for github_url, info in node_mapper._plugin_info.items():
                # 检查 GitHub URL 是否包含 cnr_id（忽略大小写和分隔符）
                url_normalized = github_url.lower().replace('-', '').replace('_', '')
                if cnr_id_lower in url_normalized:
                    return github_url
                # 检查插件名是否匹配
                if info.name:
                    name_normalized = info.name.lower().replace('-', '').replace('_', '')
                    if cnr_id_lower in name_normalized:
                        return github_url
            
            # 尝试在本地插件列表中查找
            if node_mapper._local_plugins:
                for local_url, local_info in node_mapper._local_plugins.items():
                    if local_url.startswith('local://'):
                        continue
                    url_normalized = local_url.lower().replace('-', '').replace('_', '')
                    if cnr_id_lower in url_normalized:
                        return local_url
                    if local_info.get('name'):
                        name_normalized = local_info['name'].lower().replace('-', '').replace('_', '')
                        if cnr_id_lower in name_normalized:
                            return local_url
        
        # 通过节点类型查找
        result = node_mapper.resolve_node(node_type)
        
        if result.github_url:
            return result.github_url
        
        return ""

    @staticmethod
    def _get_plugin_name(github_url: str, node_type: str) -> str:
        """
        获取插件名称
        
        Args:
            github_url: GitHub URL
            node_type: 节点类型
            
        Returns:
            插件名称
        """
        if github_url:
            from backend.src.utils.node_mapper import node_mapper
            info = node_mapper.get_plugin_info(github_url)
            if info and info.name:
                return info.name
            
            parts = github_url.rstrip("/").split("/")
            if len(parts) >= 1:
                return parts[-1]
        
        return "Unknown"

    @staticmethod
    def _parse_link(link_data: List) -> Optional[ParsedLink]:
        """
        解析单个连接
        
        连接格式: [link_id, source_node_id, source_slot, target_node_id, target_slot, data_type]
        
        Args:
            link_data: 连接数据列表
            
        Returns:
            ParsedLink 对象，解析失败返回 None
        """
        if not isinstance(link_data, list) or len(link_data) < 5:
            return None
        
        try:
            return ParsedLink(
                id=link_data[0],
                source_node_id=link_data[1],
                source_slot=link_data[2],
                target_node_id=link_data[3],
                target_slot=link_data[4],
                data_type=link_data[5] if len(link_data) > 5 else "",
            )
        except (IndexError, TypeError) as e:
            logger.warning(f"连接解析失败: {link_data}, 错误: {e}")
            return None

    @staticmethod
    def extract_node_count(data: Any) -> int:
        """
        提取节点数量

        兼容多种顶层结构，避免单个异常文件导致整条加载链路报错：
        - UI 格式：{"nodes": [...], "links": [...], ...}
        - API 格式：{"1": {"class_type": "...", "inputs": {...}}, ...}
        - 其他（如预设列表、非工作流 JSON）：返回 0
        """
        if isinstance(data, dict):
            nodes = data.get("nodes")
            if isinstance(nodes, list):
                return len(nodes)
            # API 格式没有 nodes 字段，按 class_type 条目计数
            return sum(
                1 for value in data.values()
                if isinstance(value, dict) and "class_type" in value
            )
        return 0

    @staticmethod
    def extract_plugins(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        提取插件依赖列表
        
        Args:
            data: 工作流数据字典
            
        Returns:
            插件依赖字典列表
        """
        plugins: Dict[str, Dict[str, Any]] = {}
        
        for node in data.get("nodes", []):
            node_type = node.get("type", "Unknown")
            
            if is_virtual_node(node_type):
                continue
            
            properties = node.get("properties", {})
            github_url = WorkflowParser._resolve_github_url(node_type, properties)
            
            if github_url not in plugins:
                plugins[github_url] = {
                    "githubUrl": github_url,
                    "name": WorkflowParser._get_plugin_name(github_url, node_type),
                    "color": get_plugin_color(github_url),
                    "node_types": [],
                }
            if node_type not in plugins[github_url]["node_types"]:
                plugins[github_url]["node_types"].append(node_type)
        
        if 'extra' in data and 'groupNodes' in data['extra']:
            for group_name, group_data in data['extra']['groupNodes'].items():
                group_nodes = group_data.get('nodes', [])
                for node in group_nodes:
                    node_type = node.get("type", "Unknown")
                    
                    if is_virtual_node(node_type):
                        continue
                    
                    properties = node.get("properties", {})
                    github_url = WorkflowParser._resolve_github_url(node_type, properties)
                    
                    if github_url not in plugins:
                        plugins[github_url] = {
                            "githubUrl": github_url,
                            "name": WorkflowParser._get_plugin_name(github_url, node_type),
                            "color": get_plugin_color(github_url),
                            "node_types": [],
                        }
                    if node_type not in plugins[github_url]["node_types"]:
                        plugins[github_url]["node_types"].append(node_type)
        
        return list(plugins.values())

    @staticmethod
    def get_workflow_name(data: Dict[str, Any], filename: str) -> str:
        """
        获取工作流名称
        
        优先级：
        1. JSON 中的 name 字段
        2. 文件名（不含扩展名）
        
        Args:
            data: 工作流数据字典
            filename: 文件名
            
        Returns:
            工作流名称
        """
        if data.get("name"):
            return data["name"]
        
        return Path(filename).stem

    @staticmethod
    def validate_workflow_json(content: str) -> Tuple[bool, Optional[str]]:
        """
        验证工作流 JSON 是否有效
        
        Args:
            content: JSON 字符串内容
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            data = json.loads(content)
            
            if not isinstance(data, dict):
                return False, "工作流必须是 JSON 对象"
            
            if "nodes" not in data:
                return False, "工作流缺少 nodes 字段"
            
            if not isinstance(data["nodes"], list):
                return False, "nodes 字段必须是数组"
            
            return True, None
            
        except json.JSONDecodeError as e:
            return False, f"JSON 格式错误: {e}"
