

from typing import List, Optional

from pydantic import BaseModel


class DocumentWithScore(BaseModel):
    text: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[dict] = None


class Query(BaseModel):
    query: str
    top_k: Optional[int] = 3


class QueryWithEmbedding(Query):
    embedding: List[float]


class QueryResult(BaseModel):
    query: str
    results: List[DocumentWithScore]


def get_packed_answer(results, limit_length: Optional[int] = 0) -> str:
    text_chunks = []
    for r in results:
        prefix = ""
        if r.metadata.get("url"):
            prefix = "The following information is from: " + r.metadata.get("url") + "\n"
        text_chunks.append(prefix + r.text)
    answer_text = "\n\n".join(text_chunks)
    if limit_length != 0:
        return answer_text[:limit_length]
    else:
        return answer_text
