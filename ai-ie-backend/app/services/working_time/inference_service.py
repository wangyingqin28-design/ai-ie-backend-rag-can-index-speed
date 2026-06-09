import asyncio
import json
import re
from typing import List, Dict, Any, AsyncGenerator
from fastapi import Request
from sqlalchemy.orm import Session
from loguru import logger

from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.services.working_price.bag_process_crud import XiangBaoGongXuCRUD
from app.utils.exceptions import NotFoundException, AppException


class InferenceService(BaseService):
    """工时推断服务 - 负责 AI 推断工时及批量更新"""

    BATCH_SIZE = 20
    SYSTEM_PROMPT = """你是一个专业的箱包IE工程师，根据工序名称和工种判断出工时（单位：秒）。
请严格按照以下 JSON 格式返回每个工序的工时，正常一道工序不多于10秒，不要添加任何额外说明：
[
    {"xbgxId": 工序ID1, "time": 工时1},
    {"xbgxId": 工序ID2, "time": 工时2},
    ...
]
如果某个工序无法确定工时，请将其 time 设置为 0 或省略该条目。"""

    async def working_time_for_AI_chat_async(self, question: str, request: Request, timeout: int = 60) -> str:
        """调用 LLM 获取工时推断结果（需根据你的实际 LLM 集成方式实现）"""
        # TODO: 替换为实际的 LLM 调用逻辑
        # 示例: 假设你有一个 LLMService
        from app.llm.llm_service import LLMService
        llm = LLMService()
        return await llm.complete(question, timeout=timeout)

    async def infer_and_update_times(self, xbkhId: int, request: Request, user_id: int) -> Dict[str, Any]:
        """非流式：推断工时并批量更新"""
        db = BaseService.get_db_session(request)
        try:
            gsId = get_gsId_by_userid(db, user_id)
            crud = XiangBaoGongXuCRUD()

            processes = crud.search(db=db, gsId=gsId, xbkhId=xbkhId)
            if not processes:
                raise NotFoundException(message=f"款号 {xbkhId} 下没有找到工序")

            all_updates = await self._infer_batches(db, processes)
            if not all_updates:
                raise AppException(message="没有有效的工时数据可更新")

            crud.batch_update_times(db=db, gsId=gsId, updates=all_updates, up_userid=user_id)
            db.commit()
            return {
                "message": "工时更新成功",
                "updated_count": len(all_updates),
                "total_processes": len(processes)
            }
        finally:
            db.close()

    async def infer_and_update_times_sse(self, xbkhId: int, request: Request, user_id: int) -> AsyncGenerator[str, None]:
        """SSE 流式推断工时"""
        db = BaseService.get_db_session(request)
        try:
            gsId = get_gsId_by_userid(db, user_id)
            crud = XiangBaoGongXuCRUD()

            processes = crud.search(db=db, gsId=gsId, xbkhId=xbkhId)
            if not processes:
                yield self._sse_event("error", {"message": f"款号 {xbkhId} 下没有找到工序"})
                return

            total = len(processes)
            total_batches = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            logger.info(f"款号 {xbkhId} 共 {total} 道工序，{total_batches} 个批次")

            yield self._sse_event("start", {
                "message": "开始推断工时",
                "total_processes": total,
                "total_batches": total_batches,
                "xbkhId": xbkhId
            })

            all_updates = []
            for batch_idx in range(total_batches):
                start = batch_idx * self.BATCH_SIZE
                end = min(start + self.BATCH_SIZE, total)
                batch_processes = processes[start:end]

                yield self._sse_event("batch_start", {
                    "batch": batch_idx + 1,
                    "total_batches": total_batches,
                    "batch_size": len(batch_processes),
                })

                # 构建 AI 问题
                lines = [f"工序ID: {p['xbgxId']}, 工序名称: {p['gongXuMingCheng']}, 工种: {p['GongZhong']}" for p in batch_processes]
                question = "请为以下工序推断工时（秒）：\n" + "\n".join(lines)

                ai_response = await self._call_ai_with_retry(batch_idx + 1, question, request)
                if ai_response is None:
                    return

                batch_updates = self._parse_ai_response(ai_response)
                if batch_updates is None:
                    return

                valid_ids = {p["xbgxId"] for p in batch_processes}
                batch_valid = []
                for item in batch_updates:
                    if item.get("xbgxId") in valid_ids and "time" in item:
                        try:
                            time_val = float(item["time"])
                            if time_val >= 0:
                                batch_valid.append({"xbgxId": item["xbgxId"], "time": time_val})
                        except (ValueError, TypeError):
                            continue
                all_updates.extend(batch_valid)

                yield self._sse_event("batch_end", {
                    "batch": batch_idx + 1,
                    "valid_updates": len(batch_valid),
                    "total_valid_so_far": len(all_updates)
                })
                await asyncio.sleep(0.05)

            if not all_updates:
                yield self._sse_event("error", {"message": "没有有效的工时数据可更新"})
                return

            yield self._sse_event("updating", {"message": "正在批量更新数据库...", "count": len(all_updates)})
            crud.batch_update_times(db=db, gsId=gsId, updates=all_updates, up_userid=user_id)
            db.commit()
            yield self._sse_event("complete", {
                "message": "工时更新成功",
                "updated_count": len(all_updates),
                "total_processes": total
            })

        except Exception as e:
            logger.exception(f"SSE 流程异常: {e}")
            yield self._sse_event("error", {"message": "服务内部错误", "details": str(e)})
        finally:
            db.close()

    async def _infer_batches(self, db: Session, processes: List[Dict]) -> List[Dict]:
        """分批调用 AI 并收集更新（非流式）"""
        all_updates = []
        total_batches = (len(processes) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
        for batch_idx in range(total_batches):
            start = batch_idx * self.BATCH_SIZE
            end = min(start + self.BATCH_SIZE, len(processes))
            batch_processes = processes[start:end]

            lines = [f"工序ID: {p['xbgxId']}, 工序名称: {p['gongXuMingCheng']}, 工种: {p['GongZhong']}" for p in batch_processes]
            question = "请为以下工序推断工时（秒）：\n" + "\n".join(lines)

            ai_response = await self._call_ai_with_retry(batch_idx + 1, question, None)
            if ai_response is None:
                continue

            batch_updates = self._parse_ai_response(ai_response)
            if batch_updates is None:
                continue

            valid_ids = {p["xbgxId"] for p in batch_processes}
            for item in batch_updates:
                if item.get("xbgxId") in valid_ids and "time" in item:
                    try:
                        time_val = float(item["time"])
                        if time_val >= 0:
                            all_updates.append({"xbgxId": item["xbgxId"], "time": time_val})
                    except (ValueError, TypeError):
                        continue
        return all_updates

    async def _call_ai_with_retry(self, batch_num: int, question: str, request: Request = None) -> str:
        """带重试的 AI 调用，返回响应文本，失败返回 None"""
        max_retries = 3
        for retry in range(max_retries):
            try:
                return await self.working_time_for_AI_chat_async(question, request, timeout=60)
            except Exception as e:
                if retry == max_retries - 1:
                    logger.error(f"批次 {batch_num} AI 调用最终失败: {e}")
                    return None
                logger.warning(f"批次 {batch_num} AI 调用失败，重试 {retry + 1}/{max_retries}")
                await asyncio.sleep(2 ** retry)
        return None

    def _parse_ai_response(self, ai_response: str) -> List[Dict] | None:
        """解析 AI 返回的 JSON，失败返回 None"""
        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
            json_str = json_match.group(1) if json_match else ai_response.strip()
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
            else:
                logger.error(f"AI 返回的不是列表: {data}")
                return None
        except Exception as e:
            logger.error(f"解析 AI 响应失败: {e}\n响应内容: {ai_response}")
            return None

    def _sse_event(self, event_type: str, data: dict) -> str:
        """构造 SSE 事件字符串"""
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"