# lsbase/core/exceptions.py

class APIRequestError(Exception):
    """API 요청 실패 시 발생하는 기본 예외 클래스입니다."""
    def __init__(self, message, rsp_cd=None):
        self.rsp_cd = rsp_cd
        error_message = f"[Code: {rsp_cd}] {message}" if rsp_cd else message
        super().__init__(error_message)
