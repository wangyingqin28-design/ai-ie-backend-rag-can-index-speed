import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from fastapi import Request
from loguru import logger
from minio import Minio

from app.models.orm_models import AIXiangBaoKuanHao
from app.schemas.admin.admin_schemas import AdminPageRequest
from app.schemas.dxf.dxf_schemas import AIXiangBaoKuanHaoResponse, AIXiangBaoKuanHaoRequest, AIXiangBaoCaiPianRequest, \
    PageRequest, AICaiPianGongYiResponse, AIXiangBaoCaiPianResponse
from app.services.dxf.dxf_crud import query_aiXiangBaoKuanHao_by_gsId, create_aiXiangBaoKuanHao, \
    batch_logic_delete_aiXiangBaoKuanHao, update_aiXiangBaoKuanHao, update_aiXiangBaoCaiPian_and_aiCaiPianGongYi, \
    query_aiXiangBaoKuanHao_by_xbkhId, query_all_aiXiangBaoKuanHao, admin_batch_logic_delete_aiXiangBaoKuanHao
from app.utils.exceptions import AppException
from app.utils.minio_config import MinIOConfig
from app.utils.redis.redis_sync_client import redis_hgetall_sync, redis_hmset_sync, redis_expire_sync, \
    redis_delete_sync, redis_rpush_sync, redis_lrange_sync
from app.utils.redis.redis_utils import from_redis_str, to_redis_str, FILE_URL_DB
from app.utils.snowflake_generator import SnowFlake



class FileUploadService:
    def __init__(self):
        self.config = MinIOConfig.get_config()
        self.bucket_name = self.config["bucket"]
        self.minio_client = None
        # 2026-06-02 09:21:45 修改：MinIO 是 DXF 文件上传依赖，不应在服务启动时阻断 SQL_RAG/Qdrant 后端。
        try:
            self._init_minio_client()
        except Exception as exc:
            logger.warning(f"MinIO 初始化失败，DXF 文件上传接口将延迟到实际调用时再报错: {exc}")

    def _init_minio_client(self):
        """初始化 MinIO 客户端"""
        self.minio_client = Minio(
            self.config["endpoint"],
            access_key=self.config["access_key"],
            secret_key=self.config["secret_key"],
            secure=self.config["secure"]
        )
        # 确保桶存在
        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)

    def _ensure_minio_client(self):
        # 2026-06-02 09:21:45 修改：实际上传前检查 MinIO，避免启动阶段外部存储不可用导致整个后端退出。
        if self.minio_client is None:
            raise AppException(
                code=503,
                message="MinIO 文件服务当前不可用，请检查 MinIO endpoint 配置和服务状态",
                details={"endpoint": self.config.get("endpoint"), "bucket": self.bucket_name},
                status_code=503,
            )
        return self.minio_client

    def generate_safe_filename(self, in_userid, gsId,original_filename):
        """生成安全的文件名"""
        ext = Path(original_filename).suffix
        return f"user_{in_userid}_{uuid.uuid4().hex}{ext}"

    #用于单独上传dxf，不解析，此时默认laiYuanLeiXing（来源类型）为0
    def upload_file(self,request: Request, in_userid, gsId, file, file_name, content_type):
        """上传文件到 MinIO"""
        safe_filename = self.generate_safe_filename(in_userid, gsId,file_name)

        file_object = io.BytesIO(file)
        # 上传到 MinIO
        self._ensure_minio_client().put_object(
            bucket_name=self.bucket_name,
            object_name=file_name,
            data=file_object,
            length=len(file),
            content_type=content_type
        )

        db = request.state.db
        worker = SnowFlake()  # 雪花算法对象
        print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

        aiXiangBaoKuanHao = AIXiangBaoKuanHaoResponse(
            xbkhId=worker.generate_id(),  # 箱包型号 (雪花算法)
            dxfURL=file_name,  # dxf文件路径
            laiYuanLeiXing=0,  # 来源类型
            del_flag=False,  # 是否删除标识，0表示在用，1表示逻辑删除
            kuanHaoMingCheng="",  # 产品款式编号
            banBenHao="",  # 版本号#TODO
            xbbxId=0,  # 箱包包型id#TODO
            gsId=gsId,  # 归属企业ID
            dqbmId="",  # 地区代码信息#TODO
            in_userid=in_userid,  # 插入人编号
            in_time=datetime.now().replace(microsecond=0),  # 插入时间
        )

        #入库
        create_aiXiangBaoKuanHao(db,aiXiangBaoKuanHao)



    def get_file_url(self, safe_filename):
        """生成可访问的文件 URL"""
        return f"http://{self.config['endpoint']}/{self.bucket_name}/{safe_filename}"


    def get_aiXiangBaoKuanHao_by_gsId(self,request:Request,page_request: PageRequest,start_time: Optional[str] = None,end_time: Optional[str] = None):
        """
        根据企业ID分页查询DXF文件（纸格）列表
        业务逻辑：分页计算 → 调用Repo查询 → 数据结构化
        """
        try:
            # 1. 计算分页偏移量（业务逻辑）
            offset = (page_request.page - 1) * page_request.page_size

            # 从request.state获取中间件创建的会话，无需自己创建
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 2. 调用Repo层查询数据（纯数据库操作）
            total_count, aiXiangBaoKuanHao_list = query_aiXiangBaoKuanHao_by_gsId(
                db=db,
                gsId=page_request.gsId,
                offset=offset,
                limit=page_request.page_size,
                keyword=page_request.keyword,
                start_time=start_time,
                end_time=end_time
            )

            # 3. 计算总页数（业务逻辑）
            total_pages = (total_count + page_request.page_size - 1) // page_request.page_size if page_request.page_size > 0 else 0

            # 4. 结构化返回数据（业务逻辑：适配接口响应格式）
            data = {
                "items": aiXiangBaoKuanHao_list,#箱包款号对象列表
                "total": total_count,#总记录数
                "page": page_request.page,#当前页数
                "page_size": page_request.page_size,#每页记录数
                "total_pages": total_pages,#总页数
                "has_previous": page_request.page > 1,  # 是否有上一页，（前端用）
                "has_next": page_request.page < total_pages,  # 是否有下一页（前端用）
                #让前端能直观显示 “当前页展示的是第 X 条到第 Y 条数据”
                "start_index": (page_request.page - 1) * page_request.page_size + 1 if total_count > 0 else 0,  # 新增：当前页起始索引
                "end_index": min(page_request.page * page_request.page_size, total_count)  # 新增：当前页结束索引

            }
            return data

        except Exception as e:
            raise AppException(code=404,message=f"查询DXF文件列表失败: {str(e)}")

    #管理员用
    def get_all_aiXiangBaoKuanHao(self,request:Request,page_request: AdminPageRequest,start_time: Optional[str] = None,end_time: Optional[str] = None):
        """
        根分页查询所有DXF文件（纸格）列表
        业务逻辑：分页计算 → 调用Repo查询 → 数据结构化
        """
        try:
            # 1. 计算分页偏移量（业务逻辑）
            offset = (page_request.page - 1) * page_request.page_size

            # 从request.state获取中间件创建的会话，无需自己创建
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 2. 调用Repo层查询数据（纯数据库操作）
            total_count, aiXiangBaoKuanHao_list = query_all_aiXiangBaoKuanHao(
                db=db,
                offset=offset,
                limit=page_request.page_size,
                keyword=page_request.keyword,
                start_time=start_time,
                end_time=end_time
            )

            # 3. 计算总页数（业务逻辑）
            total_pages = (total_count + page_request.page_size - 1) // page_request.page_size if page_request.page_size > 0 else 0

            # 4. 结构化返回数据（业务逻辑：适配接口响应格式）
            data = {
                "items": aiXiangBaoKuanHao_list,#箱包款号对象列表
                "total": total_count,#总记录数
                "page": page_request.page,#当前页数
                "page_size": page_request.page_size,#每页记录数
                "total_pages": total_pages,#总页数
                "has_previous": page_request.page > 1,  # 是否有上一页，（前端用）
                "has_next": page_request.page < total_pages,  # 是否有下一页（前端用）
                #让前端能直观显示 “当前页展示的是第 X 条到第 Y 条数据”
                "start_index": (page_request.page - 1) * page_request.page_size + 1 if total_count > 0 else 0,  # 新增：当前页起始索引
                "end_index": min(page_request.page * page_request.page_size, total_count)  # 新增：当前页结束索引

            }
            return data

        except Exception as e:
            raise AppException(code=404,message=f"查询DXF文件列表失败: {str(e)}")


    def batch_delete_aiXiangBaoKuanHao(self, request: Request, del_userid: int, gsId: int, aiXiangBaoKuanHao_ids: list[int]):
        """
        批量逻辑删除纸格记录（DXF文件）
        :param request: 请求对象（用于获取数据库会话）
        :param del_userid: 操作人ID
        :param gsId: 企业ID（数据归属）
        :param aiXiangBaoKuanHao_ids: 要删除的纸格ID列表（xbkhId）
        :return: 成功删除的数量
        """
        try:
            # 1. 获取数据库会话
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 1. 业务逻辑校验（Service层职责）
            # 校验纸格是否属于当前企业
            exist_ids = db.query(AIXiangBaoKuanHao.xbkhId).filter(
                AIXiangBaoKuanHao.xbkhId.in_(aiXiangBaoKuanHao_ids),
                AIXiangBaoKuanHao.gsId == gsId
            ).all()
            exist_ids = [id[0] for id in exist_ids]
            if not exist_ids:
                raise AppException(code=400, message="无符合条件的纸格记录（ID不存在或不属于当前企业）")

            #调用逻辑删除
            delete_count = batch_logic_delete_aiXiangBaoKuanHao(db,gsId,aiXiangBaoKuanHao_ids,del_userid)

            return delete_count # 成功删除的数量

        except AppException as e:
            # 捕获自定义异常，直接抛出
            raise e
        except Exception as e:
            # 捕获其他异常，封装为自定义异常
            raise AppException(code=500, message=f"删除纸格记录失败: {str(e)}")

    #管理员批量删除
    def admin_batch_delete_aiXiangBaoKuanHao(self, request: Request, del_userid: int, aiXiangBaoKuanHao_ids: list[int]):
        """
        批量逻辑删除纸格记录（DXF文件）
        :param request: 请求对象（用于获取数据库会话）
        :param del_userid: 操作人ID
        :param aiXiangBaoKuanHao_ids: 要删除的纸格ID列表（xbkhId）
        :return: 成功删除的数量
        """
        try:
            # 1. 获取数据库会话
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 1. 业务逻辑校验（Service层职责）
            # 校验纸格是否存在
            exist_ids = db.query(AIXiangBaoKuanHao.xbkhId).filter(
                AIXiangBaoKuanHao.xbkhId.in_(aiXiangBaoKuanHao_ids),
            ).all()
            exist_ids = [id[0] for id in exist_ids]
            if not exist_ids:
                raise AppException(code=400, message="无符合条件的纸格记录（ID不存在）")

            #调用逻辑删除
            delete_count = admin_batch_logic_delete_aiXiangBaoKuanHao(db,aiXiangBaoKuanHao_ids,del_userid)

            return delete_count # 成功删除的数量

        except AppException as e:
            # 捕获自定义异常，直接抛出
            raise e
        except Exception as e:
            # 捕获其他异常，封装为自定义异常
            raise AppException(code=500, message=f"删除纸格记录失败: {str(e)}")



    def update_aiXiangBaoKuanHao(self, request: Request,aiXiangBaoKuanHaoRequest: AIXiangBaoKuanHaoRequest):
        """
        更新箱包款号信息
        :param request: 请求对象（用于获取数据库会话）
        :param aiXiangBaoKuanHaoRequest: 纸格信息请求对象
        """
        try:
            # 1. 获取数据库会话
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            #调用更新方法
            update_aiXiangBaoKuanHao(db,aiXiangBaoKuanHaoRequest)

        except AppException as e:
            # 捕获自定义异常，直接抛出
            raise e
        except Exception as e:
            # 捕获其他异常，封装为自定义异常
            raise AppException(code=500, message=f"更新箱包款号信息失败: {str(e)}")


    def update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(self, request: Request,aiXiangBaoCaiPianRequest: AIXiangBaoCaiPianRequest) -> Tuple[int, int]:
        """
        更新裁片信息 + 批量更新裁片工艺信息（仅裁片类型为料格时更新工艺）
        :param request: 请求对象（用于获取数据库会话）
        :param aiXiangBaoCaiPianRequest: 裁片信息请求对象
        :return: Tuple[int, int] - (裁片更新行数, 工艺更新总行数)
        """
        try:
            # 1. 获取数据库会话
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            #调用更新方法
            aiXiangBaoCaiPian_update_count, gongyi_update_total = update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(db,aiXiangBaoCaiPianRequest)

            #返回更新行数
            return aiXiangBaoCaiPian_update_count, gongyi_update_total

        except AppException as e:
            # 捕获自定义异常，直接抛出
            raise e
        except Exception as e:
            # 捕获其他异常，封装为自定义异常
            raise AppException(code=500, message=f"更新裁片信息及裁片工艺信息失败: {str(e)}")

    #TODO待替换成缓存版本
    def query_aiXiangBaoKuanHao_by_xbkhId(self, request: Request, xbkhId: int) -> AIXiangBaoKuanHaoResponse:
        """
        根据箱包款号id查询完整纸格信息
        :param request: 请求对象（用于获取数据库会话）
        :param xbkhId: 裁片信息请求对象
        :return: AIXiangBaoKuanHaoResponse - (完整箱包款号信息)
        """
        try:
            # 1. 获取数据库会话
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 调用查询方法
            aiXiangBaoKuanHaoResponse = query_aiXiangBaoKuanHao_by_xbkhId(db, xbkhId)


            # 返回完整纸格信息对象
            return aiXiangBaoKuanHaoResponse

        except AppException as e:
            # 捕获自定义异常，直接抛出
            raise e
        except Exception as e:
            # 捕获其他异常，封装为自定义异常
            raise AppException(code=500, message=f"获取纸格信息失败: {str(e)}")

    def query_aiXiangBaoKuanHao_by_xbkhId_with_cache(self, request: Request, xbkhId: int) -> AIXiangBaoKuanHaoResponse:
        """
        根据箱包款号id查询完整纸格信息（优先缓存，保证裁片顺序）
        :param request: 请求对象（用于获取数据库会话）
        :param xbkhId: 裁片信息请求对象
        :return: AIXiangBaoKuanHaoResponse - (完整箱包款号信息)
        """
        try:
            # ========== 第一步：优先查询Redis缓存 ==========
            board_key = f"dxf:aiXiangBaoKuanHao:{xbkhId}"
            pieces_key = f"dxf:pieces:{xbkhId}"
            # 新增：裁片顺序列表的Key
            pieces_order_key = f"dxf:pieces:order:{xbkhId}"

            # 1. 读取缓存数据
            board_data = redis_hgetall_sync(board_key, db=FILE_URL_DB)
            pieces_data = redis_hgetall_sync(pieces_key, db=FILE_URL_DB)
            # 新增：读取裁片顺序列表
            piece_order_list = redis_lrange_sync(pieces_order_key, 0, -1, db=FILE_URL_DB)  # 获取全部元素

            # 2. 缓存有效：解析并返回缓存数据
            if board_data and len(board_data) > 0:  # 调整判断条件：只要纸格数据存在就走缓存（裁片可能为空）
                logger.info(f"从Redis缓存获取纸格信息 | xbkhId={xbkhId}")

                # 解析纸格基础信息
                board_response = AIXiangBaoKuanHaoResponse(
                    xbkhId=from_redis_str(board_data.get("xbkhId"), int),
                    dxfURL=from_redis_str(board_data.get("dxfURL"), str),
                    laiYuanLeiXing=from_redis_str(board_data.get("laiYuanLeiXing"), int),
                    del_flag=from_redis_str(board_data.get("del_flag"), bool),
                    kuanHaoMingCheng=from_redis_str(board_data.get("kuanHaoMingCheng"), str),
                    banBenHao=from_redis_str(board_data.get("banBenHao"), str),
                    xbbxId=from_redis_str(board_data.get("xbbxId"), int),
                    gsId=from_redis_str(board_data.get("gsId"), int),
                    dqbmId=from_redis_str(board_data.get("dqbmId"), int),
                    del_time=from_redis_str(board_data.get("del_time"), int),
                    in_userid=from_redis_str(board_data.get("in_userid"), int),
                    in_time=from_redis_str(board_data.get("in_time"), str),
                    up_userid=from_redis_str(board_data.get("up_userid"), int),
                    up_time=from_redis_str(board_data.get("up_time"), str),
                    beiZhu=from_redis_str(board_data.get("beiZhu"), str),
                    yongHuXingMing=from_redis_str(board_data.get("yongHuXingMing"), str),
                    baoXingMingCheng=from_redis_str(board_data.get("baoXingMingCheng"), str),
                    caiPianLieBiao=[]  # 后续填充裁片数据
                )

                # 解析裁片和工艺数据（核心修改：按顺序列表读取）
                if piece_order_list and len(piece_order_list) > 0:
                    # 方案1：优先按顺序列表读取（保证原始顺序）
                    for piece_id in piece_order_list:
                        try:
                            # 从Hash中按xbcpId读取对应裁片数据
                            piece_json = pieces_data.get(piece_id)
                            if not piece_json:
                                logger.warning(f"裁片ID在顺序列表中但Hash无数据 | xbkhId={xbkhId} | xbcpId={piece_id}")
                                continue

                            # 解析裁片JSON数据
                            piece_dict = json.loads(piece_json)

                            # 解析工艺列表
                            gongyi_list = []
                            for gy in piece_dict.get("gongYiLieBiao", []):
                                gongyi = AICaiPianGongYiResponse(
                                    cpgyId=from_redis_str(gy.get("cpgyId"), int),
                                    del_flag=from_redis_str(gy.get("del_flag"), bool),
                                    gongYiMiaoShu=from_redis_str(gy.get("gongYiMiaoShu"), str),
                                    gongYiWeiZhi=from_redis_str(gy.get("gongYiWeiZhi"), str),
                                    xbcpId=from_redis_str(gy.get("xbcpId"), int),
                                    gsId=from_redis_str(gy.get("gsId"), int),
                                    in_userid=from_redis_str(gy.get("in_userid"), int),
                                    in_time=from_redis_str(gy.get("in_time"), str),
                                    up_time=from_redis_str(gy.get("up_time"), str),
                                    up_userid=from_redis_str(gy.get("up_userid"), int),
                                    gongYiLeiXing=from_redis_str(gy.get("gongYiLeiXing"), int),
                                )
                                gongyi_list.append(gongyi)

                            # 封装裁片对象
                            piece = AIXiangBaoCaiPianResponse(
                                xbcpId=from_redis_str(piece_dict.get("xbcpId"), int),
                                del_flag=from_redis_str(piece_dict.get("del_flag"), bool),
                                caiPianChiCun=from_redis_str(piece_dict.get("caiPianChiCun"), str),
                                xbczId=from_redis_str(piece_dict.get("xbczId"), int),
                                caiPianHouDu=from_redis_str(piece_dict.get("caiPianHouDu"), str),
                                gsId=from_redis_str(piece_dict.get("gsId"), int),
                                caiPianMingCheng=from_redis_str(piece_dict.get("caiPianMingCheng"), str),
                                xbbwId=from_redis_str(piece_dict.get("xbbwId"), int),
                                nanDuXiShu=from_redis_str(piece_dict.get("nanDuXiShu"), float),
                                xbkhId=from_redis_str(piece_dict.get("xbkhId"), int),
                                caiPianLeiXing=from_redis_str(piece_dict.get("caiPianLeiXing"), int),
                                imgURL=from_redis_str(piece_dict.get("imgURL"), str),
                                del_time=from_redis_str(piece_dict.get("del_time"), str),
                                presigned_url=from_redis_str(piece_dict.get("presigned_url"), str),
                                in_userid=from_redis_str(piece_dict.get("in_userid"), int),
                                in_time=from_redis_str(piece_dict.get("in_time"), str),
                                up_time=from_redis_str(piece_dict.get("up_time"), str),
                                up_userid=from_redis_str(piece_dict.get("up_userid"), int),
                                gongYiLieBiao=gongyi_list
                            )
                            board_response.caiPianLieBiao.append(piece)

                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"解析裁片缓存数据失败 | xbkhId={xbkhId} | piece_id={piece_id} | error={str(e)}")
                            continue
                else:
                    # 兼容方案：无顺序列表时，按原逻辑遍历（仅兜底）
                    logger.warning(f"未找到裁片顺序列表，使用无序遍历 | xbkhId={xbkhId}")
                    for piece_name, piece_json in pieces_data.items():
                        try:
                            piece_dict = json.loads(piece_json)
                            gongyi_list = []
                            for gy in piece_dict.get("gongYiLieBiao", []):
                                gongyi = AICaiPianGongYiResponse(
                                    cpgyId=from_redis_str(gy.get("cpgyId"), int),
                                    del_flag=from_redis_str(gy.get("del_flag"), bool),
                                    gongYiMiaoShu=from_redis_str(gy.get("gongYiMiaoShu"), str),
                                    gongYiWeiZhi=from_redis_str(gy.get("gongYiWeiZhi"), str),
                                    xbcpId=from_redis_str(gy.get("xbcpId"), int),
                                    gsId=from_redis_str(gy.get("gsId"), int),
                                    in_userid=from_redis_str(gy.get("in_userid"), int),
                                    in_time=from_redis_str(gy.get("in_time"), str)
                                )
                                gongyi_list.append(gongyi)
                            piece = AIXiangBaoCaiPianResponse(
                                xbcpId=from_redis_str(piece_dict.get("xbcpId"), int),
                                del_flag=from_redis_str(piece_dict.get("del_flag"), bool),
                                caiPianChiCun=from_redis_str(piece_dict.get("caiPianChiCun"), str),
                                xbczId=from_redis_str(piece_dict.get("xbczId"), int),
                                caiPianHouDu=from_redis_str(piece_dict.get("caiPianHouDu"), str),
                                gsId=from_redis_str(piece_dict.get("gsId"), int),
                                caiPianMingCheng=from_redis_str(piece_dict.get("caiPianMingCheng"), str),
                                xbbwId=from_redis_str(piece_dict.get("xbbwId"), int),
                                nanDuXiShu=from_redis_str(piece_dict.get("nanDuXiShu"), float),
                                xbkhId=from_redis_str(piece_dict.get("xbkhId"), int),
                                caiPianLeiXing=from_redis_str(piece_dict.get("caiPianLeiXing"), int),
                                imgURL=from_redis_str(piece_dict.get("imgURL"), str),
                                presigned_url=from_redis_str(piece_dict.get("presigned_url"), str),
                                in_userid=from_redis_str(piece_dict.get("in_userid"), int),
                                in_time=from_redis_str(piece_dict.get("in_time"), str),
                                gongYiLieBiao=gongyi_list
                            )
                            board_response.caiPianLieBiao.append(piece)
                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"解析裁片缓存数据失败 | xbkhId={xbkhId} | piece_name={piece_name} | error={str(e)}")
                            continue

                return board_response

            # ========== 第二步：缓存失效 → 查询数据库 ==========
            logger.info(f"Redis缓存失效，查询数据库 | xbkhId={xbkhId}")

            # 1. 获取数据库会话
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 2. 调用原查询方法
            aiXiangBaoKuanHaoResponse = query_aiXiangBaoKuanHao_by_xbkhId(db, xbkhId)

            print(aiXiangBaoKuanHaoResponse)

            # 3. 更新Redis缓存（数据库查询结果写入缓存）
            self.update_board_cache(xbkhId, aiXiangBaoKuanHaoResponse)

            # ========== 返回数据库查询结果 ==========
            return aiXiangBaoKuanHaoResponse

        except AppException as e:
            # 捕获自定义异常，直接抛出
            raise e
        except Exception as e:
            # 捕获其他异常，封装为自定义异常
            raise AppException(code=500, message=f"获取纸格信息失败: {str(e)}")

    def update_board_cache(self, xbkhId: int, board_response: AIXiangBaoKuanHaoResponse):
        """
        将数据库查询结果更新到Redis缓存（兼容裁片为空、裁片无工艺，修复裁片数少1问题）
        :param xbkhId: 纸格ID
        :param board_response: 完整的纸格响应对象
        """
        try:
            if not board_response:
                logger.warning(f"更新缓存失败：纸格响应对象为空 | xbkhId={xbkhId}")
                return

            # 1. 组装纸格缓存数据（强制保留核心字段，避免空字典）
            board_data = {
                "xbkhId": to_redis_str(board_response.xbkhId),
                "dxfURL": to_redis_str(board_response.dxfURL),
                "laiYuanLeiXing": to_redis_str(board_response.laiYuanLeiXing),
                "del_flag": to_redis_str(board_response.del_flag),
                "kuanHaoMingCheng": to_redis_str(board_response.kuanHaoMingCheng),
                "banBenHao": to_redis_str(board_response.banBenHao),
                "xbbxId": to_redis_str(board_response.xbbxId),
                "gsId": to_redis_str(board_response.gsId),
                "dqbmId": to_redis_str(board_response.dqbmId),
                "del_time": to_redis_str(board_response.del_time),
                "in_userid": to_redis_str(board_response.in_userid),
                "in_time": to_redis_str(board_response.in_time),
                "up_time": to_redis_str(board_response.up_time),
                "up_userid": to_redis_str(board_response.up_userid),
                "beiZhu": to_redis_str(board_response.beiZhu),
                "yongHuXingMing": to_redis_str(board_response.yongHuXingMing),
                "baoXingMingCheng": to_redis_str(board_response.baoXingMingCheng),
                # 修复：用实际裁片列表长度，而非缓存后的长度
                "total_pieces": to_redis_str(len(board_response.caiPianLieBiao) if board_response.caiPianLieBiao else 0)
            }
            # 过滤空值但强制保留xbkhId（确保board_data非空）
            board_data = {k: v for k, v in board_data.items() if v != "" or k == "xbkhId"}

            # 2. 组装裁片缓存数据（兼容裁片为空、裁片无工艺，修复Key重复问题）
            pieces_data = {}
            # 仅当裁片列表非空时才遍历处理
            if board_response.caiPianLieBiao and len(board_response.caiPianLieBiao) > 0:
                for idx, piece in enumerate(board_response.caiPianLieBiao):
                    logger.info(
                        f"开始处理第{idx + 1}个裁片 | xbcpId={piece.xbcpId} | 工艺列表类型={type(piece.gongYiLieBiao)} | 工艺列表值={piece.gongYiLieBiao}")
                    try:
                        # 组装工艺列表（无工艺则为空列表，正常保留）
                        gongyi_list = []
                        if piece.gongYiLieBiao and len(piece.gongYiLieBiao) > 0:
                            for gongyi in piece.gongYiLieBiao:
                                gongyi_list.append({
                                    "cpgyId": to_redis_str(gongyi.cpgyId),
                                    "del_flag": to_redis_str(gongyi.del_flag),
                                    "gongYiMiaoShu": to_redis_str(gongyi.gongYiMiaoShu),
                                    "gongYiWeiZhi": to_redis_str(gongyi.gongYiWeiZhi),
                                    "xbcpId": to_redis_str(gongyi.xbcpId),
                                    "gsId": to_redis_str(gongyi.gsId),
                                    "in_userid": to_redis_str(gongyi.in_userid),
                                    "in_time": to_redis_str(gongyi.in_time),
                                    "up_userid": to_redis_str(gongyi.up_userid),
                                    "up_time": to_redis_str(gongyi.up_time),
                                    "gongYiLeiXing": to_redis_str(gongyi.gongYiLeiXing),
                                })

                        # 组装裁片数据（保留空工艺列表）
                        piece_data = {
                            "xbcpId": to_redis_str(piece.xbcpId),
                            "del_flag": to_redis_str(piece.del_flag),
                            "caiPianChiCun": to_redis_str(piece.caiPianChiCun),
                            "xbczId": to_redis_str(piece.xbczId),
                            "caiPianHouDu": to_redis_str(piece.caiPianHouDu),
                            "gsId": to_redis_str(piece.gsId),
                            "caiPianMingCheng": to_redis_str(piece.caiPianMingCheng),  # 保留名称字段
                            "xbbwId": to_redis_str(piece.xbbwId),
                            "nanDuXiShu": to_redis_str(piece.nanDuXiShu),
                            "xbkhId": to_redis_str(piece.xbkhId),
                            "caiPianLeiXing": to_redis_str(piece.caiPianLeiXing),
                            "imgURL": to_redis_str(piece.imgURL),
                            "presigned_url": to_redis_str(getattr(piece, 'presigned_url', '')),
                            "in_userid": to_redis_str(piece.in_userid),
                            "in_time": to_redis_str(piece.in_time),
                            "up_userid": to_redis_str(piece.up_userid),
                            "up_time": to_redis_str(piece.up_time),
                            "gongYiLieBiao": gongyi_list  # 无工艺则为空列表
                        }

                        # 核心修复1：用xbcpId作为唯一Key，避免名称重复覆盖
                        # 格式：{xbcpId}（或加前缀：piece_{xbcpId}）
                        piece_key = str(piece.xbcpId)
                        # 核心修复2：移除名称非空过滤（即使名称为空，也用xbcpId作为Key保留裁片）
                        pieces_data[piece_key] = json.dumps(piece_data, ensure_ascii=False)

                    except Exception as e:
                        logger.error(
                            f"处理第{idx + 1}个裁片失败 | xbcpId={getattr(piece, 'xbcpId', '未知')} | error={str(e)}",
                            exc_info=True)
                        # 失败后继续循环，不中断
                        continue

            # 3. 写入Redis并设置过期时间（核心：仅当数据非空时调用hmset）
            board_key = f"dxf:aiXiangBaoKuanHao:{xbkhId}"
            pieces_key = f"dxf:pieces:{xbkhId}"

            # 纸格数据：必写入（已确保非空）
            redis_hmset_sync(board_key, board_data, db=FILE_URL_DB)
            redis_expire_sync(board_key, 170, db=FILE_URL_DB)

            # 裁片数据：有数据才写入，无数据则跳过（避免空mapping）
            if len(pieces_data) > 0:
                redis_hmset_sync(pieces_key, pieces_data, db=FILE_URL_DB)
                redis_expire_sync(pieces_key, 170, db=FILE_URL_DB)

                # ======================== 新增代码开始 ========================
                # 2. 新增：存储裁片ID的顺序列表（用List类型）
                pieces_order_key = f"dxf:pieces:order:{xbkhId}"
                # 先清空旧列表（避免脏数据）
                redis_delete_sync(pieces_order_key, db=FILE_URL_DB)
                # 按原始顺序写入裁片ID列表
                piece_ids = [str(piece.xbcpId) for piece in board_response.caiPianLieBiao if piece.xbcpId]
                redis_rpush_sync(pieces_order_key, *piece_ids, db=FILE_URL_DB)
                redis_expire_sync(pieces_order_key, 170, db=FILE_URL_DB)
                # ======================== 新增代码结束 ========================

            else:
                logger.info(f"纸格无裁片数据，跳过裁片缓存写入 | xbkhId={xbkhId}")

            # 修复：日志显示实际处理的裁片数（而非缓存后的长度）
            actual_piece_count = len(board_response.caiPianLieBiao) if board_response.caiPianLieBiao else 0
            logger.info(
                f"数据库数据更新到Redis缓存 | xbkhId={xbkhId} | 实际裁片数={actual_piece_count} | 缓存裁片数={len(pieces_data)}")

        except Exception as e:
            # 缓存更新失败不影响主流程，仅记录日志
            logger.error(f"更新纸格缓存失败 | xbkhId={xbkhId} | error={str(e)}", exc_info=True)



    def delete_board_cache(self, xbkhId: int):
        """
        删除纸格相关的所有缓存
        :param xbkhId: 纸格ID
        """
        try:
            board_key = f"dxf:aiXiangBaoKuanHao:{xbkhId}"
            pieces_key = f"dxf:pieces:{xbkhId}"

            # 直接删除
            board_del_count = redis_delete_sync(board_key, db=FILE_URL_DB)
            pieces_del_count = redis_delete_sync(pieces_key, db=FILE_URL_DB)

            # 日志
            if board_del_count + pieces_del_count > 0:
                logger.info(f"删除缓存成功 | xbkhId={xbkhId} | board={board_del_count} | pieces={pieces_del_count}")
            else:
                logger.debug(f"缓存已过期/不存在，无需删除 | xbkhId={xbkhId}")
        except Exception as e:
            logger.error(f"删除缓存失败 | xbkhId={xbkhId} | error={str(e)}", exc_info=True)
