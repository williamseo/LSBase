# lsbase/core/exceptions.py

class APIRequestError(Exception):
    """API 요청 실패 시 발생하는 기본 예외 클래스입니다."""
    def __init__(self, message, rsp_cd=None, tr_code=None):
        self.rsp_cd = rsp_cd
        self.tr_code = tr_code
        error_message = f"TR({tr_code}), Code({rsp_cd}): {message}" if all([tr_code, rsp_cd]) else message
        super().__init__(error_message)

class AuthenticationError(APIRequestError):
    """인증 관련 문제(예: 토큰 만료) 발생 시"""
    pass

class RateLimitError(APIRequestError):
    """API 호출 제한(Throttling)에 도달했을 때"""
    pass

class InvalidInputError(APIRequestError):
    """잘못된 파라미터(예: 존재하지 않는 종목코드)를 입력했을 때"""
    pass

class NetworkError(APIRequestError):
    """네트워크 타임아웃 등 통신 자체의 문제 발생 시"""
    pass
