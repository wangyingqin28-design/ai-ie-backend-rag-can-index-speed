

import json
import logging
from typing import Any, List
from app.index.base import BaseIndexer, IndexResult, IndexType
from app.llm.embed.base_embedding import get_collection_embedding_service_sync
from app.config import get_vector_db_connector, settings
from app.utils.utils import generate_vector_db_collection_name
from app.schemas.mssql_qdrant.constant import IndexAction
from llama_index.core.schema import BaseNode, TextNode
from uuid_extensions import uuid7
from app.config import get_sync_session



logger = logging.getLogger(__name__)


class VectorIndexer(BaseIndexer):
    """Vector index implementation"""

    def __init__(self):
        super().__init__(IndexType.VECTOR)

    def is_enabled(self, collection) -> bool:
        """Vector indexing is always enabled"""
        return True

    def create_index(self, document_id: str, doc_parts: dict[str, dict[IndexAction, list]], collection, **kwargs) -> IndexResult:
        """Create vector index for document"""

        try:
            from app.tasks.reconciler import index_reconciler
            # Get embedding model and vector store adaptor
            embedding_model, vector_size = get_collection_embedding_service_sync(collection)
            vector_store_adaptor = get_vector_db_connector(
                collection=generate_vector_db_collection_name(collection_id=collection.id)
            )
            
            nodes: List[BaseNode] = []
            for upsert_id,doc_index in doc_parts.items():
                # 缺了 document_id == doc_parts[upsert_id]的判断
                if upsert_id != document_id:
                    continue
                
                for doc in doc_index[IndexAction.CREATE]:
                    if doc.rule and doc.rule.strip():
                        metadata = {
                            "id": doc.id,
                            "yongHuId": doc.user_id,
                            "qiYeId": doc.enterprise_id,
                            "biaoZhunId": doc.standard_id,
                            "gengXinYongHuId": doc.update_user_id,
                            "xiangBaoGuiZeLeiXing": doc.rule_type,
                            "gengXinChaRuId": doc.upsert_id,
                            "wenDangId": doc.document_id,
                        }
                        # nodes.append(TextNode(id_=doc.id, text=doc.rule, metadata=metadata))
                        nodes.append(TextNode(id_=doc.id, text=doc.rule, metadata=metadata))
            
            # Generate embeddings for text chunks
            texts = [node.get_content() for node in nodes]
            vectors = embedding_model.embed_documents(texts, vector_size)
            # Assign embeddings to nodes
            for i in range(len(vectors)):
                nodes[i].embedding = vectors[i]

            logger.info(f"processed document with {len(doc_parts)} parts and {len(vectors)} chunks")   

            for session in get_sync_session():
                operations: dict[str, dict[IndexAction, list]] = index_reconciler.get_document_indexes_by_upsert_id(session, document_id)

                
                for upsert_id, operation in operations.items():
                    if upsert_id == document_id:
                        current_doc_parts = operation[IndexAction.CREATE]
                        input_doc_parts = doc_parts[document_id][IndexAction.CREATE]
                        if len(current_doc_parts) != len(input_doc_parts):
                            # 需要实现剔除发生变化的索引【待实现】
                            # logger.warning(f"Vector index creation failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent.")
                            # return IndexResult(
                            #     success=False, index_type=self.index_type, error=f"Vector index creation failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent."
                            # )

                            # 保留输入索引和现在索引中都存在的索引
                            current_doc_ids = [doc.id for doc in current_doc_parts]
                            input_doc_ids = [doc.id for doc in input_doc_parts]
                            # current_doc_ids和input_doc_ids的交集，保留这部分索引
                            common_doc_ids = set(current_doc_ids) & set(input_doc_ids)
                            # 创建要移除的元素列表，避免在遍历时修改列表
                            docs_to_remove_from_current = [doc for doc in current_doc_parts if doc.id not in common_doc_ids]
                            docs_to_remove_from_input = [doc for doc in input_doc_parts if doc.id not in common_doc_ids]
                            for doc in docs_to_remove_from_current:
                                operation[IndexAction.CREATE].remove(doc)
                            for doc in docs_to_remove_from_input:
                                doc_parts[document_id][IndexAction.CREATE].remove(doc)


                        current_doc_parts_to_dict = []
                        input_doc_parts_to_dict = []
                        for doc in operation[IndexAction.CREATE]:
                            current_doc_parts_to_dict.append(doc.to_dict())
                        for doc in doc_parts[document_id][IndexAction.CREATE]:
                            input_doc_parts_to_dict.append(doc.to_dict())
                        if json.dumps(current_doc_parts_to_dict) != json.dumps(input_doc_parts_to_dict):
                            logger.warning(f"Vector index creation failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent.")
                            return IndexResult(
                                success=False, index_type=self.index_type, error=f"Vector index creation failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent."
                            )

                        # Atomically claim indexes for a document by updating their state.
                        index_reconciler.claim_document_indexes(
                            session=session,
                            index_type=IndexAction.CREATE,
                            indexes_to_claim=current_doc_parts
                        )
                        

            # embeddings store in vector database
            ctx_ids = vector_store_adaptor.connector.store.add(nodes) 
            logger.info(f"Vector index created for document {document_id}: {len(ctx_ids)} vectors")

            for session in get_sync_session():
                index_reconciler.confirm_document_indexes(
                    session=session,
                    index_type=IndexAction.CREATE,
                    ctx_ids=ctx_ids,
                )

            return IndexResult(
                success=True,
                index_type=self.index_type,
                data={"context_ids": ctx_ids},
                metadata={
                    "vector_count": len(ctx_ids),
                    "vector_size": vector_size,
                },
            )            

        except Exception as e:
            logger.error(f"Vector index creation failed for document {document_id}: {str(e)}")

            # Store error messages in the DocumentIndex.
            index_reconciler.handle_failed_document_indexes(
                index_type=IndexAction.CREATE,
                upsert_id=document_id,
                error_message=str(e)
            )
            return IndexResult(
                success=False, index_type=self.index_type, error=f"Vector index creation failed: {str(e)}"
            )


    def update_index(self, document_id: str, doc_parts: dict[str, dict[IndexAction, list]], collection, **kwargs) -> IndexResult:
        """Update vector index for document"""
        try:
            from app.tasks.reconciler import index_reconciler
            # Get embedding model and vector store adaptor
            embedding_model, vector_size = get_collection_embedding_service_sync(collection)
            vector_store_adaptor = get_vector_db_connector(
                collection=generate_vector_db_collection_name(collection_id=collection.id)
            )

            nodes: List[BaseNode] = []
            old_ctx_ids = []
            for upsert_id,doc_index in doc_parts.items():
                # 缺了 document_id == doc_parts[upsert_id]的判断
                if upsert_id != document_id:
                    continue

                for doc in doc_index[IndexAction.UPDATE]:
                    if doc.rule and doc.rule.strip():
                        metadata = {
                            "id": doc.id,
                            "yongHuId": doc.user_id,
                            "qiYeId": doc.enterprise_id,
                            "biaoZhunId": doc.standard_id,
                            "gengXinYongHuId": doc.update_user_id,
                            "xiangBaoGuiZeLeiXing": doc.rule_type,                            
                            "gengXinChaRuId": doc.upsert_id,
                            "wenDangId": doc.document_id,
                        }
                        nodes.append(TextNode(id_=doc.id, text=doc.rule, metadata=metadata))
                        old_ctx_ids.append(doc.id)

            # Generate embeddings for text chunks
            texts = [node.get_content() for node in nodes]
            vectors = embedding_model.embed_documents(texts, vector_size)
            # Assign embeddings to nodes
            for i in range(len(vectors)):
                nodes[i].embedding = vectors[i]

            logger.info(f"processed document with {len(doc_parts)} parts and {len(vectors)} chunks") 

            # Delete old vectors
            if old_ctx_ids:
                vector_store_adaptor.connector.delete(ids=old_ctx_ids)
                logger.info(f"Deleted {len(old_ctx_ids)} old vectors for document {document_id}")  

            for session in get_sync_session():
                operations: dict[str, dict[IndexAction, list]] = index_reconciler.get_document_indexes_by_upsert_id(session, document_id)
                
                
                for upsert_id, operation in operations.items():
                    if upsert_id == document_id:
                        current_doc_parts = operation[IndexAction.UPDATE]
                        input_doc_parts = doc_parts[document_id][IndexAction.UPDATE]
                        if len(current_doc_parts) != len(input_doc_parts):
                            # 需要实现剔除发生变化的索引【待实现】
                            # logger.warning(f"Vector index update failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent.")
                            # return IndexResult(
                            #     success=False, index_type=self.index_type, error=f"Vector index update failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent."
                            # )


                            # 保留输入索引和现在索引中都存在的索引
                            current_doc_ids = [doc.id for doc in current_doc_parts]
                            input_doc_ids = [doc.id for doc in input_doc_parts]
                            # current_doc_ids和input_doc_ids的交集，保留这部分索引
                            common_doc_ids = set(current_doc_ids) & set(input_doc_ids)
                            # 创建要移除的元素列表，避免在遍历时修改列表
                            docs_to_remove_from_current = [doc for doc in current_doc_parts if doc.id not in common_doc_ids]
                            docs_to_remove_from_input = [doc for doc in input_doc_parts if doc.id not in common_doc_ids]
                            for doc in docs_to_remove_from_current:
                                operation[IndexAction.UPDATE].remove(doc)
                            for doc in docs_to_remove_from_input:
                                doc_parts[document_id][IndexAction.UPDATE].remove(doc)                            


                        current_doc_parts_to_dict = []
                        input_doc_parts_to_dict = []
                        for doc in operation[IndexAction.UPDATE]:
                            current_doc_parts_to_dict.append(doc.to_dict())
                        for doc in doc_parts[document_id][IndexAction.UPDATE]:
                            input_doc_parts_to_dict.append(doc.to_dict())
                        if json.dumps(current_doc_parts_to_dict) != json.dumps(input_doc_parts_to_dict):
                            logger.warning(f"Vector index update failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent.")
                            return IndexResult(
                                success=False, index_type=self.index_type, error=f"Vector index update failed for document {document_id}: After the embedding model generates vectors, the index data is inconsistent."
                            )

                        # Atomically claim indexes for a document by updating their state.
                        index_reconciler.claim_document_indexes(
                            session=session,
                            index_type=IndexAction.UPDATE,
                            indexes_to_claim=current_doc_parts
                        )


            # embeddings store in vector database
            ctx_ids = vector_store_adaptor.connector.store.add(nodes)
            logger.info(f"Vector index updated for document {document_id}: {len(ctx_ids)} vectors")

            for session in get_sync_session():
                index_reconciler.confirm_document_indexes(
                    session=session,
                    index_type=IndexAction.UPDATE,
                    ctx_ids=ctx_ids,
                )

            return IndexResult(
                success=True,
                index_type=self.index_type,
                data={"context_ids": ctx_ids},
                metadata={
                    "vector_count": len(ctx_ids),
                    "old_vector_count": len(old_ctx_ids),
                    "vector_size": vector_size,
                },
            )         

        except Exception as e:
            logger.error(f"Vector index update failed for document {document_id}: {str(e)}")

            # Store error messages in the DocumentIndex.
            index_reconciler.handle_failed_document_indexes(
                index_type=IndexAction.UPDATE,
                upsert_id=document_id,
                error_message=str(e)
            )            
            return IndexResult(success=False, index_type=self.index_type, error=f"Vector index update failed: {str(e)}")          

    def delete_index(self, document_id: str, doc_parts: dict, collection, **kwargs) -> IndexResult:
        """Delete vector index for document"""
        try:
            from app.tasks.reconciler import index_reconciler
            # Get vector store adaptor
            vector_store_adaptor = get_vector_db_connector(
                collection=generate_vector_db_collection_name(collection_id=collection.id)
            )

            ctx_ids = []
            for upsert_id,doc_index in doc_parts.items():
                for doc in doc_index[IndexAction.DELETE]:
                    ctx_ids.append(doc.id)     

            for session in get_sync_session():
                input_doc_parts = doc_parts[document_id][IndexAction.DELETE]

                index_reconciler.claim_document_indexes(
                    session=session,
                    index_type=IndexAction.DELETE,
                    indexes_to_claim=input_doc_parts,
                    ctx_ids=ctx_ids,
                )


            vector_store_adaptor.connector.delete(ids=ctx_ids)
            logger.info(f"Deleted {len(ctx_ids)} vectors for document {document_id}")
            
            for session in get_sync_session():
                index_reconciler.confirm_document_indexes(
                    session=session,
                    index_type=IndexAction.DELETE,
                    ctx_ids=ctx_ids,
                )
            
            return IndexResult(
                success=True,
                index_type=self.index_type,
                data={"deleted_context_ids": ctx_ids},
                metadata={"deleted_vector_count": len(ctx_ids)},
            )
        except Exception as e:
            logger.error(f"Vector index deletion failed for document {document_id}: {str(e)}")
            
            # Store error messages in the DocumentIndex.
            index_reconciler.handle_failed_document_indexes(
                index_type=IndexAction.DELETE,
                upsert_id=document_id,
                error_message=str(e)
            )
            return IndexResult(
                success=False, index_type=self.index_type, error=f"Vector index deletion failed: {str(e)}"
            )






# Global instance
vector_indexer = VectorIndexer()