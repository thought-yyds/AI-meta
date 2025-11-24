"""调试脚本：详细检查 launch_app 和 switch_app 的行为。"""

import json
import subprocess
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from tools.windows_mcp import WindowsMCPClient, WindowsMCPError
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def check_processes(process_names):
    """检查进程是否在运行。"""
    found = []
    for proc_name in process_names:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/FO", "CSV"],
                capture_output=True,
                text=True,
                check=False,
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1 and proc_name.lower() in lines[-1].lower():
                found.append(proc_name)
        except Exception:
            pass
    return found


def main():
    print("=" * 80)
    print("详细调试：launch_app 和 switch_app")
    print("=" * 80)
    
    client = WindowsMCPClient()
    
    # 1. 检查启动前的状态
    print("\n1. 启动前的状态检查...")
    process_names = ["VooVMeeting.exe", "TencentMeeting.exe", "wemeetapp.exe"]
    before_processes = check_processes(process_names)
    print(f"   启动前运行的进程: {before_processes if before_processes else '无'}")
    
    # 2. 调用 launch_app
    print("\n2. 调用 launch_app('腾讯会议')...")
    try:
        launch_result = client.call_tool_json("launch_app", {"name": "腾讯会议"})
        print(f"   原始返回: {launch_result}")
        result = json.loads(launch_result)
        print(f"   解析后: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print(f"   is_error: {result.get('is_error')}")
        print(f"   text: {result.get('text', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 等待并检查进程
    print("\n3. 等待 2 秒后检查进程...")
    time.sleep(2)
    after_processes = check_processes(process_names)
    print(f"   启动后运行的进程: {after_processes if after_processes else '无'}")
    new_processes = [p for p in after_processes if p not in before_processes]
    if new_processes:
        print(f"   ✅ 新启动的进程: {new_processes}")
    else:
        print(f"   ⚠️  没有新进程启动")
    
    # 4. 检查窗口状态
    print("\n4. 获取桌面状态...")
    try:
        desktop_state = client.call_tool_json("get_desktop_state", {"useVision": False})
        state = json.loads(desktop_state)
        print(f"   桌面状态: {json.dumps(state, indent=2, ensure_ascii=False)}")
        active_window = state.get("activeWindow") or state.get("active_window")
        if active_window:
            print(f"   当前活动窗口: {active_window}")
    except Exception as e:
        print(f"   ❌ 获取桌面状态失败: {e}")
    
    # 5. 尝试 switch_app
    print("\n5. 调用 switch_app('腾讯会议')...")
    try:
        switch_result = client.call_tool_json("switch_app", {"name": "腾讯会议"})
        result = json.loads(switch_result)
        print(f"   解析后: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print(f"   is_error: {result.get('is_error')}")
        print(f"   text: {result.get('text', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. 再次检查窗口状态
    print("\n6. switch_app 后再次获取桌面状态...")
    time.sleep(1)
    try:
        desktop_state = client.call_tool_json("get_desktop_state", {"useVision": False})
        state = json.loads(desktop_state)
        active_window = state.get("activeWindow") or state.get("active_window")
        if active_window:
            print(f"   当前活动窗口: {active_window}")
            if "腾讯会议" in str(active_window) or "VooV" in str(active_window) or "Tencent" in str(active_window):
                print("   ✅ 确认腾讯会议窗口在前台")
            else:
                print("   ⚠️  当前活动窗口不是腾讯会议")
    except Exception as e:
        print(f"   ❌ 获取桌面状态失败: {e}")
    
    # 7. 尝试提取屏幕文本
    print("\n7. 提取屏幕文本...")
    try:
        screen_text = client.call_tool_json("extract_text_from_screen", {})
        result = json.loads(screen_text)
        if result and not result.get("is_error"):
            text = result.get("text", "")
            if text:
                print(f"   屏幕文本（前500字符）: {text[:500]}...")
                keywords = ["腾讯会议", "VooV", "Tencent", "会议", "Meeting"]
                found = [kw for kw in keywords if kw in text]
                if found:
                    print(f"   ✅ 找到关键词: {found}")
                else:
                    print("   ⚠️  未找到相关关键词")
            else:
                print("   ⚠️  屏幕文本为空")
        else:
            print(f"   ⚠️  提取失败: {result.get('text', 'N/A') if result else '无响应'}")
    except Exception as e:
        print(f"   ❌ 提取屏幕文本失败: {e}")
    
    # 8. 尝试查找腾讯会议的可执行文件路径
    print("\n8. 尝试查找腾讯会议可执行文件...")
    common_paths = [
        Path("C:/Program Files (x86)/Tencent/VooVMeeting/VooVMeeting.exe"),
        Path("C:/Program Files/Tencent/VooVMeeting/VooVMeeting.exe"),
        Path.home() / "AppData/Local/Tencent/VooVMeeting/VooVMeeting.exe",
        Path("C:/Users/Public/Desktop/VooVMeeting.lnk"),
    ]
    found_exe = None
    for path in common_paths:
        if path.exists():
            found_exe = path
            print(f"   ✅ 找到可执行文件: {found_exe}")
            break
    
    if not found_exe:
        print("   ⚠️  未找到可执行文件，尝试在注册表中查找...")
        try:
            # 尝试从注册表查找
            import winreg
            key_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\VooVMeeting.exe"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\VooVMeeting.exe"),
            ]
            for hkey, path in key_paths:
                try:
                    with winreg.OpenKey(hkey, path) as key:
                        exe_path = winreg.QueryValue(key, None)
                        if Path(exe_path).exists():
                            found_exe = Path(exe_path)
                            print(f"   ✅ 从注册表找到: {found_exe}")
                            break
                except Exception:
                    pass
        except Exception as e:
            print(f"   ⚠️  注册表查找失败: {e}")
    
    if found_exe:
        print(f"\n9. 尝试直接启动可执行文件: {found_exe}")
        try:
            subprocess.Popen([str(found_exe)], shell=False)
            print("   ✅ 已启动，等待 3 秒...")
            time.sleep(3)
            after_direct = check_processes(process_names)
            print(f"   直接启动后的进程: {after_direct if after_direct else '无'}")
        except Exception as e:
            print(f"   ❌ 直接启动失败: {e}")
    
    print("\n" + "=" * 80)
    print("调试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()

