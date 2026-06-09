# -*- coding: utf-8 -*-
"""SQL_RAG 主接口汇总入口。"""

# 修改日期：2026-06-02 10:42:00。
# 修改理由：把原 data_cleaning/main.py 的主调用关系入口上移到 SQL_RAG 根目录，后续固定从 SQL_RAG/main.py 汇总调用清洗、入库和 RAG 同步链路。

# 导入 JSON 标准库，用于打印运行摘要。
import json
# 导入 sys，用于把 data_cleaning 功能包目录加入模块搜索路径。
import sys
# 导入 dataclass 转字典工具，用于输出 PipelineSummary。
from dataclasses import asdict
# 导入 Path，用于处理输入、输出和配置文件路径。
from pathlib import Path
# 导入 Sequence，用于标注命令行参数类型。
from typing import Sequence

# 定位当前 SQL_RAG 根目录。
SQL_RAG_DIR = Path(__file__).resolve().parent
# Windows 终端默认 GBK 时可能无法打印模型返回的特殊字符，这里统一切到 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    # 只影响当前进程输出编码，不改变业务逻辑。
    sys.stdout.reconfigure(encoding="utf-8")
# 定位 data_cleaning 功能包目录。
DATA_CLEANING_DIR = SQL_RAG_DIR / "data_cleaning"
# 直接运行 SQL_RAG/main.py 时，把 data_cleaning 加入模块搜索路径。
if str(DATA_CLEANING_DIR) not in sys.path:
    # 插入到最前面，确保优先加载当前 SQL_RAG 里的功能包。
    sys.path.insert(0, str(DATA_CLEANING_DIR))

# 导入通用 env 解析工具。
from common.utils import parse_env_file
# 导入 LlamaIndex 官方 Markdown 读取封装。
from cleaning_extraction.markdown_reader import load_markdown_documents
# 导入项目问答成对适配器；内部使用 LlamaIndex pipeline/evaluator。
from cleaning_extraction.qa_pairer import pair_markdown_questions_answers
# 导入 LlamaIndex 官方 transformation 清洗封装。
from cleaning_extraction.text_cleaner import clean_qa_pair_nodes_with_llamaindex
# 导入 LlamaIndex 官方 transformation 问答元数据提取封装。
from cleaning_extraction.qa_extractor import extract_qa_metadata_with_llamaindex
# 导入 LlamaIndex 官方语义分块封装。
from semantic_chunking.semantic_chunker import semantic_chunk_nodes_with_llamaindex
# 导入 LlamaIndex 官方 TextNode 文档内聚类封装。
from semantic_chunking.clusterer import assign_rag_clusters_with_llamaindex, build_cluster_summary_nodes_with_llamaindex
# 导入 LlamaIndex 官方 TextNode 跨文档全局聚类封装。
from semantic_chunking.global_clusterer import assign_global_clusters_with_llamaindex, build_global_cluster_summary_nodes_with_llamaindex
# 导入 LlamaIndex 官方 embedding 向量化封装。
from vectorization.vectorizer import build_llamaindex_embedding_model, vectorize_nodes_with_llamaindex
# 导入 LlamaIndex TextNode JSON 整理和输出封装。
from storage.json_writer import llamaindex_cluster_nodes_to_storage_json, llamaindex_global_cluster_nodes_to_storage_json, llamaindex_nodes_to_storage_json, write_json_outputs
# 导入数据库写入统一接口。
from storage.database_writer import save_records_to_database
# 导入数据库写入 bundle 和运行摘要结构。
from data_structures.models import DatabaseWriteBundle, PipelineSummary
# 导入多文档关系构建接口。
from data_structures.relation_builder import (
    apply_fusion_metadata_with_llamaindex,
    build_chunk_fusion_payloads_with_llamaindex,
    build_document_version_payloads,
    build_entity_relation_payloads,
    build_ingestion_job_payload,
    build_job_id,
    build_neo4j_triple_payloads,
    build_rag_sync_payloads,
    build_validation_issue_payloads,
)
# 导入命令行参数定义接口。
from pipeline_cli import build_arg_parser


def _normalize_main_argv(argv: Sequence[str] | None) -> list[str]:
    # argv 为空时读取系统命令行参数。
    if argv is None:
        # 返回去掉脚本名后的参数列表。
        return list(sys.argv[1:])
    # argv 不为空时转成普通列表，避免多次迭代 Sequence。
    return list(argv)


def _is_agent_runtime_request(argv: list[str]) -> bool:
    # 约定 python main.py agent ... 进入 RAG Agent 运行时。
    return bool(argv) and argv[0] == "agent"


def _is_model_service_request(argv: list[str]) -> bool:
    # 约定 python main.py model-service ... 进入 Qwen3.5 模型服务部署辅助入口。
    return bool(argv) and argv[0] == "model-service"


def _is_qwen35_2b_request(argv: list[str]) -> bool:
    # 约定 python main.py qwen35-2b ... 进入当前本机 Qwen3.5-2B GGUF 验证模型入口。
    return bool(argv) and argv[0] == "qwen35-2b"


def _is_business_brain_service_request(argv: list[str]) -> bool:
    # 约定 python main.py business-brain-service ... 启动商业级业务脑 HTTP 服务。
    return bool(argv) and argv[0] == "business-brain-service"


def _is_business_brain_health_request(argv: list[str]) -> bool:
    # 约定 python main.py business-brain-health ... 检查业务脑依赖是否就绪。
    return bool(argv) and argv[0] == "business-brain-health"


def _is_mcp_gateway_request(argv: list[str]) -> bool:
    # 约定 python main.py mcp-gateway ... 进入 SQL_RAG MCP 工具网关入口。
    return bool(argv) and argv[0] == "mcp-gateway"


def run_model_service_runtime(argv: Sequence[str]) -> int:
    # 导入 module_config 下的模型服务部署辅助入口。
    from module_config.model_service import run_model_service_cli

    # 把去掉子命令后的参数交给模型服务模块处理。
    return run_model_service_cli(argv, sql_rag_dir=SQL_RAG_DIR)


def run_qwen35_2b_runtime(argv: Sequence[str]) -> int:
    # 导入 Qwen3.5-2B 本机验证模型服务入口。
    from module_config.model_service import run_qwen35_2b_cli

    # 把去掉子命令后的参数交给 Qwen3.5-2B 模块处理。
    return run_qwen35_2b_cli(argv, sql_rag_dir=SQL_RAG_DIR)


def run_business_brain_service(argv: Sequence[str]) -> int:
    # 导入业务脑 HTTP 服务启动入口。
    from overall_planning.agent_Business_Brain.business_brain_service import run_business_brain_service_cli

    # 把去掉子命令后的参数交给业务脑服务模块处理。
    return run_business_brain_service_cli(argv, sql_rag_dir=SQL_RAG_DIR)


def run_business_brain_health(argv: Sequence[str]) -> int:
    # 导入业务脑健康检查入口。
    from overall_planning.agent_Business_Brain.business_brain_service import run_business_brain_health_cli

    # 把去掉子命令后的参数交给业务脑健康检查模块处理。
    return run_business_brain_health_cli(argv, sql_rag_dir=SQL_RAG_DIR)


def run_mcp_gateway_runtime(argv: Sequence[str]) -> int:
    # 导入 MCP Gateway 运行入口，main 只负责分发，不承载网关工具逻辑。
    from overall_planning.agent_Business_Brain.mcp_gateway_runtime import run_mcp_gateway_cli

    # 把去掉子命令后的参数交给 MCP Gateway 入口解析。
    return run_mcp_gateway_cli(argv, sql_rag_dir=SQL_RAG_DIR)


def run_agent_runtime(argv: Sequence[str]) -> int:
    # 导入第 1 点业务大脑配置和运行时。
    from overall_planning.agent_Business_Brain import BusinessBrainRuntime, build_agent_arg_parser, load_business_brain_config
    # 导入第 2 点三层记忆配置和运行时。
    from overall_planning.long_memory import ThreeLayerMemoryRuntime, load_memory_config
    # 导入第 3 点纠错飞轮配置和运行时。
    from overall_planning.Answer_correction import AnswerCorrectionRuntime, load_correction_config

    # 构建 agent 子入口命令行解析器。
    parser = build_agent_arg_parser()
    # 解析 agent 子入口参数。
    args = parser.parse_args(list(argv))
    # 读取业务大脑配置。
    business_config = load_business_brain_config(SQL_RAG_DIR)
    # 读取三层记忆配置。
    memory_config = load_memory_config()
    # 读取纠错飞轮配置。
    correction_config = load_correction_config()
    # 创建三层记忆运行时。
    memory_runtime = ThreeLayerMemoryRuntime(memory_config)
    # 确保长连接资源最终关闭。
    try:
        # 创建纠错飞轮运行时。
        correction_runtime = AnswerCorrectionRuntime(correction_config)
        # 创建 LangGraph + Qwen-Agent + LlamaIndex/Qdrant 业务大脑运行时。
        business_runtime = BusinessBrainRuntime(
            config=business_config,
            memory_runtime=memory_runtime,
            correction_runtime=correction_runtime,
            require_qwen=not args.qdrant_check_only,
        )
        # 只检查 Qdrant 消费链路时不调用 Qwen。
        if args.qdrant_check_only:
            # 调用 LlamaIndex + Qdrant 官方检索链路。
            result = business_runtime.qdrant_check(args.question)
        # 正常运行完整 RAG Agent。
        else:
            # 调用 LangGraph Agent Runtime。
            result = business_runtime.invoke(
                question=args.question,
                user_id=args.user_id,
                thread_id=args.thread_id,
            )
        # 打印 JSON 结果，便于命令行和自动化测试读取。
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # 返回成功退出码。
        return 0
    # 无论是否成功，都释放记忆层资源。
    finally:
        # 关闭三层记忆运行时。
        memory_runtime.close()


def main(argv: Sequence[str] | None = None) -> int:
    # 统一整理主入口参数。
    actual_argv = _normalize_main_argv(argv)
    # 如果请求模型服务部署辅助，就进入 module_config/model_service 汇总入口。
    if _is_model_service_request(actual_argv):
        # 去掉 model-service 子命令后交给模型服务入口解析。
        return run_model_service_runtime(actual_argv[1:])
    # 如果请求 Qwen3.5-2B 本机验证模型，就进入专用 GGUF/llama.cpp 入口。
    if _is_qwen35_2b_request(actual_argv):
        # 去掉 qwen35-2b 子命令后交给本机模型入口解析。
        return run_qwen35_2b_runtime(actual_argv[1:])
    # 如果请求业务脑 HTTP 服务，就进入商业级智能体服务入口。
    if _is_business_brain_service_request(actual_argv):
        # 去掉 business-brain-service 子命令后交给服务入口解析。
        return run_business_brain_service(actual_argv[1:])
    # 如果请求业务脑健康检查，就进入依赖检查入口。
    if _is_business_brain_health_request(actual_argv):
        # 去掉 business-brain-health 子命令后交给健康检查入口解析。
        return run_business_brain_health(actual_argv[1:])
    # 如果请求 MCP 工具网关，就进入 FastMCP 标准化工具入口。
    if _is_mcp_gateway_request(actual_argv):
        # 去掉 mcp-gateway 子命令后交给 MCP Gateway 入口解析。
        return run_mcp_gateway_runtime(actual_argv[1:])
    # 如果请求 RAG Agent，就按截图架构进入 Agent 汇总入口。
    if _is_agent_runtime_request(actual_argv):
        # 去掉 agent 子命令后交给 Agent 入口解析。
        return run_agent_runtime(actual_argv[1:])
    # 读取 SQL_RAG/.env，复用 SQL Server 2022 初始化配置。
    default_env = parse_env_file(SQL_RAG_DIR / ".env")
    # 构建命令行解析器，默认输出仍然落在 data_cleaning 目录。
    parser = build_arg_parser(default_env, DATA_CLEANING_DIR)
    # 解析命令行参数。
    args = parser.parse_args(actual_argv)
    # 创建 LlamaIndex 官方 embedding 模型实例。
    embed_model = build_llamaindex_embedding_model(args.vector_dim, args.vector_model)
    # 使用 LlamaIndex 官方 SimpleDirectoryReader 读取单个或多个 Markdown 文档。
    documents = load_markdown_documents(Path(args.input))
    # 使用项目适配器先做问题答案强相关成对，适配器内部调用 LlamaIndex pipeline/evaluator。
    qa_pair_nodes = pair_markdown_questions_answers(
        documents=documents,
        embed_model=embed_model,
        min_similarity=args.qa_similarity_threshold,
        max_answer_sentences=args.max_answer_sentences,
    )
    # 对已成对的问题答案执行 LlamaIndex 官方清洗。
    cleaned_nodes = clean_qa_pair_nodes_with_llamaindex(qa_pair_nodes)
    # 对清洗后的问答节点执行 LlamaIndex 官方语义分块。
    semantic_nodes = semantic_chunk_nodes_with_llamaindex(cleaned_nodes, embed_model, args.breakpoint_percentile)
    # 对语义节点执行 LlamaIndex 官方问答元数据提取。
    qa_nodes = extract_qa_metadata_with_llamaindex(semantic_nodes)
    # 给问答节点补齐文档内 RAG 聚类 metadata。
    clustered_nodes = assign_rag_clusters_with_llamaindex(qa_nodes)
    # 给问答节点补齐跨文档全局聚类 metadata。
    global_clustered_nodes = assign_global_clusters_with_llamaindex(clustered_nodes)
    # 对全局聚类后的节点执行 LlamaIndex 官方向量化。
    vectorized_nodes = vectorize_nodes_with_llamaindex(global_clustered_nodes, embed_model, args.vector_model)
    # 基于 LlamaIndex embedding 结果构建跨文档重复/近似融合关系。
    fusion_payloads = build_chunk_fusion_payloads_with_llamaindex(vectorized_nodes, args.fusion_similarity_threshold)
    # 把融合关系写回 LlamaIndex 节点 metadata。
    fused_nodes = apply_fusion_metadata_with_llamaindex(vectorized_nodes, fusion_payloads)
    # 构建文档内聚类摘要节点。
    cluster_nodes = build_cluster_summary_nodes_with_llamaindex(fused_nodes)
    # 构建跨文档全局聚类摘要节点。
    global_cluster_nodes = build_global_cluster_summary_nodes_with_llamaindex(fused_nodes)
    # 把 LlamaIndex TextNode 官方序列化结构整理成 chunk JSON payload。
    storage_payloads = llamaindex_nodes_to_storage_json(fused_nodes)
    # 把 LlamaIndex 聚类 TextNode 官方序列化结构整理成聚类 JSON payload。
    cluster_payloads = llamaindex_cluster_nodes_to_storage_json(cluster_nodes)
    # 把 LlamaIndex 全局聚类 TextNode 官方序列化结构整理成全局聚类 JSON payload。
    global_cluster_payloads = llamaindex_global_cluster_nodes_to_storage_json(global_cluster_nodes)
    # 从节点 metadata 构建实体提及和实体别名 payload。
    entity_mention_payloads, entity_alias_payloads = build_entity_relation_payloads(fused_nodes)
    # 2026-06-04 16:24:19 新增原因：构建 Neo4j 多跳三元组 payload，避免图谱只停留在 SQL mention 表。
    neo4j_triple_payloads = build_neo4j_triple_payloads(entity_mention_payloads, storage_payloads, fusion_payloads)
    # 构建问答校验问题 payload。
    validation_issue_payloads = build_validation_issue_payloads(fused_nodes)
    # 构建后续 RAG/向量库同步状态 payload。
    rag_sync_payloads = build_rag_sync_payloads(documents, fused_nodes)
    # 构建本次多文档摄取任务 ID。
    job_id = build_job_id(Path(args.input), documents)
    # 构建文档版本 payload。
    document_version_payloads = build_document_version_payloads(documents, job_id)
    # 构建本次摄取任务 payload。
    ingestion_job_payload = build_ingestion_job_payload(
        input_path=Path(args.input),
        job_id=job_id,
        args=args,
        documents=documents,
        chunks=fused_nodes,
        global_cluster_count=len(global_cluster_payloads),
        fusion_count=len(fusion_payloads),
        validation_issue_count=len(validation_issue_payloads),
    )
    # 汇总数据库写入 bundle，main 只组织调用关系，不堆入库临时逻辑。
    database_bundle = DatabaseWriteBundle(
        ingestion_job=ingestion_job_payload,
        documents=documents,
        document_versions=document_version_payloads,
        chunk_payloads=storage_payloads,
        document_cluster_payloads=cluster_payloads,
        global_cluster_payloads=global_cluster_payloads,
        entity_mention_payloads=entity_mention_payloads,
        entity_alias_payloads=entity_alias_payloads,
        fusion_payloads=fusion_payloads,
        validation_issue_payloads=validation_issue_payloads,
        rag_sync_payloads=rag_sync_payloads,
        neo4j_triple_payloads=neo4j_triple_payloads,
    )
    # 输出 JSON 和 JSONL 清洗结果。
    write_json_outputs(
        payloads=storage_payloads,
        output_json=Path(args.output_json).resolve() if args.output_json else None,
        output_jsonl=Path(args.output_jsonl).resolve() if args.output_jsonl else None,
    )
    # 把完整关系型 payload 写入指定数据库后端。
    db_message = save_records_to_database(args, database_bundle)
    # 汇总运行结果。
    summary = PipelineSummary(
        job_id=job_id,
        document_count=len(documents),
        document_ids=[document.node_id for document in documents],
        source_hashes=[str(document.metadata.get("source_hash", "")) for document in documents],
        sections=len({node.metadata.get("audio_no") for node in qa_pair_nodes}),
        qa_pairs=len(qa_pair_nodes),
        chunks=len(semantic_nodes),
        clusters=len(cluster_payloads),
        global_clusters=len(global_cluster_payloads),
        fusion_links=len(fusion_payloads),
        validation_issues=len(validation_issue_payloads),
        records=len(storage_payloads),
        output_json=str(Path(args.output_json).resolve()) if args.output_json else "",
        output_jsonl=str(Path(args.output_jsonl).resolve()) if args.output_jsonl else "",
        db_backend=args.db_backend,
        db_message=db_message,
    )
    # 打印 JSON 摘要，方便命令行、日志和自动化任务读取。
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    # 返回成功退出码。
    return 0


# 允许直接执行 python app/SQL_RAG/main.py。
if __name__ == "__main__":
    # 把 main 的退出码交给系统进程。
    raise SystemExit(main())
