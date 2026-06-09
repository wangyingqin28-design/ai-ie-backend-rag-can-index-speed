import json
from pathlib import Path
from typing import Any, Optional

from lightrag import QueryParam


def clear_query_cache(
    working_dir: str | Path,
    *,
    question: Optional[str] = None,
    clear_all: bool = False,
) -> None:
    """Clear stale LightRAG hybrid query cache entries."""

    cache_file = Path(working_dir) / "kv_store_llm_response_cache.json"
    if not cache_file.exists():
        return

    if clear_all:
        cache_file.unlink(missing_ok=True)
        return

    try:
        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        cache_file.unlink(missing_ok=True)
        return

    changed = False
    for key in list(cache_data.keys()):
        record = cache_data.get(key, {})
        original_prompt = record.get("original_prompt") if isinstance(record, dict) else None
        if key.startswith("hybrid:query:") or key.startswith("hybrid:keywords:"):
            if question is None or original_prompt == question:
                cache_data.pop(key, None)
                changed = True

    if changed:
        cache_file.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


async def retrieve_context(
    rag,
    question: str,
    *,
    query_param: Optional[QueryParam] = None,
) -> dict:
    """Return LightRAG raw retrieval data using aquery_data."""

    query_param = query_param or QueryParam(
        mode="hybrid",
        enable_rerank=True,
        top_k=20,
        chunk_top_k=5,
        response_type="Single Paragraph",
    )
    return await rag.aquery_data(question, query_param)


def format_retrieval_context(result: dict, *, max_items: int = 12, max_chunks: int = 5) -> str:
    """Format entities, relationships, and chunks into prompt-friendly context."""

    payload: dict[str, Any] = result.get("data", {})
    entities = payload.get("entities", [])[:max_items]
    relationships = payload.get("relationships", [])[:max_items]
    chunks = payload.get("chunks", [])[:max_chunks]

    entity_lines = [
        "- {name} | type={type} | desc={desc}".format(
            name=entity.get("entity_name", ""),
            type=entity.get("entity_type", ""),
            desc=entity.get("description", ""),
        )
        for entity in entities
    ]
    relation_lines = [
        "- {src} -> {keywords} -> {tgt} | desc={desc}".format(
            src=relation.get("src_id", ""),
            keywords=relation.get("keywords", ""),
            tgt=relation.get("tgt_id", ""),
            desc=relation.get("description", ""),
        )
        for relation in relationships
    ]
    chunk_lines = [
        "[chunk {ref}]\n{content}".format(
            ref=chunk.get("reference_id", ""),
            content=chunk.get("content", ""),
        )
        for chunk in chunks
    ]

    return (
        "[Entities]\n"
        + ("\n".join(entity_lines) or "None")
        + "\n\n[Relationships]\n"
        + ("\n".join(relation_lines) or "None")
        + "\n\n[Chunks]\n"
        + ("\n\n".join(chunk_lines) or "None")
    )
