import asyncio

from app.services.rag.memory_ai import (
    ChatAI, AIConfig, SQLAlchemyChatRepository, Base, LightRAGBackend,
)
from app.services.rag.memory_ai.scripts.Lightrag_step import init_lightrag
from app.utils.database import SessionLocal, engine


async def main():
    # 一次性建表（生产用 Alembic 迁移）
    Base.metadata.create_all(engine)

    # 初始化 LightRAG（确保 lightrag_ingest.py 已经跑过）
    rag = await init_lightrag()

    ai = ChatAI(
        config=AIConfig(
            model="",            # LightRAGBackend 不用这个字段
            api_key="",
            base_url="",
            system_prompt=(
                "你是一位电商客服，请使用知识图谱中的知识进行回答,如果没有找到相关的知识，则不回答"
            ),
        ),
        repository=SQLAlchemyChatRepository(session_factory=SessionLocal),
        backend=LightRAGBackend(rag=rag, mode="hybrid", history_turns=3),
    )

    tenant = "demo_user"
    session = ai.get_or_create_session(tenant_id=tenant)
    sid = session["session_id"]

    # 第 1 轮：图谱能力体现
    r1 = await ai.chat(
        session_id=sid, tenant_id=tenant,
        message="蓝色的裙子有没有大号的",
    )
    print("Q1 →", r1[:300], "...\n")

    # # 第 2 轮：验证会话记忆（代词"它们"依赖上下文）
    # r2 = await ai.chat(
    #     session_id=sid, tenant_id=tenant,
    #     message="它们的维护要点分别是什么？",
    # )
    # print("Q2 →", r2[:300], "...\n")
    #
    # # 流式示例
    # print("Q3 (stream) →", end=" ", flush=True)
    # async for chunk in ai.stream_chat(
    #     session_id=sid, tenant_id=tenant,
    #     message="请用一句话总结刚才的对话。",
    # ):
    #     print(chunk, end="", flush=True)
    # print()


if __name__ == "__main__":
    asyncio.run(main())