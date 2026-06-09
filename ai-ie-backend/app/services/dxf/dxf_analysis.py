import datetime
import json
import os
import tempfile

import ezdxf
from fastapi import Request
from loguru import logger

from app.schemas.dxf.dxf_schemas import AIXiangBaoKuanHaoResponse, AIXiangBaoCaiPianResponse, AICaiPianGongYiResponse
from app.services.dxf import entities
from app.services.dxf.dxf_crud import save_aiXiangBaoKuanHao_with_aiXiangBaoCaiPian_pro
from app.utils.exceptions import AnalysisException
from app.utils.minio_utils import generate_caipian_presigned_url
from app.utils.redis.redis_sync_client import redis_sadd_sync, redis_expire_sync, redis_hmset_sync, redis_delete_sync, \
    redis_rpush_sync
from app.utils.redis.redis_utils import FILE_URL_DB, to_redis_str
from app.utils.snowflake_generator import SnowFlake


class DxfAnalysisService:


    """解析dxf函数"""
    def parse_dxf_entities(self,request: Request, file: bytes,file_name:str,in_userid: int, gsId: int, object_name_list:list, laiYuanLeiXing: int):


        # 创建临时文件（自动删除，二进制模式）
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.dxf', delete=False) as temp_f:
            temp_f.write(file)  # 把字节数据写入临时文件
            temp_path = temp_f.name  # 获取临时文件路径

        try:

            # 用readfile读取临时文件路径
            doc = ezdxf.readfile(temp_path)
            msp = doc.modelspace()
            blocks = doc.blocks
            data_list = []

            worker = SnowFlake()  # 雪花算法对象
            i = 1  # 这是裁片表数(排除纸格信息)
            j = 0  # 用来遍历object_name_list（存储着dxf转png生成的用来存入minio的所有裁片文件名）
            #k = '' #新增求dxf款号名称
            # 创建一个箱包款号对象
            aiXiangBaoKuanHao = AIXiangBaoKuanHaoResponse(
                xbkhId=worker.generate_id(),  # 箱包型号 (雪花算法)
                dxfURL=file_name,  # dxf文件路径
                laiYuanLeiXing=laiYuanLeiXing,  # 来源类型
                del_flag=False,  # 是否删除标识，0表示在用，1表示逻辑删除
                kuanHaoMingCheng=None,  # 产品款式编号
                banBenHao=None,  # 版本号
                xbbxId=None,  # 箱包包型id
                gsId=gsId,  # 归属企业ID
                dqbmId=None,  # 地区代码信息
                in_userid=in_userid,  # 插入人编号
                in_time=datetime.datetime.now().replace(microsecond=0),  # 插入时间
                caiPianLieBiao=[]  # 该纸格下的裁片列表
            )

            for entity in msp:
                # 获取实体类型
                entity_type = entity.dxftype()  # 这是识别实体的方法

                # 解析块引用
                if entity_type == "INSERT":
                    print(f"\n===== 块引用(INSERT) =====")
                    # 1. 获取 INSERT 实体自身的属性

                    block_name = entity.dxf.name  # 引用的块名
                    if i == 1 and len(data_list) > 0:  # i = 1 时，包含无效信息

                        insert_point = entity.dxf.insert  # 插入点坐标 (x, y, z)
                        xscale = entity.dxf.xscale  # X 方向缩放比例（默认 1.0）
                        yscale = entity.dxf.yscale  # Y 方向缩放比例（默认 1.0）
                        zscale = entity.dxf.zscale  # Z 方向缩放比例（默认 1.0）
                        rotation = entity.dxf.rotation  # 旋转角度（度，默认 0）

                        print(f"引用的块名: {block_name}")
                        print(f"插入点坐标: {insert_point}")  # 块的中心点
                        print(f"缩放比例: X={xscale}, Y={yscale}, Z={zscale}")
                        print(f"旋转角度: {rotation}°")

                    # 2. 根据块名查找对应的块定义
                    block = blocks.get(block_name)
                    if not block:
                        print(f"警告：未找到块定义 '{block_name}'")
                        continue

                    text_num = 1  # 判断裁片名裁片尺寸和工艺的参数，意思为子实体中的TEXT实体编号,裁片名裁片尺寸编号分别为1和2
                    for sub_entity in block:  # 识别块中的所有子实体  <<<<================

                        data = entities.dxf_entities(sub_entity)  # 用识别实体的方法，获取TEXT实体文本信息

                        if data != "":  # 非空则为获取到了TEXT实体

                            if text_num == 1:
                                piece_type = 0
                                if data == "Material":  # 匹配资料卡
                                    piece_type = 1
                                elif "正格" in data:  # 匹配正格
                                    piece_type = 2

                                # 封装裁片数据
                                aiXiangBaoCaiPian = AIXiangBaoCaiPianResponse(
                                    xbcpId=worker.generate_id(),  # 裁片唯一标识 (雪花算法)
                                    del_flag=False,  # 是否删除标识，0表示在用，1表示逻辑删除
                                    caiPianChiCun="",  # 裁片尺寸
                                    xbczId=None,  # 裁片材质ID#TODO
                                    caiPianHouDu=None,  # 裁片厚度#TODO
                                    gsId=gsId,  # 归属公司ID
                                    caiPianMingCheng=data[0],  # 裁片名称
                                    xbbwId=None,  # 裁片所属部位ID#TODO
                                    nanDuXiShu=1,  # 难度系数#TODO
                                    xbkhId=aiXiangBaoKuanHao.xbkhId,  # 纸格款号款号id
                                    caiPianLeiXing=piece_type,  # 裁片类型（0=料格/1=资料卡/2=正格/3=工艺格/4=其他）
                                    imgURL=object_name_list[j],  # 裁片图片路径
                                    in_userid=in_userid,  # 插入人编号
                                    in_time=datetime.datetime.now().replace(microsecond=0),  # 插入时间
                                    presigned_url=generate_caipian_presigned_url(object_name=object_name_list[j]),
                                    gongYiLieBiao=[]  # 该裁片下的工艺列表
                                )



                            elif text_num == 2:  # 编号为2时，data是裁片尺寸
                                #if aiXiangBaoCaiPian.caiPianChiCun == '':#新增求dxf款号名称
                                aiXiangBaoCaiPian.caiPianChiCun = data[0]  # 设置裁片尺寸
                                aiXiangBaoKuanHao.caiPianLieBiao.append(aiXiangBaoCaiPian)  # 将裁片对象加入纸格对象的裁片列表中

                                if aiXiangBaoCaiPian.caiPianMingCheng == "Material":  # 如果裁片名称为Material即代表是资料卡需要停止循环
                                    break
                                    # if "款号" in data[0]:#新增求dxf款号名称
                                    #     k = data[0]#新增求dxf款号名称
                                    #     continue#新增求dxf款号名称
                                    # elif "款号" in k:#新增求dxf款号名称
                                    #     aiXiangBaoKuanHao.kuanHaoMingCheng = data[0]#新增求dxf款号名称
                                    #     break#新增求dxf款号名称
                                    # else:#新增求dxf款号名称
                                    #     continue#新增求dxf款号名称

                            else:
                                # 封装工艺数据
                                aiCaiPianGongYi = AICaiPianGongYiResponse(
                                    cpgyId=worker.generate_id(),  # 工艺记录唯一标识 (雪花算法)
                                    del_flag=False,  # 是否删除标识，0表示在用，1表示逻辑删除
                                    gongYiMiaoShu=data[0],  # 工艺文本描述
                                    gongYiWeiZhi=data[1],  # 位置坐标
                                    xbcpId=aiXiangBaoCaiPian.xbcpId,  # 关联所属的裁片id
                                    gsId=gsId,  # 归属企业ID
                                    in_userid=in_userid,  # 插入人编号
                                    in_time=datetime.datetime.now().replace(microsecond=0),  # 插入时间

                                )
                                aiXiangBaoCaiPian.gongYiLieBiao.append(aiCaiPianGongYi)

                            text_num = text_num + 1

                    i = i + 1
                    j = j + 1
                # ============================子块遍历结束==============================
                else:

                    text = entities.dxf_entities(entity)  # 用识别实体的方法

                    text.append("不在裁片中，视为纸格信息")

                    if text != "":
                        # TODO
                        pass
            # 从request.state获取中间件创建的会话，无需自己创建
            db = request.state.db
            print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

            # 调用入库函数（传入中间件的会话）
            save_aiXiangBaoKuanHao_with_aiXiangBaoCaiPian_pro(db, aiXiangBaoKuanHao)

            # 注意：此处不再调用 db.commit()/rollback()/close()
            # 所有事务操作由中间件统一处理

            # ========== 重构后的缓存逻辑（和查询方法完全对齐） ==========
            try:
                # 1. 前置校验：确保纸格对象非空
                if not aiXiangBaoKuanHao:
                    logger.warning(
                        f"更新缓存失败：纸格响应对象为空 | xbkhId={aiXiangBaoKuanHao.xbkhId if hasattr(aiXiangBaoKuanHao, 'xbkhId') else '未知'}")
                else:
                    xbkhId = aiXiangBaoKuanHao.xbkhId

                    # 2. 组装纸格缓存数据（完全对齐 update_board_cache 的字段和处理规则）
                    board_data = {
                        "xbkhId": to_redis_str(aiXiangBaoKuanHao.xbkhId),
                        "dxfURL": to_redis_str(aiXiangBaoKuanHao.dxfURL),
                        "laiYuanLeiXing": to_redis_str(aiXiangBaoKuanHao.laiYuanLeiXing),
                        "del_flag": to_redis_str(aiXiangBaoKuanHao.del_flag),
                        "kuanHaoMingCheng": to_redis_str(aiXiangBaoKuanHao.kuanHaoMingCheng),
                        "banBenHao": to_redis_str(aiXiangBaoKuanHao.banBenHao),
                        "xbbxId": to_redis_str(aiXiangBaoKuanHao.xbbxId),
                        "gsId": to_redis_str(aiXiangBaoKuanHao.gsId),
                        "dqbmId": to_redis_str(aiXiangBaoKuanHao.dqbmId),
                        "del_time": to_redis_str(
                            aiXiangBaoKuanHao.del_time if hasattr(aiXiangBaoKuanHao, 'del_time') else None),
                        "in_userid": to_redis_str(aiXiangBaoKuanHao.in_userid),
                        "in_time": to_redis_str(aiXiangBaoKuanHao.in_time),
                        "up_time": to_redis_str(
                            aiXiangBaoKuanHao.up_time if hasattr(aiXiangBaoKuanHao, 'up_time') else None),
                        "up_userid": to_redis_str(
                            aiXiangBaoKuanHao.up_userid if hasattr(aiXiangBaoKuanHao, 'up_userid') else None),
                        "beiZhu": to_redis_str(
                            aiXiangBaoKuanHao.beiZhu if hasattr(aiXiangBaoKuanHao, 'beiZhu') else None),
                        "yongHuXingMing": to_redis_str(
                            aiXiangBaoKuanHao.yongHuXingMing if hasattr(aiXiangBaoKuanHao, 'yongHuXingMing') else None),
                        "baoXingMingCheng": to_redis_str(
                            aiXiangBaoKuanHao.baoXingMingCheng if hasattr(aiXiangBaoKuanHao,
                                                                          'baoXingMingCheng') else None),
                        # 完全对齐：用实际裁片列表长度，过滤空值但保留xbkhId
                        "total_pieces": to_redis_str(
                            len(aiXiangBaoKuanHao.caiPianLieBiao) if aiXiangBaoKuanHao.caiPianLieBiao else 0)
                    }
                    # 核心规则：过滤空值但强制保留xbkhId（和 update_board_cache 一致）
                    board_data = {k: v for k, v in board_data.items() if v != "" or k == "xbkhId"}

                    # 3. 组装裁片缓存数据（完全对齐 update_board_cache 的容错和Key规则）
                    pieces_data = {}
                    if aiXiangBaoKuanHao.caiPianLieBiao and len(aiXiangBaoKuanHao.caiPianLieBiao) > 0:
                        for idx, piece in enumerate(aiXiangBaoKuanHao.caiPianLieBiao):
                            logger.info(
                                f"开始处理第{idx + 1}个裁片 | xbcpId={piece.xbcpId} | 工艺列表类型={type(piece.gongYiLieBiao)} | 工艺列表值={piece.gongYiLieBiao}")
                            try:
                                # 3.1 组装工艺列表（无工艺则为空列表，不过滤）
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
                                            "up_userid": to_redis_str(
                                                gongyi.up_userid if hasattr(gongyi, 'up_userid') else None),
                                            "up_time": to_redis_str(
                                                gongyi.up_time if hasattr(gongyi, 'up_time') else None),
                                            "gongYiLeiXing": to_redis_str(
                                                gongyi.gongYiLeiXing if hasattr(gongyi, 'gongYiLeiXing') else None),
                                        })

                                # 3.2 组装裁片数据（完全对齐字段和容错规则）
                                piece_data = {
                                    "xbcpId": to_redis_str(piece.xbcpId),
                                    "del_flag": to_redis_str(piece.del_flag),
                                    "caiPianChiCun": to_redis_str(piece.caiPianChiCun),
                                    "xbczId": to_redis_str(piece.xbczId),
                                    "caiPianHouDu": to_redis_str(piece.caiPianHouDu),
                                    "gsId": to_redis_str(piece.gsId),
                                    "caiPianMingCheng": to_redis_str(piece.caiPianMingCheng),  # 保留名称字段（即使为空）
                                    "xbbwId": to_redis_str(piece.xbbwId),
                                    "nanDuXiShu": to_redis_str(piece.nanDuXiShu),
                                    "xbkhId": to_redis_str(piece.xbkhId),
                                    "caiPianLeiXing": to_redis_str(piece.caiPianLeiXing),
                                    "imgURL": to_redis_str(piece.imgURL),
                                    "presigned_url": to_redis_str(getattr(piece, 'presigned_url', '')),  # 兼容字段不存在
                                    "in_userid": to_redis_str(piece.in_userid),
                                    "in_time": to_redis_str(piece.in_time),
                                    "up_userid": to_redis_str(piece.up_userid if hasattr(piece, 'up_userid') else None),
                                    "up_time": to_redis_str(piece.up_time if hasattr(piece, 'up_time') else None),
                                    "gongYiLieBiao": gongyi_list  # 无工艺则为空列表（不删除字段）
                                }

                                # 核心规则：用xbcpId作为Key，即使名称为空也保留（和 update_board_cache 一致）
                                piece_key = str(piece.xbcpId)
                                pieces_data[piece_key] = json.dumps(piece_data, ensure_ascii=False)

                            except Exception as e:
                                logger.error(
                                    f"处理第{idx + 1}个裁片失败 | xbcpId={getattr(piece, 'xbcpId', '未知')} | error={str(e)}",
                                    exc_info=True)
                                continue

                    # 4. 写入Redis并设置过期时间（完全对齐 update_board_cache 的执行逻辑）
                    board_key = f"dxf:aiXiangBaoKuanHao:{xbkhId}"
                    pieces_key = f"dxf:pieces:{xbkhId}"

                    # 4.1 纸格数据：必写入（已过滤确保非空）
                    redis_hmset_sync(board_key, board_data, db=FILE_URL_DB)
                    redis_expire_sync(board_key, 170, db=FILE_URL_DB)

                    # 4.2 裁片数据：有数据才写入，无数据则跳过
                    if len(pieces_data) > 0:
                        redis_hmset_sync(pieces_key, pieces_data, db=FILE_URL_DB)
                        redis_expire_sync(pieces_key, 170, db=FILE_URL_DB)

                        # 4.3 裁片顺序列表：完全对齐 update_board_cache 的写入逻辑
                        pieces_order_key = f"dxf:pieces:order:{xbkhId}"
                        redis_delete_sync(pieces_order_key, db=FILE_URL_DB)  # 先清空旧数据
                        piece_ids = [str(piece.xbcpId) for piece in aiXiangBaoKuanHao.caiPianLieBiao if piece.xbcpId]
                        redis_rpush_sync(pieces_order_key, *piece_ids, db=FILE_URL_DB)
                        redis_expire_sync(pieces_order_key, 170, db=FILE_URL_DB)
                    else:
                        logger.info(f"纸格无裁片数据，跳过裁片缓存写入 | xbkhId={xbkhId}")

                    # 5. 日志输出：完全对齐 update_board_cache 的日志格式
                    actual_piece_count = len(
                        aiXiangBaoKuanHao.caiPianLieBiao) if aiXiangBaoKuanHao.caiPianLieBiao else 0
                    logger.info(
                        f"DXF解析数据更新到Redis缓存 | xbkhId={xbkhId} | 实际裁片数={actual_piece_count} | 缓存裁片数={len(pieces_data)}")

            except Exception as e:
                # 缓存失败不影响主流程，仅记录日志（和 update_board_cache 一致）
                logger.error(
                    f"DXF解析后更新纸格缓存失败 | xbkhId={aiXiangBaoKuanHao.xbkhId if hasattr(aiXiangBaoKuanHao, 'xbkhId') else '未知'} | error={str(e)}",
                    exc_info=True)

            return aiXiangBaoKuanHao

        except Exception as e:
            raise AnalysisException(
                message=f"DXF文件解析失败：{str(e)}",
                details={"error": str(e), "type": type(e).__name__}
            )

        finally:
            # 删除临时文件，避免残留
            if os.path.exists(temp_path):
                os.unlink(temp_path)


    def cache_presigned_urls_sync(self, aiXiangBaoKuanHao):
        """
        纯同步缓存预签名URL到Redis
        :param aiXiangBaoKuanHao: 解析后的纸格对象
        """
        # 1. 基础校验
        if not aiXiangBaoKuanHao.xbkhId:
            logger.warning("xbkhId为空，跳过预签名URL缓存")
            return

        # 2. 提取有效预签名URL
        valid_urls = []
        for caiPian in aiXiangBaoKuanHao.caiPianLieBiao:
            url = getattr(caiPian, 'presigned_url', '')
            if url and isinstance(url, str) and url.strip():
                valid_urls.append(url.strip())

        if not valid_urls:
            logger.info(f"xbkhId={aiXiangBaoKuanHao.xbkhId} 无有效预签名URL，跳过缓存")
            return

        # 3. 同步写入Redis（使用专用DB=4，与Token缓存隔离）
        redis_key = f"dxf:presigned_url:{aiXiangBaoKuanHao.xbkhId}"

        # 写入集合（自动去重）
        added_count = redis_sadd_sync(redis_key, *valid_urls, db=FILE_URL_DB)

        # 设置170秒过期（比MinIO URL有效期3分钟短10秒）
        expire_ok = redis_expire_sync(redis_key, 170, db=FILE_URL_DB)

        # 日志记录
        logger.info(
            f"Redis同步缓存详情 | "
            f"key={redis_key} | "
            f"新增URL数={added_count} | "
            f"过期设置={'成功' if expire_ok else '失败'} | "
            f"DB={FILE_URL_DB}"
        )