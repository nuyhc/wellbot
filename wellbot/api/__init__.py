"""WellBot FastAPI custom routes.

Reflex 0.8 의 `rx.App.api_transformer` 에 마운트되는 독립 FastAPI 앱.
파일 업로드처럼 멀티파트 스트리밍이 필요한 HTTP 엔드포인트를 제공한다.
"""

from wellbot.api.app import api_app

__all__ = ["api_app"]
