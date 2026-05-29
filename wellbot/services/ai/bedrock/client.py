"""Bedrock Runtime boto3 클라이언트 싱글턴."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import boto3


@lru_cache(maxsize=1)
def get_client() -> Any:
    """Bedrock Runtime 클라이언트를 생성한다 (싱글턴)."""
    region = os.environ.get(
        "AWS_REGION",
        os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    return boto3.client("bedrock-runtime", region_name=region)
