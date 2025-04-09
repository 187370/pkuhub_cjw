# 导入必要的标准库
import os
import smtplib
from email.message import EmailMessage
from typing import Union, List, Dict, Callable, Any
from dataclasses import dataclass
import logging
import threading
import queue
import time
from dotenv import load_dotenv
import sys


# 自定义异常 --------------------------------------------------
class NotificationError(Exception):
    """通知系统基异常 - 所有通知相关异常的基类"""


class AuthenticationError(NotificationError):
    """认证失败异常 - 当SMTP身份验证失败时抛出"""


class DeliveryError(NotificationError):
    """邮件投递失败异常 - 当邮件无法发送到目标收件人时抛出"""


class ConfigurationError(NotificationError):
    """配置错误异常 - 当环境变量配置缺失或不正确时抛出"""


# 配置层 ------------------------------------------------------
@dataclass
class EmailAccount:
    """
    邮箱账户实体 - 存储单个邮箱账户的配置信息
    使用dataclass简化类定义,自动生成初始化方法和其他魔术方法
    """

    address: str  # 邮箱地址
    password: str  # 邮箱密码
    priority: int = 1  # 优先级,数字越小优先级越高,默认为1
    daily_limit: int = 50  # 每日发送限制,防止触发服务商限制


class MailPoolConfig:
    """邮箱池配置中心 - 负责加载和管理SMTP服务器配置及多个邮箱账户"""

    def __init__(self):
        """初始化方法,加载环境变量和邮箱账户列表"""
        # 获取当前模块文件的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 向上一级找到项目根目录
        project_root = os.path.abspath(os.path.join(current_dir, ".."))

        # 检查项目根目录下是否存在.env文件
        env_file = os.path.join(project_root, ".env")
        if not os.path.exists(env_file):
            # 如果项目根目录没有，检查当前模块目录
            env_file = os.path.join(current_dir, ".env")
            if not os.path.exists(env_file):
                # 如果模块目录也没有，检查当前工作目录
                env_file = ".env"
                if not os.path.exists(env_file):
                    # 如果当前工作目录也没有，创建示例文件
                    self._create_example_env(project_root)
                    print(
                        f"⚠️ 未找到环境变量配置文件。已创建示例配置文件 {os.path.join(current_dir, '.env.example')}，"
                        f"请根据示例配置后重命名为 .env"
                    )
                    # 可能需要抛出异常或提前退出，因为没有配置文件

        # 无论在哪里找到.env文件,都加载它
        load_dotenv(dotenv_path=env_file)

        # 检查SMTP配置是否存在
        self.smtp_host = os.getenv("SMTP_HOST")
        if not self.smtp_host:
            raise ConfigurationError("缺少SMTP_HOST环境变量配置，请检查.env文件")

        self.smtp_port = self._get_port()
        self.accounts = self._load_accounts()  # 加载所有配置的邮箱账户

        # 如果没有找到任何可用账户，记录错误
        if not self.accounts:
            raise ConfigurationError(
                "未找到任何邮箱账户配置，请在.env文件中添加至少一个EMAIL_USER_1和EMAIL_PWD_1"
            )

    def _get_port(self) -> int:
        """获取SMTP端口号，确保是有效的整数"""
        try:
            return int(os.getenv("SMTP_PORT", 465))
        except ValueError:
            raise ConfigurationError("SMTP_PORT必须是一个有效的整数")

    def _create_example_env(self, project_root):
        """
        创建示例.env文件，为用户提供配置模板

        参数:
            project_root: 项目根目录路径，用于确定示例文件的存放位置
        """
        example_content = """# SMTP服务器配置
    SMTP_HOST=smtp.example.com
    SMTP_PORT=465
    
    # 第一个邮箱账户（必须）
    EMAIL_USER_1=your_email@example.com
    EMAIL_PWD_1=your_password_or_app_password
    EMAIL_PRIORITY_1=1
    
    # 第二个邮箱账户（可选）
    # EMAIL_USER_2=backup_email@example.com
    # EMAIL_PWD_2=backup_password
    # EMAIL_PRIORITY_2=2
    
    # 常见SMTP服务器配置：
    # QQ邮箱: SMTP_HOST=smtp.qq.com, SMTP_PORT=465
    # Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=465
    # 163邮箱: SMTP_HOST=smtp.163.com, SMTP_PORT=465
    # Outlook: SMTP_HOST=smtp.office365.com, SMTP_PORT=587
    """
        # 创建示例配置文件到项目根目录
        example_file_path = os.path.join(project_root, ".env.example")
        with open(example_file_path, "w", encoding="utf-8") as f:
            f.write(example_content)

    def _load_accounts(self) -> List[EmailAccount]:
        """
        从环境变量加载多账户
        返回:按优先级排序的EmailAccount对象列表
        """
        accounts = []
        idx = 1
        # 持续尝试读取EMAIL_USER_1, EMAIL_USER_2...直到找不到为止
        while True:
            user_key = f"EMAIL_USER_{idx}"
            if not (user := os.getenv(user_key)):
                break  # 如果没有找到用户名,退出循环

            pwd_key = f"EMAIL_PWD_{idx}"
            pwd = os.getenv(pwd_key)
            if not pwd:
                logging.warning(
                    f"找到用户名 {user} 但缺少密码，请检查 {pwd_key} 环境变量"
                )
                idx += 1
                continue

            priority_key = f"EMAIL_PRIORITY_{idx}"
            try:
                priority = int(os.getenv(priority_key, 1))
            except ValueError:
                logging.warning(f"{priority_key} 应该是整数，使用默认值 1")
                priority = 1

            accounts.append(EmailAccount(address=user, password=pwd, priority=priority))
            logging.info(f"已加载邮箱账户: {user} (优先级: {priority})")
            idx += 1  # 递增索引以读取下一个账户

        # 返回按优先级排序的账户列表
        return sorted(accounts, key=lambda x: x.priority)


# 连接层 ------------------------------------------------------
class ConnectionPool:
    """
    轻量级连接池 - 管理和复用SMTP连接,避免频繁创建和关闭连接
    """

    def __init__(self):
        """初始化连接池和使用计数器"""
        self._pool = {}  # 存储 {account.address: SMTP_SSL实例} 的字典
        self._usage_counter = {}  # 每个账户的使用计数,用于实现发送限制
        self._lock = threading.RLock()  # 添加锁以保护连接池的线程安全

    def _create_connection(self, config: MailPoolConfig) -> smtplib.SMTP_SSL:
        """
        创建新的SMTP连接
        参数:config - 包含SMTP服务器配置的对象
        返回:已配置的SMTP_SSL连接实例
        """
        try:
            logging.info(f"尝试连接到SMTP服务器: {config.smtp_host}:{config.smtp_port}")
            return smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port
            )  # 创建SSL安全连接
        except Exception as e:
            logging.error(f"连接SMTP服务器失败: {e}")
            raise

    def get_connection(
        self, account: EmailAccount, config: MailPoolConfig
    ) -> smtplib.SMTP_SSL:
        """
        获取指定账户的可用连接,如果不存在则创建新连接
        参数:
            account - 要使用的邮箱账户
            config - SMTP服务器配置
        返回:
            可用的SMTP连接
        抛出:
            DeliveryError - 当账户达到每日发送限制时
        """
        with self._lock:
            # 如果该账户没有活跃连接,创建新连接
            if account.address not in self._pool:
                self._pool[account.address] = self._create_connection(config)
                self._usage_counter[account.address] = 0

            # 检查连接是否仍然有效
            try:
                # 尝试执行一个简单的SMTP命令来验证连接状态
                self._pool[account.address].noop()
            except Exception as e:
                logging.info(
                    f"检测到无效连接 ({account.address}): {str(e)}，正在重新创建..."
                )
                try:
                    # 尝试关闭旧连接
                    try:
                        self._pool[account.address].quit()
                    except:
                        pass
                    # 创建新连接
                    self._pool[account.address] = self._create_connection(config)
                except Exception as conn_error:
                    logging.error(f"重新创建连接失败: {str(conn_error)}")
                    raise DeliveryError(f"无法创建SMTP连接: {str(conn_error)}")

            # 检查账户是否达到发送限制
            if self._usage_counter[account.address] >= account.daily_limit:
                raise DeliveryError(f"Account {account.address} reached daily limit")

            # 返回该账户的活跃连接
            return self._pool[account.address]

    def increment_usage(self, account: EmailAccount):
        """
        增加账户的使用计数,在每次成功发送邮件后调用
        参数:account - 要增加使用计数的账户
        """
        with self._lock:
            self._usage_counter[account.address] = (
                self._usage_counter.get(account.address, 0) + 1
            )

    def close_all(self):
        """
        关闭所有连接,在程序结束时调用以释放资源
        忽略关闭过程中可能出现的异常
        """
        with self._lock:
            for address, conn in self._pool.items():
                try:
                    logging.info(f"正在关闭与 {address} 的连接")
                    conn.quit()  # 尝试正常关闭连接
                except:
                    pass  # 忽略关闭过程中的异常
            self._pool.clear()  # 清空连接池


# 任务队列层 --------------------------------------------------
class MailQueue:
    """
    邮件任务队列 - 管理邮件发送任务并使用工作线程处理
    """

    def __init__(self, worker_count=3, queue_size=100):
        """
        初始化邮件队列和工作线程

        参数:
            worker_count: 工作线程数量
            queue_size: 队列最大容量
        """
        self._queue = queue.Queue(maxsize=queue_size)
        self._workers = []
        self._running = False
        self._worker_count = worker_count
        self._lock = threading.RLock()

    def start(self):
        """启动工作线程"""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._workers = []

            # 创建并启动工作线程
            for i in range(self._worker_count):
                worker = threading.Thread(
                    target=self._worker_loop, name=f"MailWorker-{i}", daemon=True
                )
                worker.start()
                self._workers.append(worker)

            logging.info(f"邮件队列已启动，使用 {self._worker_count} 个工作线程")

    def stop(self):
        """停止所有工作线程"""
        with self._lock:
            if not self._running:
                return

            self._running = False

            # 为每个工作线程添加停止信号
            for _ in self._workers:
                self._queue.put(None)

            # 等待所有工作线程完成
            for worker in self._workers:
                if worker.is_alive():
                    worker.join(timeout=2.0)

            self._workers = []
            logging.info("邮件队列已停止")

    def put(self, task):
        """
        将任务添加到队列

        参数:
            task: 包含任务信息的字典
        """
        if not self._running:
            self.start()

        self._queue.put(task)

    def _worker_loop(self):
        """工作线程的主循环"""
        while self._running:
            try:
                # 从队列获取任务
                task = self._queue.get(block=True, timeout=1.0)

                # 检查是否是停止信号
                if task is None:
                    self._queue.task_done()
                    break

                try:
                    # 执行任务
                    self._execute_task(task)
                except Exception as e:
                    logging.error(f"处理邮件任务时出错: {str(e)}", exc_info=True)
                finally:
                    self._queue.task_done()

            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logging.error(f"邮件工作线程出现错误: {str(e)}", exc_info=True)
                # 短暂暂停以避免CPU占用过高
                time.sleep(0.1)

    def _execute_task(self, task):
        """
        执行邮件发送任务

        参数:
            task: 包含任务信息的字典
        """
        # 解包任务信息
        notifier = task["notifier"]
        to = task["to"]
        subject = task["subject"]
        content = task["content"]
        content_type = task["content_type"]
        callback = task.get("callback")

        # 执行发送
        result = notifier._send_sync(to, subject, content, content_type)

        # 如果提供了回调函数，调用它
        if callback:
            try:
                callback(result)
            except Exception as e:
                logging.error(f"执行回调函数时出错: {str(e)}", exc_info=True)


# 业务逻辑层 --------------------------------------------------
class MailNotifier:
    """
    邮件通知器主类 - 提供发送邮件通知的API和业务逻辑
    单例模式实现，确保所有实例共享相同的连接池和配置
    """

    _instance = None
    _config = None
    _pool = None
    _logger = None
    _initialized = False
    _mail_queue = None

    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(MailNotifier, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化通知器,加载配置和创建连接池"""
        # 避免重复初始化
        if MailNotifier._initialized:
            return

        try:
            # 初始化日志系统
            MailNotifier._logger = self._init_logger()
            self.logger.info("正在初始化邮件通知系统...", extra={"account": "system"})

            # 创建配置和连接池
            MailNotifier._config = MailPoolConfig()
            self.logger.info(
                f"成功加载配置: SMTP服务器 {self.config.smtp_host}:{self.config.smtp_port}",
                extra={"account": "system"},
            )
            self.logger.info(
                f"已加载 {len(self.config.accounts)} 个邮箱账户",
                extra={"account": "system"},
            )

            MailNotifier._pool = ConnectionPool()

            # 初始化邮件队列
            MailNotifier._mail_queue = MailQueue(worker_count=3)
            MailNotifier._mail_queue.start()

            MailNotifier._initialized = True

        except ConfigurationError as e:
            self.logger.error(f"配置错误: {e}", extra={"account": "system"})
            print(f"\n配置错误: {e}\n请检查您的.env配置文件后重试。\n")
            sys.exit(1)
        except Exception as e:
            self.logger.error(
                f"初始化失败: {e}", extra={"account": "system"}, exc_info=True
            )
            print(f"\n初始化失败: {e}\n")
            sys.exit(1)

    @property
    def logger(self):
        """获取日志记录器"""
        if MailNotifier._logger is None:
            MailNotifier._logger = self._init_logger()
        return MailNotifier._logger

    @property
    def config(self):
        """获取配置"""
        return MailNotifier._config

    @property
    def pool(self):
        """获取连接池"""
        return MailNotifier._pool

    @property
    def mail_queue(self):
        """获取邮件队列"""
        return MailNotifier._mail_queue

    def _init_logger(self):
        """
        初始化日志系统
        返回:已配置的Logger实例
        """
        logger = logging.getLogger(
            "mail_notifier"
        )  # 创建或获取名为"mail_notifier"的logger
        logger.setLevel(logging.INFO)  # 设置日志级别为INFO
        # 确保不会重复添加handler
        if not logger.handlers:
            handler = logging.StreamHandler()  # 创建控制台输出handler
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - [%(account)s] %(message)s"
                )  # 设置包含时间、日志级别、账户和消息的格式
            )
            logger.addHandler(handler)  # 添加handler到logger
        return logger

    def send(
        self,
        to: Union[str, List[str]],  # 支持单个收件人或收件人列表
        subject: str,  # 邮件主题
        content: str,  # 邮件内容
        content_type: str = "plain",  # 内容类型,默认为纯文本
        callback: Callable[[Dict], Any] = None,  # 可选的回调函数
    ) -> None:
        """
        将邮件发送任务添加到队列（非阻塞）

        参数:
            to - 收件人地址(字符串)或地址列表
            subject - 邮件主题
            content - 邮件内容
            content_type - 内容类型("plain"或"html")
            callback - 可选的回调函数，接收结果字典作为参数
        """
        # 创建任务并添加到队列
        task = {
            "notifier": self,
            "to": to,
            "subject": subject,
            "content": content,
            "content_type": content_type,
            "callback": callback,
        }

        self.mail_queue.put(task)

    def send_sync(
        self,
        to: Union[str, List[str]],
        subject: str,
        content: str,
        content_type: str = "plain",
    ) -> Dict:
        """
        同步发送邮件（阻塞直到完成）

        参数:
            to - 收件人地址或地址列表
            subject - 邮件主题
            content - 邮件内容
            content_type - 内容类型

        返回:
            包含发送结果的字典
        """
        return self._send_sync(to, subject, content, content_type)

    def _send_sync(self, to, subject, content, content_type):
        """
        同步发送邮件的核心逻辑
        参数:
            to - 收件人地址或地址列表
            subject - 邮件主题
            content - 邮件内容
            content_type - 内容类型
        返回:
            包含发送结果的字典
        """
        # 确保收件人是列表形式
        recipients = [to] if isinstance(to, str) else to
        # 初始化结果字典
        result = {"success": [], "failed": {}}

        # 检查收件人列表是否为空
        if not recipients:
            self.logger.warning(
                "收件人列表为空，没有邮件需要发送", extra={"account": "system"}
            )
            return result
        # 按优先级尝试不同账户
        for account in self.config.accounts:
            try:
                # 获取SMTP连接并登录
                self.logger.info(
                    f"尝试使用账户 {account.address} 发送邮件",
                    extra={"account": account.address},
                )
                conn = self.pool.get_connection(account, self.config)

                try:
                    self.logger.info(
                        f"正在登录邮箱账户 {account.address}...",
                        extra={"account": account.address},
                    )
                    conn.login(account.address, account.password)
                except smtplib.SMTPAuthenticationError as auth_error:
                    self.logger.error(
                        f"邮箱账户认证失败: {str(auth_error)}",
                        extra={"account": account.address},
                    )
                    result["failed"][
                        "authentication"
                    ] = f"账户 {account.address} 认证失败: {str(auth_error)}"
                    continue

                # 记录开始发送的日志
                self.logger.info(
                    f"准备发送邮件给 {len(recipients)} 位收件人",
                    extra={"account": account.address},
                )

                # 发送给所有未成功的收件人
                remaining = [r for r in recipients if r not in result["success"]]
                for email in remaining:
                    try:
                        # 为每个收件人创建一个新的邮件对象
                        msg = EmailMessage()
                        msg.set_content(content, subtype=content_type)
                        msg["Subject"] = subject
                        msg["From"] = f"Notification System <{account.address}>"
                        msg["To"] = email  # 设置收件人

                        conn.send_message(msg)  # 发送邮件
                        result["success"].append(email)  # 记录成功
                        self.pool.increment_usage(account)  # 增加使用计数
                        # 记录成功发送的日志
                        self.logger.info(
                            f"成功发送邮件给 {email}",
                            extra={"account": account.address},
                        )
                    except smtplib.SMTPRecipientsRefused as e:
                        # 记录收件人被拒绝的错误
                        result["failed"][email] = str(e)
                        self.logger.warning(
                            f"发送给 {email} 失败 ({str(e)})",
                            extra={"account": account.address},
                        )
                    except Exception as e:
                        # 捕获并记录其他可能的发送错误
                        result["failed"][email] = str(e)
                        self.logger.warning(
                            f"发送给 {email} 时出错: {str(e)}",
                            extra={"account": account.address},
                        )

                # 如果所有收件人都已处理（无论成功或失败）,退出循环
                if set(result["success"] + list(result["failed"].keys())) == set(
                    recipients
                ):
                    break

            except smtplib.SMTPAuthenticationError:
                # 记录认证失败的错误
                self.logger.error(
                    "认证失败",
                    extra={"account": account.address},
                    exc_info=True,  # 包含异常堆栈
                )
                # 继续尝试下一个账户
            except smtplib.SMTPException as e:
                # 记录其他SMTP错误
                self.logger.error(
                    f"SMTP错误: {str(e)}",
                    extra={"account": account.address},
                    exc_info=True,
                )
                # 继续尝试下一个账户
            except Exception as e:
                # 捕获并记录所有其他可能的错误
                self.logger.error(
                    f"发送邮件时出现未预期错误: {str(e)}",
                    extra={"account": account.address},
                    exc_info=True,
                )

        # 如果所有邮箱账户都尝试过但没有成功发送,记录错误
        if not result["success"] and len(self.config.accounts) > 0:
            self.logger.error(
                "所有邮箱账户都无法发送邮件，请检查配置和网络连接",
                extra={"account": "system"},
            )

        return result  # 返回发送结果

    @classmethod
    def close(cls):
        """关闭所有连接和工作线程,释放资源"""
        if cls._logger and cls._pool:
            cls._logger.info("正在关闭所有连接...", extra={"account": "system"})

            # 停止邮件队列
            if cls._mail_queue:
                cls._mail_queue.stop()

            # 关闭所有SMTP连接
            cls._pool.close_all()
            cls._initialized = False
