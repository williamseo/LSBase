# lsbase/logger.py
import logging
import sys
from . import config # config 모듈 임포트

def setup_logger():
    # 최상위 로거 'lsbase'를 가져옴
    logger = logging.getLogger('lsbase')
    logger.setLevel(config.LOG_LEVEL) # config에서 읽어온 로그 레벨로 설정

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
    
    # 설정된 로그 레벨을 INFO 레벨로 출력하여 확인
    logger.info(f"Logger initialized with level: {config.LOG_LEVEL}")
    
    return logger
