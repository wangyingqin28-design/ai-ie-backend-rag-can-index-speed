from app.tasks.collection import collection_task
from app.schemas.mssql_qdrant.utils import generateCollectionCreate
import json
from app.schemas.mssql_qdrant.view_models import ModelSpec
from app.schemas.mssql_qdrant.utils import parseCollectionConfig
import time

# model_spec = ModelSpec(
#     model_name="embedding",
#     model_version="1.0.0",
#     model_type="embedding",
#     model_provider="custom",
#     model_custom_llm_provider="openai",
# )
# config = json.dumps(model_spec.model_dump())
# config = {"embedding": config}
# config_str = json.dumps(config)
# print(config_str)
# config_dict = json.loads(config_str)
# print(config_dict)

start_time = time.time()
collection = generateCollectionCreate(collection_id="test")
config = parseCollectionConfig(collection.config)
print(config)
end_time = time.time()
print(f"Execution time: {(end_time - start_time) * 1000:.2f} ms")
collection_task._initialize_vector_databases(collection_id="AI_XiangBaoGuiZee", collection=collection)


