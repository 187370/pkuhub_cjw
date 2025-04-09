from notification import MailNotifier
import logging
import time
import random
from typing import List, Tuple, Dict, Union, Callable
from threading import Lock, Event


class VerificationCodeManager:
    """
    验证码管理器 - 存储和管理验证码，提供自动清理过期验证码功能
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """单例模式实现"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VerificationCodeManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """初始化验证码管理器"""
        if self._initialized:
            return

        # 验证码存储格式: {email: (code, expire_time)}
        self._codes = {}
        self._expire_minutes = 15  # 默认过期时间15分钟
        self._cleanup_interval = 60  # 清理间隔(秒)
        self._initialized = True

        # 启动自动清理任务
        self._start_cleanup_task()

    def add_code(self, email: str, code: str) -> None:
        """
        添加或更新验证码

        参数:
            email: 用户邮箱
            code: 验证码
        """
        expire_time = time.time() + (self._expire_minutes * 60)
        with self._lock:
            self._codes[email] = (code, expire_time)
        logging.debug(
            f"已保存验证码 {code} 到 {email}，过期时间 {self._expire_minutes} 分钟"
        )

    def verify_code(self, email: str, code: str) -> bool:
        """
        验证用户提交的验证码是否正确且未过期

        参数:
            email: 用户邮箱
            code: 用户提交的验证码

        返回:
            验证是否通过
        """
        with self._lock:
            if email not in self._codes:
                return False

            stored_code, expire_time = self._codes[email]

            # 检查是否过期
            if time.time() > expire_time:
                # 自动清除过期验证码
                del self._codes[email]
                return False

            # 检查验证码是否匹配
            return stored_code == code

    def remove_code(self, email: str) -> None:
        """
        手动删除验证码(如验证成功后)

        参数:
            email: 用户邮箱
        """
        with self._lock:
            if email in self._codes:
                del self._codes[email]

    def _cleanup_expired(self) -> None:
        """清理所有过期的验证码"""
        now = time.time()
        expired_emails = []

        with self._lock:
            # 找出所有过期的邮箱
            for email, (_, expire_time) in self._codes.items():
                if now > expire_time:
                    expired_emails.append(email)

            # 删除过期的验证码
            for email in expired_emails:
                del self._codes[email]

        if expired_emails:
            logging.debug(f"自动清理了 {len(expired_emails)} 个过期验证码")

    def _start_cleanup_task(self) -> None:
        """启动定期清理任务"""
        import threading

        def cleanup_loop():
            consecutive_errors = 0
            max_consecutive_errors = 3

            while True:
                try:
                    self._cleanup_expired()
                    consecutive_errors = 0  # 成功执行后重置错误计数

                except Exception as e:
                    consecutive_errors += 1
                    logging.error(
                        f"清理验证码时出错 (第{consecutive_errors}次): {str(e)}"
                    )

                    # 如果连续多次出错，添加更长的暂停时间让系统恢复
                    if consecutive_errors >= max_consecutive_errors:
                        logging.critical(
                            f"验证码清理任务连续{max_consecutive_errors}次失败，暂停较长时间..."
                        )
                        time.sleep(self._cleanup_interval * 5)  # 暂停更长时间
                        consecutive_errors = 0  # 重置错误计数

                time.sleep(self._cleanup_interval)

        # 使用守护线程，这样主程序退出时，清理线程也会退出
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        logging.info("验证码自动清理任务已启动")

    @property
    def expire_minutes(self) -> int:
        """获取验证码过期时间(分钟)"""
        return self._expire_minutes

    @expire_minutes.setter
    def expire_minutes(self, minutes: int) -> None:
        """设置验证码过期时间(分钟)"""
        if minutes < 1:
            raise ValueError("过期时间不能小于1分钟")
        self._expire_minutes = minutes


# 创建全局验证码管理器实例
code_manager = VerificationCodeManager()


def code_generator():
    """生成验证码
    生成6位数字验证码
    """
    return "".join([random.choice("0123456789") for _ in range(6)])


def send_verification_codes(
    email_list: List[str], subject: str = "验证码 - PKUHUB", timeout: int = 60
) -> List[Tuple[bool, str, str]]:
    """
    发送验证码到指定邮箱列表，使用任务队列处理

    参数:
        email_list: 接收验证码的邮箱列表
        subject: 邮件标题，默认为"验证码 - PKUHUB"
        timeout: 发送超时时间（秒）

    返回:
        包含三元组的列表，每个三元组包含(是否成功, 邮箱, 验证码)
    """
    notifier = MailNotifier()

    # 用于存储每个邮箱的发送状态和结果
    results_dict = {}
    # 用于线程同步的事件对象
    completion_event = Event()
    # 记录总任务数和已完成任务数
    total_tasks = len(email_list)
    completed_tasks = 0

    # 结果锁，用于线程安全操作
    results_lock = Lock()

    def on_task_complete(email, code, result):
        """处理单个邮件任务完成"""
        nonlocal completed_tasks
        with results_lock:
            success = email in result.get("success", [])
            results_dict[email] = (success, email, code)

            # 如果发送失败，移除验证码
            if not success:
                error = result.get("failed", {}).get(email, "未知错误")
                logging.warning(f"邮件发送失败，邮箱: {email}, 错误: {error}")
                code_manager.remove_code(email)

            # 增加已完成任务计数
            completed_tasks += 1

            # 如果所有任务都已完成，设置完成事件
            if completed_tasks >= total_tasks:
                completion_event.set()

    # 为每个邮箱启动发送任务
    for email in email_list:
        # 生成验证码
        code = code_generator()

        # 添加验证码到管理器
        code_manager.add_code(email, code)

        # 创建HTML内容
        content = f"""
        <div style="font-family:Arial,sans-serif; max-width:600px; margin:0 auto; padding:20px; border:1px solid #ddd; border-radius:5px;">
            <h2 style="color:#900023; text-align:center;">PKUHUB</h2>
            <p>您好!</p>
            <p>您的验证码是: <strong style="font-size:24px; color:#900023;">{code}</strong></p>
            <p>验证码将在{code_manager.expire_minutes}分钟内有效。如果您没有请求此验证码，请忽略此邮件。</p>
            <p style="font-size:12px; color:#666; margin-top:30px;">本邮件由系统自动发送，请勿回复</p>
        </div>
        """

        # 创建特定邮件的回调函数
        def make_callback(email_addr, verification_code):
            def callback_func(result):
                on_task_complete(email_addr, verification_code, result)

            return callback_func

        # 添加发送任务到队列
        notifier.send(
            to=email,
            subject=subject,
            content=content,
            content_type="html",
            callback=make_callback(email, code),
        )

    # 等待所有任务完成或超时
    completion_event.wait(timeout=timeout)

    # 处理超时情况
    if not completion_event.is_set():
        logging.warning(f"验证码发送操作超时 (超过 {timeout} 秒)")
        # 处理未完成的任务
        with results_lock:
            for email in email_list:
                if email not in results_dict:
                    # 为未完成的邮箱记录失败
                    code = next(
                        (c for e, (_, c) in results_dict.items() if e == email),
                        code_generator(),
                    )
                    results_dict[email] = (False, email, code)
                    # 从验证码管理器中移除
                    code_manager.remove_code(email)

    # 按照原始邮件列表顺序返回结果
    return [
        results_dict.get(email, (False, email, code_generator()))
        for email in email_list
    ]


def verify_code(email: str, submitted_code: str) -> bool:
    """
    验证用户提交的验证码

    参数:
        email: 用户邮箱
        submitted_code: 用户提交的验证码

    返回:
        验证是否通过
    """
    result = code_manager.verify_code(email, submitted_code)
    if result:
        # 验证成功后删除验证码，防止重复使用
        code_manager.remove_code(email)
    return result
