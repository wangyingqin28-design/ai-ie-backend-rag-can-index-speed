

from .view_models import CollectionCreate, ModelSpec
from app.config import settings
import json
from app.schemas.mssql_qdrant.view_models import CollectionConfig

def generateCollectionCreate(collection_id: str) -> CollectionCreate:
    """Generate a CollectionCreate object with default config"""
    model_spec = ModelSpec(
        model=settings.embedding_model,
        model_service_provider=settings.embedding_model_service_provider,
        custom_llm_provider=settings.embedding_custom_llm_provider,
        dimensions=settings.embedding_dimensions,
    )
    config = CollectionConfig(embedding=model_spec).model_dump()
    config_str = json.dumps(config)
    return CollectionCreate(id=collection_id, config=config_str)

def parseCollectionConfig(config: str) -> CollectionConfig:
    try:
        config_dict = json.loads(config)
        collection_config = CollectionConfig.model_validate(config_dict)
        return collection_config
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON string: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse collection config: {str(e)}")


