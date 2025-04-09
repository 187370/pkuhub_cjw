# 主程序入口
# 原有导入
from __init__ import create_app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
