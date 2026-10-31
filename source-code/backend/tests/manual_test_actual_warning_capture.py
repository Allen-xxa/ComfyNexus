"""
测试实际环境中的警告信息捕获

使用 ComfyUI 环境的 Python 来测试
"""

import os
import subprocess
import sys

# ComfyUI 环境的 Python 路径，通过环境变量 COMFYUI_PYTHON 指定
COMFYUI_PYTHON = os.environ.get("COMFYUI_PYTHON", "")


def test_warning_capture():
    print("=" * 80)
    print("测试警告信息捕获")
    print("=" * 80)
    
    print(f"\nPython 路径: {COMFYUI_PYTHON}")
    
    # 测试 1: pipdeptree --json-tree
    print("\n1. 测试 pipdeptree --json-tree")
    print("-" * 80)
    
    result1 = subprocess.run(
        [COMFYUI_PYTHON, '-m', 'pipdeptree', '--json-tree'],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    print(f"返回码: {result1.returncode}")
    print(f"stdout 长度: {len(result1.stdout)} 字符")
    print(f"stderr 长度: {len(result1.stderr)} 字符")
    print(f"stdout 包含 'Warning': {'Warning' in result1.stdout}")
    print(f"stderr 包含 'Warning': {'Warning' in result1.stderr}")
    
    if 'Warning' in result1.stdout:
        print("\n⚠️ 警告信息在 stdout 中！")
        print(result1.stdout[:500])
    
    if 'Warning' in result1.stderr:
        print("\n⚠️ 警告信息在 stderr 中！")
        print(result1.stderr[:500])
    
    # 测试 2: pipdeptree (不带参数)
    print("\n2. 测试 pipdeptree (不带参数)")
    print("-" * 80)
    
    result2 = subprocess.run(
        [COMFYUI_PYTHON, '-m', 'pipdeptree'],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    print(f"返回码: {result2.returncode}")
    print(f"stdout 长度: {len(result2.stdout)} 字符")
    print(f"stderr 长度: {len(result2.stderr)} 字符")
    print(f"stdout 包含 'Warning': {'Warning' in result2.stdout}")
    print(f"stderr 包含 'Warning': {'Warning' in result2.stderr}")
    
    if 'Warning' in result2.stdout:
        print("\n✓ 警告信息在 stdout 中！")
        # 提取警告部分
        lines = result2.stdout.split('\n')
        warning_start = -1
        for i, line in enumerate(lines):
            if 'Warning!!!' in line:
                warning_start = i
                break
        
        if warning_start >= 0:
            # 找到分隔线
            warning_end = warning_start + 1
            for i in range(warning_start + 1, len(lines)):
                if '---' in lines[i]:
                    warning_end = i
                    break
            
            warning_text = '\n'.join(lines[warning_start:warning_end])
            print(f"\n警告文本长度: {len(warning_text)} 字符")
            print(f"警告文本:\n{warning_text}")
            
            # 统计冲突数量
            conflict_count = warning_text.count('* ')
            print(f"\n冲突包数量: {conflict_count}")
    
    if 'Warning' in result2.stderr:
        print("\n⚠️ 警告信息在 stderr 中！")
        print(result2.stderr[:500])
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    test_warning_capture()
