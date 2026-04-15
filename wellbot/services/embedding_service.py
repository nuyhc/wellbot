"""임베딩 및 FAISS 인덱스 서비스.

- Bedrock Titan Embeddings V2 호출로 텍스트 임베딩 생성
- FAISS 인덱스 빌드/직렬화/역직렬화
- 대화 단위 LRU 메모리 캐시 (다음 Phase 에서 활용)

업로드 시 (Phase 2):
  1. 청크 텍스트 → Bedrock Titan 임베딩
  2. FAISS IndexFlatIP 인덱스 빌드
  3. faiss.serialize_index() → bytes → S3 저장

검색 시 (Phase 5, 아직 미사용):
  1. S3 에서 index.faiss + chunks.jsonl 다운로드
  2. faiss.deserialize_index() → 메모리 인덱스
  3. query 임베딩 생성 → index.search() → top-k 청크
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Iterable, Sequence

import boto3
import numpy as np

from wellbot.constants import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_ID,
    FAISS_CACHE_MAX_CONVERSATIONS,
)


# ── Bedrock Titan 임베딩 호출 ──


def _get_client():
    """Bedrock Runtime 클라이언트. Bedrock 호출과 동일한 자격증명 사용."""
    region = os.environ.get(
        "AWS_REGION",
        os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    return boto3.client("bedrock-runtime", region_name=region)


def embed_text(text: str) -> np.ndarray:
    """단일 텍스트를 임베딩한다.

    Returns:
        shape=(EMBEDDING_DIMENSION,) float32 array.
    """
    client = _get_client()
    body = json.dumps({"inputText": text}).encode("utf-8")
    response = client.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    payload = json.loads(response["body"].read())
    embedding = payload.get("embedding") or []
    arr = np.asarray(embedding, dtype=np.float32)
    if arr.shape[0] != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"임베딩 차원 불일치: 예상 {EMBEDDING_DIMENSION}, 실제 {arr.shape[0]}"
        )
    return arr


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """여러 텍스트를 배치 임베딩한다.

    Titan V2 는 배치 입력을 지원하지 않아 순차 호출.
    (향후 Bedrock batch inference 로 최적화 가능)

    Returns:
        shape=(N, EMBEDDING_DIMENSION) float32 array.
    """
    if not texts:
        return np.empty((0, EMBEDDING_DIMENSION), dtype=np.float32)

    vectors: list[np.ndarray] = []
    for text in texts:
        if not text.strip():
            vectors.append(np.zeros(EMBEDDING_DIMENSION, dtype=np.float32))
            continue
        vectors.append(embed_text(text))
    return np.vstack(vectors)


# ── FAISS 인덱스 빌드/직렬화 ──


def build_index(embeddings: np.ndarray):
    """임베딩 배열로 FAISS IndexFlatIP (내적) 인덱스를 빌드한다.

    Titan V2 는 정규화되지 않은 벡터를 반환하므로, 코사인 유사도를 위해
    명시적으로 L2 정규화한 뒤 내적 검색 사용.

    Args:
        embeddings: shape=(N, EMBEDDING_DIMENSION) float32 array.

    Returns:
        faiss.IndexFlatIP 인덱스.
    """
    import faiss

    if embeddings.size == 0:
        # 빈 인덱스
        return faiss.IndexFlatIP(EMBEDDING_DIMENSION)

    # 정규화 (in-place)
    normalized = embeddings.copy()
    faiss.normalize_L2(normalized)

    index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
    index.add(normalized)
    return index


def serialize_index(index) -> bytes:
    """FAISS 인덱스를 바이트로 직렬화 (S3 PUT 용)."""
    import faiss

    buffer = faiss.serialize_index(index)
    # numpy array 로 반환되므로 bytes 로 변환
    return bytes(buffer)


def deserialize_index(data: bytes):
    """바이트에서 FAISS 인덱스를 역직렬화 (S3 GET 후)."""
    import faiss

    arr = np.frombuffer(data, dtype=np.uint8)
    return faiss.deserialize_index(arr)


def search_index(index, query_vec: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
    """인덱스에서 top-k 검색.

    Args:
        index: faiss 인덱스.
        query_vec: shape=(EMBEDDING_DIMENSION,) float32.
        top_k: 반환 개수.

    Returns:
        (scores, indices) — 각 shape=(1, top_k) array.
    """
    import faiss

    q = query_vec.astype(np.float32).reshape(1, -1).copy()
    faiss.normalize_L2(q)
    k = min(top_k, index.ntotal) if index.ntotal > 0 else 0
    if k == 0:
        return np.empty((1, 0), dtype=np.float32), np.empty((1, 0), dtype=np.int64)
    return index.search(q, k)


# ── 대화 단위 LRU 캐시 (Phase 5 에서 본격 활용) ──


@dataclass
class ConversationIndex:
    """대화 하나에 속한 통합 FAISS 인덱스 + 청크 메타."""

    smry_id: str
    index: object                          # faiss.Index
    chunks: list[dict] = field(default_factory=list)
    # chunks[i] = {"file_no": int, "file_name": str, "seq": int, "text": str}


class FaissCache:
    """대화 단위 FAISS 인덱스 LRU 메모리 캐시."""

    def __init__(self, max_size: int = FAISS_CACHE_MAX_CONVERSATIONS) -> None:
        self._store: OrderedDict[str, ConversationIndex] = OrderedDict()
        self._max_size = max_size
        self._lock = Lock()

    def get(self, smry_id: str) -> ConversationIndex | None:
        with self._lock:
            if smry_id not in self._store:
                return None
            # LRU 갱신
            self._store.move_to_end(smry_id)
            return self._store[smry_id]

    def set(self, smry_id: str, conv_index: ConversationIndex) -> None:
        with self._lock:
            self._store[smry_id] = conv_index
            self._store.move_to_end(smry_id)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate(self, smry_id: str) -> None:
        with self._lock:
            self._store.pop(smry_id, None)


_cache = FaissCache()


def get_cache() -> FaissCache:
    """전역 FAISS 캐시 인스턴스."""
    return _cache


# ── 대화별 인덱스 로드 + 검색 ──


def load_conversation_index(smry_id: str) -> ConversationIndex:
    """대화에 속한 모든 파일의 청크/인덱스를 S3 에서 로드해 통합한다.

    - 각 파일의 chunks.jsonl + index.faiss 를 S3 에서 GET
    - 모든 임베딩을 하나의 IndexFlatIP 로 merge
    - chunks 리스트는 flat: [{file_no, file_name, seq, text}, ...]
      -> FAISS 검색 결과 인덱스 → chunks[idx] 로 바로 매핑 가능

    파일이 처리 중이거나 실패한 경우(S3 에 파생물 부재) 는 조용히 스킵.
    """
    # 순환 import 방지 위해 lazy
    from wellbot.services import attachment_service
    from wellbot.services import chunker as chunker_mod
    from wellbot.services import storage_service

    import faiss

    atts = attachment_service.get_conversation_attachments(smry_id)

    flat_chunks: list[dict] = []
    vectors: list[np.ndarray] = []

    for att in atts:
        if not att.s3_prefix:
            continue
        chunks_key = f"{att.s3_prefix}chunks.jsonl"
        index_key = f"{att.s3_prefix}index.faiss"

        try:
            chunks_bytes = storage_service.download_bytes(chunks_key)
            index_bytes = storage_service.download_bytes(index_key)
        except Exception:
            # 처리 중이거나 이미지 등 파생물이 없는 파일 → 스킵
            continue

        chunks = chunker_mod.chunks_from_jsonl(chunks_bytes)
        file_index = deserialize_index(index_bytes)

        # 이 파일의 모든 벡터를 추출하려면 reconstruct 를 사용
        n = file_index.ntotal
        if n != len(chunks) or n == 0:
            # 정합성 불일치 → 스킵
            continue
        try:
            file_vectors = np.vstack(
                [file_index.reconstruct(i) for i in range(n)]
            )
        except Exception:
            continue

        vectors.append(file_vectors)
        for c in chunks:
            flat_chunks.append(
                {
                    "file_no": att.file_no,
                    "file_name": att.file_name,
                    "seq": c.seq,
                    "text": c.text,
                }
            )

    # 통합 인덱스 구축
    if vectors:
        all_vectors = np.vstack(vectors).astype(np.float32)
        # build_index 는 normalize_L2 + IndexFlatIP
        index = build_index(all_vectors)
    else:
        index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)

    return ConversationIndex(
        smry_id=smry_id,
        index=index,
        chunks=flat_chunks,
    )


def get_or_load(smry_id: str) -> ConversationIndex:
    """캐시 우선 → 없으면 S3 에서 로드."""
    cached = _cache.get(smry_id)
    if cached is not None:
        return cached
    conv_index = load_conversation_index(smry_id)
    _cache.set(smry_id, conv_index)
    return conv_index


def search_conversation(
    smry_id: str,
    query: str,
    top_k: int = 5,
    file_names: Iterable[str] | None = None,
) -> list[dict]:
    """대화 인덱스에서 유사도 top-k 검색.

    Args:
        smry_id: 대화 ID
        query: 자연어 쿼리
        top_k: 반환 개수
        file_names: 지정 시 해당 파일명만 검색 대상

    Returns:
        [{file_no, file_name, seq, text, score}, ...]  (score 내림차순)
    """
    conv_index = get_or_load(smry_id)
    if conv_index.index is None or conv_index.index.ntotal == 0:
        return []

    query_vec = embed_text(query)

    # 탐색은 top_k 의 3배까지 가져와 필터 여유 확보
    scores, ids = search_index(
        conv_index.index, query_vec, top_k * 3 if file_names else top_k
    )

    allowed = None
    if file_names:
        allowed = {n.strip().lower() for n in file_names if n and n.strip()}

    results: list[dict] = []
    for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
        if idx < 0 or idx >= len(conv_index.chunks):
            continue
        chunk = conv_index.chunks[idx]
        if allowed and chunk["file_name"].lower() not in allowed:
            continue
        results.append({**chunk, "score": float(score)})
        if len(results) >= top_k:
            break
    return results
