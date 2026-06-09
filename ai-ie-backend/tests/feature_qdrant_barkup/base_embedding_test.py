

from app.schemas.mssql_qdrant.view_models import Collection
import json

collection = Collection(
    id="1",
    title="Test Collection",
    description="Test Collection Description",
    user="testuser",
    status="active",
    type="test",
    config='{"collection_id": "1","embedding": {"model_service_provider": "openai", "model": "text-embedding-ada-002", "custom_llm_provider": "openai"}}'
)

collection_id = getattr(collection, "id", "unknown")

print(collection_id)


model = '{"multimodal": false}'
model = json.loads(model)
multimodal = model.get("multimodal")
print(multimodal)

