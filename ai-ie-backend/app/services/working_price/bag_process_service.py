# app/services/system_manage/BiaoZhunGongXu_service.py
import asyncio
import json
import re
from typing import List, Dict, Any, AsyncGenerator

from fastapi import Request
from llama_index.core import Settings
from loguru import logger
from decimal import Decimal
from app.services.system_manage.GongSiGongJia_crud import GongSiGongJiaCRUD
from app.services.system_manage.QuYuGongJia_crud import QuYuGongJiaCRUD
from app.services.dxf.dxf_crud import query_aiXiangBaoKuanHao_by_xbkhId
from app.services.user.user_crud import get_gsId_by_userid
from app.services.working_price.bag_process_crud import XiangBaoGongXuCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.utils.exceptions import AppException, NotFoundException,ValidationException


class XiangBaoGongXuService(BaseService):
    """箱包工序服务类，包含 AI 推断工时功能"""

    # 系统提示词，用于指导 AI 返回 JSON 格式的工时数据
    SYSTEM_PROMPT = """你是一个专业的箱包IE工程师，根据工序名称和工种判断出工时（单位：秒）。
请严格按照以下 JSON 格式返回每个工序的工时，正常一道工序不多于10秒，不要添加任何额外说明：
[
    {"xbgxId": 工序ID1, "time": 工时1},
    {"xbgxId": 工序ID2, "time": 工时2},
    ...
]
如果某个工序无法确定工时，请将其 time 设置为 0 或省略该条目。"""

    # 分批大小，避免单次请求过大导致超时
    BATCH_SIZE = 20

    def get_bag_process(self, xbkhId: int, request: Request, userid: int) -> List[Dict[str, Any]]:
        """
        获取指定款号下的工序列表（不含工时，用于前端展示）
        """
        BaseService.mark_read_only(request)
        db = BaseService.get_db_session(request)
        gsId = get_gsId_by_userid(db, userid)
        crud = XiangBaoGongXuCRUD()
        return crud.search(db=db, xbkhId=xbkhId, gsId=gsId)

    async def working_time_for_AI_chat_async(self, question: str, request: Request, timeout: int = 60) -> str:
        """
        异步调用已配置的 LLM，并设置超时时间
        :param question: 用户问题
        :param request: FastAPI Request 对象（当前未使用，但保留以兼容）
        :param timeout: 超时时间（秒）
        :return: AI 返回的文本
        """
        full_prompt = f"{self.SYSTEM_PROMPT}\n用户问题：{question}"
        loop = asyncio.get_event_loop()
        try:
            # 使用 asyncio.wait_for 控制超时，在线程池中执行同步的 complete 方法
            response = await asyncio.wait_for(
                loop.run_in_executor(None, Settings.llm.complete, full_prompt),
                timeout=timeout
            )
            return response.text
        except asyncio.TimeoutError:
            raise AppException(code=500, message=f"AI 调用超时（{timeout} 秒）")
        except Exception as e:
            raise AppException(code=500, message="AI 调用失败", details={"error": str(e)})

    async def infer_and_update_times(self, xbkhId: int, request: Request, userid: int) -> Dict[str, Any]:
        """
        主流程：根据款号获取工序列表，分批调用 AI 推断工时，并批量更新到数据库
        :param xbkhId: 款号 ID
        :param request: FastAPI Request 对象
        :param userid: 当前用户 ID
        :return: 包含更新结果的字典
        """
        db = BaseService.get_db_session(request)
        gsId = get_gsId_by_userid(db, userid)
        crud = XiangBaoGongXuCRUD()

        # 1. 获取工序列表（不含工时）
        processes = crud.search(db=db, gsId=gsId, xbkhId=xbkhId)
        if not processes:
            raise NotFoundException(message=f"款号 {xbkhId} 下没有找到工序")

        logger.info(f"款号 {xbkhId} 共 {len(processes)} 道工序，开始分批推断工时")

        all_updates = []  # 存储所有批次的有效更新
        total_batches = (len(processes) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        for batch_idx in range(total_batches):
            start = batch_idx * self.BATCH_SIZE
            end = start + self.BATCH_SIZE
            batch_processes = processes[start:end]

            # 构建当前批次的 AI 问题
            lines = []
            for p in batch_processes:
                lines.append(f"工序ID: {p['xbgxId']}, 工序名称: {p['gongXuMingCheng']}, 工种: {p['GongZhong']}")
            question = "请为以下工序推断工时（秒）：\n" + "\n".join(lines)

            logger.debug(f"批次 {batch_idx + 1}/{total_batches}，工序数：{len(batch_processes)}")

            # 调用 AI（带重试机制）
            max_retries = 3
            ai_response = None
            for retry in range(max_retries):
                try:
                    ai_response = await self.working_time_for_AI_chat_async(question, request, timeout=60)
                    break
                except Exception as e:
                    if retry == max_retries - 1:
                        logger.error(f"批次 {batch_idx + 1} AI 调用失败，已重试 {max_retries} 次: {e}")
                        raise
                    logger.warning(f"批次 {batch_idx + 1} AI 调用失败，{retry + 1}/{max_retries} 重试中...")
                    await asyncio.sleep(2 ** retry)  # 指数退避

            # 解析 AI 返回的 JSON
            try:
                # 提取 JSON 内容（可能被包裹在 ```json ... ``` 中）
                json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = ai_response.strip()
                batch_updates = json.loads(json_str)
                if not isinstance(batch_updates, list):
                    raise AppException(code=500,message="AI 返回的不是列表",details={})
            except AppException:
                raise
            except Exception as e:
                logger.error(f"批次 {batch_idx + 1} AI 响应解析失败: {e}\n响应内容: {ai_response}")
                raise AppException(
                    code=500,
                    message=f"AI 返回格式解析失败（批次 {batch_idx + 1}）",
                    details={"error": str(e), "response": ai_response}
                )

            # 校验并收集有效的更新数据
            valid_ids = {p["xbgxId"] for p in batch_processes}
            for item in batch_updates:
                if "xbgxId" in item and "time" in item and item["xbgxId"] in valid_ids:
                    try:
                        time_val = float(item["time"])
                        if time_val >= 0:
                            all_updates.append({"xbgxId": item["xbgxId"], "time": time_val})
                    except (ValueError, TypeError):
                        continue

        if not all_updates:
            raise AppException(code=500, message="没有有效的工时数据可更新")

        logger.info(f"共收集到 {len(all_updates)} 条有效工时数据，开始批量更新")

        # 批量更新数据库
        crud.batch_update_times(db=db, gsId=gsId, updates=all_updates, up_userid=userid)

        return {
            "message": "工时更新成功",
            "updated_count": len(all_updates),
            "total_processes": len(processes)
        }

    async def calculate_and_update_gongjia(self, mode: int, xbkhId: int, request: Request, userid: int) -> Dict[
        str, Any]:
        db = BaseService.get_db_session(request)
        gsId = get_gsId_by_userid(db, userid)
        crud = XiangBaoGongXuCRUD()

        # 1. 根据模式获取地区编码或公司ID
        if mode == 0:
            try:
                # 调用 dxf_crud 的查询方法获取款号信息（含地区编码）
                kuanhao_resp = query_aiXiangBaoKuanHao_by_xbkhId(db, xbkhId)
                dqbmId = kuanhao_resp.dqbmId
                if not dqbmId:
                    logger.info(f"款号 {xbkhId} 的地区编码为空，无法查询区域工价")
                    raise ValidationException(message=f"该款号的地区编码为空，无法查询区域工价")
            except NotFoundException:
                logger.info(f"款号 {xbkhId} 不存在")
                raise NotFoundException(message=f"该款号不存在")
        else:
            dqbmId = None

        # 2. 获取该款号的所有工序（包含 xbgzId, time）
        processes = crud.get_processes_with_time(db=db, gsId=gsId, xbkhId=xbkhId)
        if not processes:
            logger.info(f"款号 {xbkhId} 下没有找到工序")
            raise NotFoundException(message=f"该款号下没有找到工序")

        # 3. 获取工价映射
        if mode == 0:
            qygjcrud=QuYuGongJiaCRUD()
            gongjia_map = qygjcrud.get_quyu_gongjia_map(db=db, dqbmId=dqbmId)
        else:
            # 使用 GongSiGongJiaCRUD.get_gongjia_map 替代 crud.get_gongsi_gongjia_map
            gongjia_map = GongSiGongJiaCRUD.get_gongjia_map(db, gsId)

        if not gongjia_map:
            logger.info(f"未找到任何工价数据（mode={mode}, dqbmId={dqbmId}, gsId={gsId})")
            raise AppException(code=500, message=f"未找到任何工价数据")

        # 4. 计算每个工序的总工价
        updates = []
        missing_gongjia = []
        missing_time = []
        for proc in processes:
            xbgxId = proc["xbgxId"]
            xbgzId = proc["xbgzId"]
            time = proc["time"]
            if time is None:
                missing_time.append(xbgxId)
                continue
            gongjia = gongjia_map.get(xbgzId)
            if gongjia is None:
                missing_gongjia.append({"xbgxId": xbgxId, "xbgzId": xbgzId})
                continue
            # 计算总工价：工时（秒） * 工价（元/秒）
            total = Decimal(str(time)) * (Decimal(str(gongjia))/30/86400)
            updates.append({"xbgxId": xbgxId, "gongJia": total})

        if missing_time:
            logger.warning(f"以下工序缺少工时: {missing_time}")
        if missing_gongjia:
            logger.warning(f"以下工序未找到对应工价: {missing_gongjia}")

        if not updates:
            raise AppException(code=500, message="没有有效的工价数据可更新", details={
                "missing_time": missing_time,
                "missing_gongjia": missing_gongjia
            })

        # 5. 批量更新工价
        crud.batch_update_gongjia(db=db, gsId=gsId, updates=updates, up_userid=userid,xbkhId=xbkhId)

        return {
            "message": "工价计算并更新成功",
            "updated_count": len(updates),
            "total_processes": len(processes),
            "missing_time": missing_time,
            "missing_gongjia": missing_gongjia
        }

    async def infer_and_update_times_sse(self, xbkhId: int, request: Request, userid: int) -> AsyncGenerator[str, None]:
        """
        SSE 流式版本：分批调用 AI 推断工时，实时推送进度。
        """
        # 获取数据库会话（注意：整个生成器期间会话保持打开，finally 中关闭）
        db = BaseService.get_db_session(request)
        try:
            gsId = get_gsId_by_userid(db, userid)
            crud = XiangBaoGongXuCRUD()

            # 1. 获取工序列表
            processes = crud.search(db=db, gsId=gsId, xbkhId=xbkhId)
            if not processes:
                yield self._sse_event("error", {"message": f"款号 {xbkhId} 下没有找到工序"})
                return

            total = len(processes)
            total_batches = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            logger.info(f"款号 {xbkhId} 共 {total} 道工序，{total_batches} 个批次")

            # 发送开始事件
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

                # 发送批次开始事件
                yield self._sse_event("batch_start", {
                    "batch_begining": batch_idx + 1,
                    "total_batches": total_batches,
                    "batch_size": len(batch_processes),
                })

                # 构建 AI 问题
                lines = []
                for p in batch_processes:
                    lines.append(f"工序ID: {p['xbgxId']}, 工序名称: {p['gongXuMingCheng']}, 工种: {p['GongZhong']}")
                question = "请为以下工序推断工时（秒）：\n" + "\n".join(lines)

                # 调用 AI（带重试）
                max_retries = 3
                ai_response = None
                for retry in range(max_retries):
                    try:
                        yield self._sse_event("ai_infer_start", {
                            "batch": batch_idx + 1,
                            "retry": retry + 1
                        })
                        await asyncio.sleep(0.05)
                        ai_response = await self.working_time_for_AI_chat_async(question, request, timeout=60)
                        yield self._sse_event("ai_infer_end", {
                            "batch": batch_idx + 1,
                            "response_length": len(ai_response)
                        })
                        await asyncio.sleep(0.05)
                        break
                    except Exception as e:
                        if retry == max_retries - 1:
                            logger.error(f"批次 {batch_idx + 1} AI 调用最终失败: {e}")
                            yield self._sse_event("error", {
                                "message": f"批次 {batch_idx + 1} AI 调用失败",
                                "batch": batch_idx + 1,
                                "details": str(e)
                            })
                            return
                        logger.warning(f"批次 {batch_idx + 1} AI 调用失败，重试 {retry + 1}/{max_retries}")
                        yield self._sse_event("ai_infer_retry", {
                            "batch": batch_idx + 1,
                            "retry": retry + 1,
                            "wait": 2 ** retry
                        })
                        await asyncio.sleep(2 ** retry)

                # 解析 AI 返回的 JSON
                try:
                    json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
                    json_str = json_match.group(1) if json_match else ai_response.strip()
                    batch_updates = json.loads(json_str)
                    if not isinstance(batch_updates, list):
                        raise ValueError("AI 返回的不是列表")
                except Exception as e:
                    logger.error(f"批次 {batch_idx + 1} AI 响应解析失败: {e}\n响应内容: {ai_response}")
                    yield self._sse_event("error", {
                        "message": f"批次 {batch_idx + 1} AI 返回格式解析失败",
                        "batch": batch_idx + 1,
                        "details": {"error": str(e), "response": ai_response}
                    })
                    await asyncio.sleep(0.05)
                    return

                # 校验并收集有效数据
                valid_ids = {p["xbgxId"] for p in batch_processes}
                batch_valid = []
                for item in batch_updates:
                    if "xbgxId" in item and "time" in item and item["xbgxId"] in valid_ids:
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
                await asyncio.sleep(0.05)
                return

            # 批量更新数据库
            yield self._sse_event("updating", {"message": "正在批量更新数据库...", "count": len(all_updates)})
            await asyncio.sleep(0.05)
            crud.batch_update_times(db=db, gsId=gsId, updates=all_updates, up_userid=userid)
            yield self._sse_event("complete", {
                "message": "工时更新成功",
                "updated_count": len(all_updates),
                "total_processes": total
            })
            await asyncio.sleep(0.05)

        except Exception as e:
            logger.exception(f"SSE 流程异常: {e}")
            yield self._sse_event("error", {"message": "服务内部错误", "details": str(e)})
            await asyncio.sleep(0.05)
        finally:
            db.flush()

    def _sse_event(self, event_type: str, data: dict) -> str:
        """
        构造 SSE 事件字符串
        """
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"