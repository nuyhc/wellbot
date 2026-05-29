"""WellBot FastAPI 앱 (Reflex api_transformer 에 마운트).

Reflex State 로 처리할 수 없는 (또는 비효율적인) 케이스를 담당.
- 파일 업로드 (대용량 스트리밍, multipart/form-data)
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from wellbot import log_context
from wellbot.api.upload import router as upload_router
from wellbot.api.download import router as download_router
from wellbot.logging_config import install_asyncio_handler

api_app = FastAPI(title="WellBot API", docs_url=None, redoc_url=None)


@api_app.on_event("startup")
async def _install_loop_exception_handler() -> None:
    """서버 이벤트 루프에 asyncio uncaught 예외 핸들러를 설치한다.

    setup_logging() 은 앱 import 시점(루프 밖)에 실행되므로
    asyncio 핸들러는 루프가 살아있는 startup 에서 설치해야 한다.
    """
    install_asyncio_handler()


@api_app.middleware("http")
async def _bind_log_context(request: Request, call_next):
    """요청마다 request_id 를 바인딩해 로그 상관관계를 추적한다.

    emp_no 는 인증을 거친 엔드포인트에서 log_context.bind() 로 보강한다.
    """
    with log_context.scope(request_id=log_context.new_request_id()):
        return await call_next(request)


api_app.include_router(upload_router)
api_app.include_router(download_router)
