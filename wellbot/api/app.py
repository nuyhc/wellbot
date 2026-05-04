"""WellBot FastAPI 앱 (Reflex api_transformer 에 마운트).

Reflex State 로 처리할 수 없는 (또는 비효율적인) 케이스를 담당.
- 파일 업로드 (대용량 스트리밍, multipart/form-data)
"""

from __future__ import annotations

from fastapi import FastAPI

from wellbot.api.upload import router as upload_router
from wellbot.api.download import router as download_router

api_app = FastAPI(title="WellBot API", docs_url=None, redoc_url=None)
api_app.include_router(upload_router)
api_app.include_router(download_router)
