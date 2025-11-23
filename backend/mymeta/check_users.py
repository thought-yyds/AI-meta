#!/usr/bin/env python3
"""
诊断脚本：检查数据库中的用户
用于调试注册和登录问题
"""

import sys
from app.core.database import SessionLocal
from app.models.models import User
from app.core.auth import verify_password

def check_users():
    """检查数据库中的所有用户"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"\n数据库中共有 {len(users)} 个用户：\n")
        
        if not users:
            print("❌ 数据库中没有用户！")
            print("\n建议：")
            print("1. 通过前端注册一个新用户")
            print("2. 或使用以下命令创建测试用户：")
            print("   python create_test_user.py")
            return
        
        for user in users:
            print(f"用户 ID: {user.id}")
            print(f"  用户名: {user.username}")
            print(f"  邮箱: {user.email}")
            print(f"  是否激活: {user.is_active}")
            print(f"  创建时间: {user.created_at}")
            print(f"  密码哈希: {user.hashed_password[:20]}...")
            print()
        
        # 测试密码验证
        if users:
            test_user = users[0]
            print(f"\n测试用户 '{test_user.username}' 的密码验证：")
            print("（这只是一个示例，不会显示实际密码）")
            print("要测试登录，请使用前端界面或 API")
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("用户数据库诊断工具")
    print("=" * 50)
    check_users()
    print("\n✅ 检查完成")

