"""诊断脚本：检查腾讯会议是否在运行，并提供调试信息。"""

import json
import subprocess
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from tools.windows_mcp import WindowsMCPClient, WindowsMCPError
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保已安装依赖: pip install mcp")
    sys.exit(1)


def check_process_running(process_name: str) -> bool:
    """检查进程是否在运行。"""
    try:
        # 使用 tasklist 命令检查进程
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV"],
            capture_output=True,
            text=True,
            check=False,
        )
        # 如果输出包含进程名（除了标题行），说明进程在运行
        lines = result.stdout.strip().split("\n")
        return len(lines) > 1 and process_name.lower() in lines[-1].lower()
    except Exception:
        return False


def main():
    print("=" * 80)
    print("腾讯会议状态诊断工具")
    print("=" * 80)
    
    # 1. 检查进程
    print("\n1. 检查腾讯会议进程...")
    process_names = ["VooVMeeting.exe", "TencentMeeting.exe", "wemeetapp.exe"]
    found_processes = []
    for proc_name in process_names:
        if check_process_running(proc_name):
            found_processes.append(proc_name)
            print(f"   ✅ 找到进程: {proc_name}")
        else:
            print(f"   ❌ 未找到进程: {proc_name}")
    
    if not found_processes:
        print("\n   ⚠️  未检测到腾讯会议进程在运行")
        print("   可能的原因：")
        print("   - 应用未启动")
        print("   - 应用已退出")
        print("   - 进程名称不同（请手动检查任务管理器）")
    else:
        print(f"\n   ✅ 检测到 {len(found_processes)} 个相关进程在运行")
    
    # 2. 检查 WindowsMCP 连接
    print("\n2. 检查 WindowsMCP 连接...")
    try:
        client = WindowsMCPClient()
        print("   ✅ WindowsMCP 客户端创建成功")
    except WindowsMCPError as e:
        print(f"   ❌ WindowsMCP 客户端创建失败: {e}")
        return
    
    # 3. 检查应用窗口状态
    print("\n3. 检查应用窗口状态...")
    try:
        # 尝试切换到腾讯会议窗口
        switch_result = json.loads(client.call_tool_json("switch_app", {"name": "腾讯会议"}))
        if switch_result.get("is_error"):
            print(f"   ⚠️  无法切换到腾讯会议窗口: {switch_result.get('text', '未知错误')}")
        else:
            print("   ✅ 成功切换到腾讯会议窗口")
        
        # 获取桌面状态
        print("\n4. 获取当前桌面状态...")
        desktop_state = json.loads(client.call_tool_json("get_desktop_state", {"useVision": False}))
        if isinstance(desktop_state, dict):
            active_window = desktop_state.get("activeWindow") or desktop_state.get("active_window")
            if active_window:
                print(f"   当前活动窗口: {active_window}")
                if "腾讯会议" in str(active_window) or "VooV" in str(active_window) or "Tencent" in str(active_window):
                    print("   ✅ 确认腾讯会议窗口在前台")
                else:
                    print("   ⚠️  当前活动窗口不是腾讯会议")
            else:
                print("   ⚠️  无法获取活动窗口信息")
        else:
            print("   ⚠️  桌面状态格式异常")
    except Exception as e:
        print(f"   ❌ 检查窗口状态时出错: {e}")
    
    # 4. 尝试提取屏幕文本
    print("\n5. 尝试提取屏幕文本（检查应用是否可见）...")
    try:
        screen_text = json.loads(client.call_tool_json("extract_text_from_screen", {}))
        if screen_text and not screen_text.get("is_error"):
            text_content = screen_text.get("text", "")
            if text_content:
                # 查找腾讯会议相关的关键词
                keywords = ["腾讯会议", "VooV", "Tencent", "会议", "Meeting", "创建", "加入"]
                found_keywords = [kw for kw in keywords if kw in text_content]
                if found_keywords:
                    print(f"   ✅ 在屏幕上找到相关关键词: {', '.join(found_keywords)}")
                    print(f"   屏幕文本预览（前200字符）: {text_content[:200]}...")
                else:
                    print("   ⚠️  未在屏幕上找到腾讯会议相关文本")
                    print(f"   屏幕文本预览（前200字符）: {text_content[:200]}...")
            else:
                print("   ⚠️  屏幕文本为空")
        else:
            print(f"   ⚠️  提取屏幕文本失败: {screen_text.get('text', '未知错误') if screen_text else '无响应'}")
    except Exception as e:
        print(f"   ❌ 提取屏幕文本时出错: {e}")
    
    print("\n" + "=" * 80)
    print("诊断完成")
    print("=" * 80)
    print("\n建议：")
    if not found_processes:
        print("1. 如果应用未运行，请手动启动腾讯会议")
    else:
        print("1. 进程在运行，但窗口可能被最小化或遮挡")
        print("2. 尝试按 Alt+Tab 切换到腾讯会议窗口")
        print("3. 检查任务栏是否有腾讯会议图标，点击它来显示窗口")
    print("4. 如果看到权限提示，请点击'允许'或'是'")


if __name__ == "__main__":
    main()

