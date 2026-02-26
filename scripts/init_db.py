"""
初始化数据库 - 创建所有表
"""
import sys
sys.path.insert(0, './backend')

from app.core.database import init_db

if __name__ == "__main__":
    print("正在初始化数据库...")
    init_db()
    print("数据库初始化完成")
