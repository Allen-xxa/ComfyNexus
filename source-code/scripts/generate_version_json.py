"""
本地测试脚本：生成 version.json
从 GitHub API 获取最新 Release 信息
"""

import json
import requests
import os
import sys
from pathlib import Path

REPO_OWNER = "qiqStrong"
REPO_NAME = "ComfyNexus"

def get_proxy_from_settings():
    """从项目设置中读取代理配置"""
    try:
        project_root = Path(__file__).parent.parent
        settings_file = project_root / "data" / "settings.json"
        
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            
            proxy = settings.get("proxy", {})
            if proxy.get("enabled"):
                host = proxy.get("host", "").strip()
                port = proxy.get("port", "").strip()
                if host and port:
                    proxy_url = f"http://{host}:{port}"
                    return {"http": proxy_url, "https": proxy_url}
    except Exception as e:
        print(f"读取设置失败: {e}")
    
    return None

def get_proxy_from_env():
    """从环境变量获取代理设置"""
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    
    if https_proxy:
        return {"http": https_proxy, "https": https_proxy}
    if http_proxy:
        return {"http": http_proxy, "https": http_proxy}
    return None

def get_proxy():
    """获取代理配置（优先从设置读取）"""
    proxy = get_proxy_from_settings()
    if proxy:
        return proxy
    return get_proxy_from_env()

def generate_version_json():
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    
    print(f"正在获取 {REPO_OWNER}/{REPO_NAME} 的最新 Release 信息...")
    
    proxies = get_proxy()
    if proxies:
        print(f"使用代理: {proxies.get('https')}")
    else:
        print("未使用代理")
    
    try:
        response = requests.get(
            api_url, 
            timeout=15, 
            params={"per_page": 1},
            proxies=proxies
        )
        response.raise_for_status()
        
        releases = response.json()
        if not releases:
            print("未找到任何 Release")
            return
        
        release = releases[0]
        
        release_tag = release.get("tag_name", "")
        release_body = release.get("body", "")
        published_at = release.get("published_at", "")
        
        download_url = ""
        file_size = 0
        file_hash = ""
        
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.endswith("-win64.zip"):
                download_url = asset.get("browser_download_url", "")
                file_size = asset.get("size", 0)
                digest = asset.get("digest", "")
                if digest and digest.startswith("sha256:"):
                    file_hash = digest[7:]
                break
        
        version_info = {
            "version": release_tag,
            "published_at": published_at,
            "download_url": download_url,
            "file_size": file_size,
            "file_hash": file_hash,
            "release_notes": release_body
        }
        
        project_root = Path(__file__).parent.parent
        output_path = project_root / "version.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)
        
        print(f"\n已生成 {output_path}")
        print(f"版本: {release_tag}")
        print(f"发布时间: {published_at}")
        if download_url:
            print(f"下载链接: {download_url}")
            print(f"文件大小: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
            if file_hash:
                print(f"SHA256: {file_hash[:16]}...")
        else:
            print("警告: 未找到 -win64.zip 资源文件")
        
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        print("\n提示: 如果网络无法访问 GitHub，请尝试:")
        print("  1. 在设置中启用代理")
        print("  2. 或设置环境变量: set HTTPS_PROXY=http://127.0.0.1:端口")
    except Exception as e:
        print(f"生成失败: {e}")

if __name__ == "__main__":
    generate_version_json()
