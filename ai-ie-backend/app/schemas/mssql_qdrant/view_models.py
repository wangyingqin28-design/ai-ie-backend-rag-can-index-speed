


from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, EmailStr, Field, RootModel, confloat, conint, field_validator
from datetime import datetime
from app.models.models import DocumentIndexType


# models
class Collection(BaseModel):
    id: str = Field(..., description="Collection ID")
    title: Optional[str] = Field(None, description="Collection Title")
    description: Optional[str] = Field(None, description="Collection Description")
    user: Optional[str] = Field(None, description="Collection User")
    status: Optional[str] = Field(None, description="Collection Status")
    type: Optional[str] = Field(None, description="Collection Type")
    config: str = Field(..., description="Collection Config")

# view_models
class CollectionCreate(BaseModel):
    id: str = Field(..., description="Collection ID")
    config: str = Field(..., description="Collection Config")

class ModelSpec(BaseModel):
    model: Optional[str] = Field(
        None,
        description='The name of the language model to use',
        examples=['gpt-4o-mini'],
    )
    model_service_provider: Optional[str] = Field(
        None,
        description='Used for querying auth information (api_key/api_base/...) for a model service provider.',
        examples=['openai'],
    )
    custom_llm_provider: Optional[str] = Field(
        None,
        description="Used for Non-OpenAI LLMs (e.g. 'bedrock' for amazon.titan-tg1-large)",
        examples=['openai'],
    )
    temperature: Optional[confloat(ge=0.0, le=2.0)] = Field(
        0.1,
        description='Controls randomness in the output. Values between 0 and 2. Lower values make output more focused and deterministic',
        examples=[0.1],
    )
    max_tokens: Optional[conint(ge=1)] = Field(
        None, description='Maximum number of tokens to generate', examples=[4096]
    )
    max_completion_tokens: Optional[conint(ge=1)] = Field(
        None,
        description='Upper bound for generated completion tokens, including visible and reasoning tokens',
        examples=[4096],
    )
    timeout: Optional[conint(ge=1)] = Field(
        None, description='Maximum execution time in seconds for the API request'
    )
    top_n: Optional[conint(ge=1)] = Field(
        None, description='Number of top results to return when reranking documents'
    )
    tags: Optional[list[str]] = Field(
        [],
        description='Tags for model categorization',
        examples=[['free', 'recommend']],
    )
    dimensions: Optional[conint(ge=1)] = Field(
        None, description='Dimension of the embedding vector', examples=[1024]
    )

class CollectionConfig(BaseModel):
    embedding: Optional[ModelSpec] = None

class DocumentIndexResponse(BaseModel):
    id: str = Field(..., description="Document Index ID")
    user_id: int = Field(..., description="User ID")
    enterprise_id: Optional[int] = Field(None, description="Enterprise ID")
    standard_id: Optional[int] = Field(None, description="Standard ID")
    update_user_id: int = Field(..., description="Update User ID")
    rule_type: int = Field(..., description="Rule Type")
    rule: str = Field(..., description="Rule")
    status: str = Field(..., description="Status")
    gmt_created: str = Field(..., description="Created Time")
    gmt_updated: str = Field(..., description="Updated Time")
    gmt_deleted: Optional[str] = Field(None, description="Deleted Time")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def format_datetime(cls, v):
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return v


class DocumentCreateRequest(BaseModel):
    """创建文档索引请求"""
    user_id: int = Field(..., description="用户ID")
    rule_type: int = Field(..., description="规则类型")
    rules: list[str] = Field(..., description="规则列表")
    enterprise_id: Optional[int] = Field(None, description="企业ID")
    standard_id: Optional[int] = Field(None, description="标准ID")
    index_types: Optional[list[DocumentIndexType]] = Field(None, description="索引类型列表")


class DocumentUpdateRequest(BaseModel):
    """更新文档索引请求"""
    user_id: int = Field(..., description="用户ID")
    id_rule_dict: dict[str, str] = Field(..., description="文档ID和规则的映射字典")
    index_types: Optional[list[DocumentIndexType]] = Field(None, description="索引类型列表")


class DocumentDeleteRequest(BaseModel):
    """删除文档索引请求"""
    user_id: int = Field(..., description="用户ID")
    ids: list[str] = Field(..., description="文档ID列表")
    index_types: Optional[list[DocumentIndexType]] = Field(None, description="索引类型列表")


class RuleTypeResponse(BaseModel):
    """规则类型响应"""
    id: int = Field(..., description="规则类型ID")
    rule_type: str = Field(..., description="规则类型名称")

