import json, logging, re, time, html, sys, asyncio, uvicorn, os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# 애플리케이션 로깅 설정 (stdout으로 출력하여 podman logs에서 확인 가능)
# basicConfig는 uvicorn에 의해 무시될 수 있으므로 force=True 사용
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Python 3.8+: 기존 핸들러를 제거하고 재설정
)

# 루트 로거와 애플리케이션 로거 레벨 명시적 설정
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('routers').setLevel(logging.INFO)
logging.getLogger('utils').setLevel(logging.INFO)

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
    docs_url=None,  # 커스텀 docs 엔드포인트 사용
    redoc_url=None,  # 커스텀 redoc 엔드포인트 사용
    openapi_url="/api/openapi.json"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Swagger UI 정적 파일 마운트 (폐쇄망 환경 대응)
app.mount("/static", StaticFiles(directory="static"), name="static")

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

# 애플리케이션 시작 시 로그 설정 적용
configure_pyats_logging()

# 커스텀 Swagger UI (로컬 정적 파일 사용)
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <link type="text/css" rel="stylesheet" href="/static/swagger-ui/swagger-ui.css">
        <title>Network Admin API - Swagger UI</title>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="/static/swagger-ui/swagger-ui-bundle.js"></script>
        <script src="/static/swagger-ui/swagger-ui-standalone-preset.js"></script>
        <script>
        const ui = SwaggerUIBundle({
            url: '/api/openapi.json',
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true
        })
        </script>
    </body>
    </html>
    """)

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




