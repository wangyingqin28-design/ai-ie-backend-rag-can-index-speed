import os
import shutil
from enum import Enum
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from pathlib import Path as FilePath
from app.ai.vlmLI.processor import query_file, query_folder
from app.ai.vlmLI.run_query import get_question_by_prompt_type

app = FastAPI()

# ---------- 枚举定义 ----------
class TargetType(str, Enum):
    file = "file"
    folder = "folder"

class ProcessMode(str, Enum):
    auto = "auto"
    ocr = "ocr"
    recognize = "recognize"
    parse = "parse"

class PromptType(str, Enum):
    auto = "auto"
    ocr = "ocr"
    recognize = "recognize"
    audio = "audio"

# ---------- 文件夹预设映射 ----------
FOLDER_MAP = {
    "demo": "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data",
}
# 临时文件存储目录
UPLOAD_DIR = FilePath("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

async def save_upload_file(upload_file: UploadFile) -> str:
    """保存上传的文件到本地，返回文件绝对路径"""
    file_path = UPLOAD_DIR / upload_file.filename
    with open(file_path, "wb") as buffer:
        # 将上传文件内容写入本地文件
        shutil.copyfileobj(upload_file.file, buffer)
    return str(file_path.absolute())


@app.post("/query")
async def unified_query(
    target_type: TargetType = Query(..., description="目标类型：file 或 folder"),
    mode: ProcessMode = Query(ProcessMode.auto),
    prompt_type: PromptType = Query(None, description="不填则默认等于 mode"),
    use_default_prompt: bool = Query(True),
    custom_question: str | None = Query(None),
    similarity_top_k: int = Query(3, ge=1, le=10),
    recursive: bool = Query(True, description="仅文件夹有效"),
    # 文件相关
    file: UploadFile | None = File(None, description="上传文件（target_type=file 时必填）"),
    # 文件夹相关
    folder_name: str | None = Query(None, description="预置文件夹名（target_type=folder 时必填）"),
):
    # 1. 参数校验
    if target_type == TargetType.file and file is None:
        raise HTTPException(400, "target_type=file 时必须上传文件")
    if target_type == TargetType.folder and folder_name is None:
        raise HTTPException(400, "target_type=folder 时必须指定 folder_name")
    if target_type == TargetType.folder and folder_name not in FOLDER_MAP:
        raise HTTPException(400, f"未知文件夹: {folder_name}")

    # 2. 确定最终提示词类型和问题文本
    final_prompt_type = prompt_type.value if prompt_type else mode.value
    try:
        question = get_question_by_prompt_type(
            prompt_type=final_prompt_type,
            use_default_prompt=use_default_prompt,
            question=custom_question,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # 3. 处理文件或文件夹
    if target_type == TargetType.file:
        # 保存上传文件到临时目录
        file_path = await save_upload_file(file)
        try:
            result = await query_file(
                file_path=file_path,
                question=question,
                mode=mode.value,
                similarity_top_k=similarity_top_k,
            )
            return result
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    else:  # folder
        folder_path = FOLDER_MAP[folder_name]
        return await query_folder(
            folder_path=folder_path,
            question=question,
            mode=mode.value,
            recursive=recursive,
            similarity_top_k=similarity_top_k,
        )
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "vlm_router:app",          # 假设 FastAPI 实例定义在 api_server.py 中，变量名为 app
        host="0.0.0.0",
        port=8000,
        reload=True,               # 开发模式，代码改动自动重启
    )