import json, logging, re, time, html, sys, asyncio, uvicorn, os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from typing import List, Dict, Tuple, Union, Optional
## Router
from routers.webhook import router as webhook_router
from routers.network import router as network_router

# .env 파일에서 환경 변수 로드
load_dotenv()

# pyATS 로깅 환경 변수 설정 (로그 출력 완전 비활성화)
os.environ['PYATS_LOGGING_LEVEL'] = 'CRITICAL'
os.environ['GENIE_LOGGING_LEVEL'] = 'CRITICAL'
os.environ['UNICON_LOGGING_LEVEL'] = 'CRITICAL'
os.environ['PYATS_DISABLE_LOGGING'] = '1'
os.environ['GENIE_DISABLE_LOGGING'] = '1'

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Network Admin API",
    description="API for managing network devices and monitoring",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Network",
            "description": "API for network management and monitoring"
        },
        {
            "name": "Webhook",
            "description": "API for handling webhooks from external services"
        }
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router, prefix="/api/v1")
app.include_router(network_router, prefix="/api/v1")

# fast api에서 router를 분리해서 기능별로 구성
# /api/webhook/
# /api/network/

# pyATS 로거 설정 (로그 출력 완전 비활성화)
def configure_pyats_logging():
    """pyATS, genie, unicon 로그를 완전히 비활성화"""
    import logging
    
    # 모든 관련 로거들을 완전히 비활성화
    loggers_to_disable = [
        'pyats', 'genie', 'unicon', 'pyats.aetest', 'pyats.topology',
        'pyats.connections', 'pyats.datastructures', 'pyats.easypy',
        'genie.libs', 'genie.libs.parser', 'genie.libs.sdk',
        'unicon.core', 'unicon.plugins', 'unicon.connections'
    ]
    
    for logger_name in loggers_to_disable:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.disabled = True
        logger.propagate = False
        
        # 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # 루트 로거에서도 관련 로그 필터링
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(lambda record: not any(
            record.name.startswith(name) for name in ['pyats', 'genie', 'unicon']
        ))

# 애플리케이션 시작 시 로그 설정 적용
configure_pyats_logging()

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """API 헬스체크"""
    return {
        "status": "healthy",
        "message": "Network Admin API is running",
        "version": "1.0.0"
    }

# 2. FastAPI 실행 시 초기 설정
@app.on_event("startup")
async def startup_event():
    # 로그 설정이 이미 위에서 적용되었지만, 시작 시 한 번 더 확인
    configure_pyats_logging()




