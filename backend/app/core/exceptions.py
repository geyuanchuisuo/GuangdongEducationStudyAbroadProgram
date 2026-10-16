class BusinessError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class AuthError(BusinessError):
    def __init__(self, message: str = "未登录或Token过期"):
        super().__init__(code=40101, message=message)


class ForbiddenError(BusinessError):
    def __init__(self, message: str = "无权限访问"):
        super().__init__(code=40301, message=message)


class NotFoundError(BusinessError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=40401, message=message)


class ValidationError(BusinessError):
    def __init__(self, message: str = "参数验证失败"):
        super().__init__(code=40002, message=message)


ERROR_CODE_MAP: dict[int, str] = {
    200: "成功",
    40001: "用户名或密码错误",
    40002: "参数验证失败",
    40003: "账号已被禁用",
    40101: "未登录或Token过期",
    40301: "无权限访问",
    40401: "资源不存在",
    50001: "服务器内部错误",
}
