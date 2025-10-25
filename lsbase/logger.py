# lsbase/logger.py
import logging
import sys

def setup_logger():
    # 최상위 로거 'lsbase'를 가져옴
    logger = logging.getLogger('lsbase')
    logger.setLevel(logging.INFO) # 기본 로그 레벨 설정

    # 이미 핸들러가 설정되어 있다면 중복 추가 방지
    if logger.hasHandlers():
        logger.handlers.clear()

    # 스트림 핸들러 (콘솔 출력)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
