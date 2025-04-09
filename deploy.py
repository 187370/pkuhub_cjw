# deploy.py
# 用于在生产环境中启动 PKU Hub 应用
# 仅仅在linux环境下运行
# 该脚本使用 Gunicorn 作为 WSGI HTTP 服务器，提供比 Flask 开发服务器更好的性能和稳定性

import subprocess  # 导入子进程模块，用于执行系统命令


def run_gunicorn():
    """
    启动 Gunicorn WSGI 服务器来运行 Flask 应用

    参数说明:
    -w 4: 使用4个工作进程(workers)处理请求，提高并发能力
    -b 0.0.0.0:5000: 绑定到所有网络接口的5000端口
    --access-logfile -: 将访问日志输出到标准输出(控制台)
    main:app: 指定 Flask 应用实例，格式为 "模块名:应用实例变量名"
    """
    subprocess.run(
        [
            "gunicorn",  # 使用 gunicorn 命令
            "-w",
            "12",  # 设置12个工作进程，根据CPU核心数可调整
            "-b",
            "0.0.0.0:5000",  # 监听所有网络接口的5000端口
            "--access-logfile",
            "-",  # 访问日志输出到标准输出
            "main:app",  # 指定 Flask 应用实例，从 main.py 中导入 app 变量
        ]
    )


if __name__ == "__main__":
    # 当脚本直接运行时(而不是被导入)，启动 Gunicorn 服务器
    run_gunicorn()
