import json
import os
from datetime import datetime


def create_welcome_notification():
    notification_file = "notifications.json"
    if not os.path.exists(notification_file):
        welcome_notification = {
            "id": str(datetime.now().timestamp()),
            "title": "欢迎使用PKUHUB",
            "content": "欢迎使用PKUHUB！\n\n这是一个由北大学生自主开发的学习资源共享网站，旨在促进校内知识流通，提高学习效率。\n\n如有任何问题或建议，请联系管理员。",
            "target_role": "all",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": 1,  # 假设ID为1的是管理员
            "read_by": [],
        }

        with open(notification_file, "w", encoding="utf-8") as f:
            json.dump([welcome_notification], f, ensure_ascii=False, indent=2)

        print("已创建欢迎通知")
    else:
        print("通知文件已存在，跳过创建")


if __name__ == "__main__":
    create_welcome_notification()
