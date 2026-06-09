from datetime import datetime
from typing import List, Tuple, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.models.orm_models import AIXiangBaoKuanHao, AIXiangBaoCaiPian, AICaiPianGongYi, AIXiangBaoBaoXing, \
    AIGongSiYongHu
from app.schemas.dxf.dxf_schemas import AIXiangBaoKuanHaoResponse, AIXiangBaoCaiPianResponse, AICaiPianGongYiResponse, \
    AIXiangBaoKuanHaoRequest, AIXiangBaoCaiPianRequest
from app.utils.exceptions import DataUpdateFailedException, NotFoundException
from app.utils.minio_utils import generate_caipian_presigned_url

def create_aiXiangBaoKuanHao(db: Session, aiXiangBaoKuanHao: AIXiangBaoKuanHaoResponse):
    """创建纸格记录"""

    #构建orm模型
    db_aiXiangBaoKuanHao = AIXiangBaoKuanHao(
        xbkhId = aiXiangBaoKuanHao.xbkhId,
        dxfURL = aiXiangBaoKuanHao.dxfURL,
        laiYuanLeiXing = aiXiangBaoKuanHao.laiYuanLeiXing,
        del_flag = aiXiangBaoKuanHao.del_flag,
        kuanHaoMingCheng = aiXiangBaoKuanHao.kuanHaoMingCheng,
        banBenHao = aiXiangBaoKuanHao.banBenHao,
        xbbxId = aiXiangBaoKuanHao.xbbxId,
        gsId = aiXiangBaoKuanHao.gsId,
        dqbmId = aiXiangBaoKuanHao.dqbmId,
        del_time = aiXiangBaoKuanHao.del_time,
        in_userid = aiXiangBaoKuanHao.in_userid,
        in_time = aiXiangBaoKuanHao.in_time,
        up_userid = aiXiangBaoKuanHao.up_userid,
        up_time = aiXiangBaoKuanHao.up_time,
    )
    db.add(db_aiXiangBaoKuanHao)



def create_aiXiangBaoCaiPian(db: Session, aiXiangBaoCaiPian: AIXiangBaoCaiPianResponse):
    """创建裁片记录"""

    # 构建orm模型
    db_aiXiangBaoCaiPian = AIXiangBaoCaiPian(
        xbcpId = aiXiangBaoCaiPian.xbcpId,
        del_flag = aiXiangBaoCaiPian.del_flag,
        caiPianChiCun = aiXiangBaoCaiPian.caiPianChiCun,
        xbczId = aiXiangBaoCaiPian.xbczId,
        caiPianHouDu = aiXiangBaoCaiPian.caiPianHouDu,
        gsId = aiXiangBaoCaiPian.gsId,
        caiPianMingCheng = aiXiangBaoCaiPian.caiPianMingCheng,
        xbbwId = aiXiangBaoCaiPian.xbbwId,
        nanDuXiShu = aiXiangBaoCaiPian.nanDuXiShu,
        xbkhId = aiXiangBaoCaiPian.xbkhId,
        caiPianLeiXing = aiXiangBaoCaiPian.caiPianLeiXing,
        imgURL = aiXiangBaoCaiPian.imgURL,
        del_time = aiXiangBaoCaiPian.del_time,
        in_userid = aiXiangBaoCaiPian.in_userid,
        in_time = aiXiangBaoCaiPian.in_time,
        up_userid = aiXiangBaoCaiPian.up_userid,
        up_time = aiXiangBaoCaiPian.up_time,

    )
    db.add(db_aiXiangBaoCaiPian)



def create_aiCaiPianGongYi(db: Session, aiCaiPianGongYi: AICaiPianGongYiResponse):
    """创建工艺记录，返回包含自增ID的Process对象"""

    # 构建orm模型
    db_aiCaiPianGongYi = AICaiPianGongYi(
        cpgyId = aiCaiPianGongYi.cpgyId,
        del_flag = aiCaiPianGongYi.del_flag,
        gongYiMiaoShu = aiCaiPianGongYi.gongYiMiaoShu,
        gongYiWeiZhi =  aiCaiPianGongYi.gongYiWeiZhi,
        xbcpId = aiCaiPianGongYi.xbcpId,
        gsId = aiCaiPianGongYi.gsId,
        del_time = aiCaiPianGongYi.del_time,
        in_userid = aiCaiPianGongYi.in_userid,
        in_time = aiCaiPianGongYi.in_time,
        up_userid = aiCaiPianGongYi.up_userid,
        up_time = aiCaiPianGongYi.up_time
    )

    db.add(db_aiCaiPianGongYi)


# ========== 批量创建裁片函数（解决N+1） ==========
def bulk_create_aiXiangBaoCaiPian(db: Session, aiXiangBaoCaiPian_list: List[AIXiangBaoCaiPianResponse]):
    """批量创建裁片记录（1条SQL插入所有裁片，解决N+1）"""
    # 批量转换响应体为ORM模型
    db_aiXiangBaoCaiPian_list = [
        AIXiangBaoCaiPian(
            xbcpId = item.xbcpId,
            del_flag = item.del_flag,
            caiPianChiCun = item.caiPianChiCun,
            xbczId = item.xbczId,
            caiPianHouDu = item.caiPianHouDu,
            gsId = item.gsId,
            caiPianMingCheng = item.caiPianMingCheng,
            xbbwId = item.xbbwId,
            nanDuXiShu = item.nanDuXiShu,
            xbkhId = item.xbkhId,
            caiPianLeiXing = item.caiPianLeiXing,
            imgURL = item.imgURL,
            del_time = item.del_time,
            in_userid = item.in_userid,
            in_time = item.in_time,
            up_userid = item.up_userid,
            up_time = item.up_time,
        )
        for item in aiXiangBaoCaiPian_list
    ]
    # 批量添加
    db.add_all(db_aiXiangBaoCaiPian_list)

# ========== 批量创建工艺函数（解决N+1） ==========
def bulk_create_aiCaiPianGongYi(db: Session, aiCaiPianGongYi_list: List[AICaiPianGongYiResponse]):
    """批量创建工艺记录（1条SQL插入所有工艺，解决N+1）"""
    db_aiCaiPianGongYi_list = [
        AICaiPianGongYi(
            cpgyId = item.cpgyId,
            del_flag = item.del_flag,
            gongYiMiaoShu = item.gongYiMiaoShu,
            gongYiWeiZhi =  item.gongYiWeiZhi,
            xbcpId = item.xbcpId,
            gsId = item.gsId,
            del_time = item.del_time,
            in_userid = item.in_userid,
            in_time = item.in_time,
            up_userid = item.up_userid,
            up_time = item.up_time
        )
        for item in aiCaiPianGongYi_list
    ]
    db.add_all(db_aiCaiPianGongYi_list)


def save_aiXiangBaoKuanHao_with_aiXiangBaoCaiPian_pro(db: Session, aiXiangBaoKuanHao: AIXiangBaoKuanHaoResponse)-> List[AIXiangBaoCaiPian]:
    """保存完整的纸格数据入库"""
    # ========== 1. 插入款号 ==========
    create_aiXiangBaoKuanHao(db, aiXiangBaoKuanHao)

    # ========== 2. 收集所有裁片+工艺数据 ==========
    cai_pian_batch_list = []  # 批量裁片数据
    gong_yi_batch_list = []   # 批量工艺数据

    for aiXiangBaoCaiPian in aiXiangBaoKuanHao.caiPianLieBiao:
        # 生成预签名URL
        #aiXiangBaoCaiPian.presigned_url = generate_caipian_presigned_url(object_name=aiXiangBaoCaiPian.imgURL)#已经转到服务层analysis文件中
        # 收集裁片数据（用于批量插入）
        cai_pian_batch_list.append(aiXiangBaoCaiPian)
        # 收集当前裁片的所有工艺数据
        gong_yi_batch_list.extend(aiXiangBaoCaiPian.gongYiLieBiao)

    # ========== 3. 批量插入裁片 ==========
    if cai_pian_batch_list:
        bulk_create_aiXiangBaoCaiPian(db, cai_pian_batch_list)

    # ========== 4. 批量插入工艺 ==========
    if gong_yi_batch_list:
        bulk_create_aiCaiPianGongYi(db, gong_yi_batch_list)

    # ========== 5. 刷新会话（适配中间件，提前校验并且分散压力） ==========
    db.flush()


    return aiXiangBaoKuanHao.caiPianLieBiao



def save_aiXiangBaoKuanHao_with_aiXiangBaoCaiPian(db: Session, aiXiangBaoKuanHao: AIXiangBaoKuanHaoResponse)-> List[AIXiangBaoCaiPian]:
    """保存完整的纸格数据入库"""
    # 1. 插入纸格
    create_aiXiangBaoKuanHao(db, aiXiangBaoKuanHao)

    # 2. 为每个裁片插入数据
    for aiXiangBaoCaiPian in aiXiangBaoKuanHao.caiPianLieBiao:
        create_aiXiangBaoCaiPian(db, aiXiangBaoCaiPian)

        #TODO预签名生成规则有待完善
        aiXiangBaoCaiPian.presigned_url = generate_caipian_presigned_url(object_name=aiXiangBaoCaiPian.imgURL)#【裁片场景专用】生成预签名URL（自动使用裁片桶 cutting_pieces_bucket）

        # 3. 为每个裁片的工艺插入数据
        for aiCaiPianGongYi in aiXiangBaoCaiPian.gongYiLieBiao:
            create_aiCaiPianGongYi(db, aiCaiPianGongYi)

    return aiXiangBaoKuanHao.caiPianLieBiao#返回所有的裁片



def query_aiXiangBaoKuanHao_by_gsId(db: Session,gsId: int,offset: int,limit: int,keyword:Optional[str] = None,start_time: Optional[datetime] = None,end_time: Optional[datetime] = None) -> Tuple[int, List[AIXiangBaoKuanHaoResponse]]:
    """
    根据企业ID分页查询DXF文件（纸格）列表
    :param db: 数据库会话
    :param gsId: 企业ID
    :param offset: 分页偏移量
    :param limit: 每页条数
    :param keyword: 模糊查询关键词
    :param start_time: 上传开始时间
    :param end_time: 上传结束时间
    :return: 总条数 + 分页数据列表
    """

    # 1. 构建基础查询：查询 AIXiangBaoKuanHao 实例
    query = db.query(
        AIXiangBaoKuanHao,  # 主表所有字段#TODO不应查询所有字段
        func.coalesce(AIXiangBaoBaoXing.baoXingMingCheng, "").label("baoXingMingCheng"),#查询关联表字段
        func.coalesce(AIGongSiYongHu.yongHuXingMing, "").label("yongHuXingMing")#查询关联表字段
    )

    # 2.构建查询条件
    query = query.filter(
        AIXiangBaoKuanHao.gsId == gsId,
        AIXiangBaoKuanHao.del_flag == False  # 过滤已删除数据
    )

    # 2. 新增：日期时间段筛选（in_time为上传时间）
    if start_time:
        query = query.filter(AIXiangBaoKuanHao.in_time >= start_time)
    if end_time:
        query = query.filter(AIXiangBaoKuanHao.in_time <= end_time)

    # 关联包型表和用户表（outerjoin）
    query = query.outerjoin(AIXiangBaoBaoXing, AIXiangBaoKuanHao.xbbxId == AIXiangBaoBaoXing.xbbxId)
    query = query.outerjoin(AIGongSiYongHu, AIXiangBaoKuanHao.in_userid == AIGongSiYongHu.gsyhId)

    # 3. 模糊查询（关键词匹配款号名称、版本号、DXF路径）
    if keyword and keyword.strip():
        keyword = f"%{keyword.strip()}%"  # SQL模糊查询通配符

        query = query.filter(
            or_(
                AIXiangBaoKuanHao.kuanHaoMingCheng.like(keyword),#款号名称
                AIXiangBaoKuanHao.banBenHao.like(keyword),#版本号
                AIXiangBaoKuanHao.dxfURL.like(keyword),#dxfurl
                AIXiangBaoKuanHao.beiZhu.like(keyword),#备注

                #outerjoin箱包包型表
                func.coalesce(AIXiangBaoBaoXing.baoXingMingCheng, "").like(keyword),
                #outerjoin公司用户表
                func.coalesce(AIGongSiYongHu.yongHuXingMing, "").like(keyword),
            )
        )

    # 基于主表主键去重计数
    total_count = query.with_entities(AIXiangBaoKuanHao.xbkhId).distinct().count()

    # 4. 分页查询数据（注意：必须有ORDER BY，MSSQL的强制要求）
    aiXiangBaoKuanHao_list = query.order_by(AIXiangBaoKuanHao.in_time.desc()) \
        .offset(offset) \
        .limit(limit) \
        .all()#注意：这里的aiXiangBaoKuanHao对象没有用户名称和包型名称的映射

    #手动构建用户名称和包型名称的映射
    aiXiangBaoKuanHaoResponse_list = []

    for item in aiXiangBaoKuanHao_list:
        main_obj, baoXingMingCheng, yongHuXingMing = item #一一对应上面的基础query
        response_obj = AIXiangBaoKuanHaoResponse.from_orm(main_obj)  # 扩展模型
        response_obj.baoXingMingCheng = baoXingMingCheng  # 赋值包型名称
        response_obj.yongHuXingMing = yongHuXingMing  # 赋值用户名
        aiXiangBaoKuanHaoResponse_list.append(response_obj)



    return total_count, aiXiangBaoKuanHaoResponse_list

#管理员用
def query_all_aiXiangBaoKuanHao(db: Session,offset: int,limit: int,keyword:Optional[str] = None,start_time: Optional[datetime] = None,end_time: Optional[datetime] = None) -> Tuple[int, List[AIXiangBaoKuanHaoResponse]]:
    """
    根据企业ID分页查询DXF文件（纸格）列表
    :param db: 数据库会话
    :param offset: 分页偏移量
    :param limit: 每页条数
    :param keyword: 模糊查询关键词
    :param start_time: 上传开始时间
    :param end_time: 上传结束时间
    :return: 总条数 + 分页数据列表
    """

    # 1. 构建基础查询：查询 AIXiangBaoKuanHao 实例
    query = db.query(
        AIXiangBaoKuanHao,  # 主表所有字段#TODO不应查询所有字段
        func.coalesce(AIXiangBaoBaoXing.baoXingMingCheng, "").label("baoXingMingCheng"),#查询关联表字段
        func.coalesce(AIGongSiYongHu.yongHuXingMing, "").label("yongHuXingMing")#查询关联表字段
    )

    # 2.构建查询条件
    query = query.filter(

        AIXiangBaoKuanHao.del_flag == False  # 过滤已删除数据
    )

    # 2. 新增：日期时间段筛选（in_time为上传时间）
    if start_time:
        query = query.filter(AIXiangBaoKuanHao.in_time >= start_time)
    if end_time:
        query = query.filter(AIXiangBaoKuanHao.in_time <= end_time)

    # 关联包型表和用户表（outerjoin）
    query = query.outerjoin(AIXiangBaoBaoXing, AIXiangBaoKuanHao.xbbxId == AIXiangBaoBaoXing.xbbxId)
    query = query.outerjoin(AIGongSiYongHu, AIXiangBaoKuanHao.in_userid == AIGongSiYongHu.gsyhId)

    # 3. 模糊查询（关键词匹配款号名称、版本号、DXF路径）
    if keyword and keyword.strip():
        keyword = f"%{keyword.strip()}%"  # SQL模糊查询通配符

        query = query.filter(
            or_(
                AIXiangBaoKuanHao.kuanHaoMingCheng.like(keyword),#款号名称
                AIXiangBaoKuanHao.banBenHao.like(keyword),#版本号
                AIXiangBaoKuanHao.dxfURL.like(keyword),#dxfurl
                AIXiangBaoKuanHao.beiZhu.like(keyword),#备注

                #outerjoin箱包包型表
                func.coalesce(AIXiangBaoBaoXing.baoXingMingCheng, "").like(keyword),
                #outerjoin公司用户表
                func.coalesce(AIGongSiYongHu.yongHuXingMing, "").like(keyword),
            )
        )

    # 基于主表主键去重计数
    total_count = query.with_entities(AIXiangBaoKuanHao.xbkhId).distinct().count()

    # 4. 分页查询数据（注意：必须有ORDER BY，MSSQL的强制要求）
    aiXiangBaoKuanHao_list = query.order_by(AIXiangBaoKuanHao.in_time.desc()) \
        .offset(offset) \
        .limit(limit) \
        .all()#注意：这里的aiXiangBaoKuanHao对象没有用户名称和包型名称的映射

    #手动构建用户名称和包型名称的映射
    aiXiangBaoKuanHaoResponse_list = []

    for item in aiXiangBaoKuanHao_list:
        main_obj, baoXingMingCheng, yongHuXingMing = item #一一对应上面的基础query
        response_obj = AIXiangBaoKuanHaoResponse.from_orm(main_obj)  # 扩展模型
        response_obj.baoXingMingCheng = baoXingMingCheng  # 赋值包型名称
        response_obj.yongHuXingMing = yongHuXingMing  # 赋值用户名
        aiXiangBaoKuanHaoResponse_list.append(response_obj)



    return total_count, aiXiangBaoKuanHaoResponse_list





def query_aiXiangBaoKuanHao_by_xbkhId(db: Session,xbkhId:int) -> AIXiangBaoKuanHaoResponse:
    """
    根据箱包款号ID查询单个DXF文件（纸格）信息
    :param db: 数据库会话
    :param xbkhId: 箱包款号ID
    :return: AIXiangBaoKuanHaoResponse - (完整箱包款号信息)
    """

    # aiXiangBaoKuanHao = db.query(AIXiangBaoKuanHao).filter(
    #     AIXiangBaoKuanHao.xbkhId == xbkhId,
    #     AIXiangBaoKuanHao.del_flag == False
    # ).first()

    query = db.query(
        AIXiangBaoKuanHao,
        func.coalesce(AIXiangBaoBaoXing.baoXingMingCheng, "").label("baoXingMingCheng"),
    )

    # 关联两张表（outerjoin，保证款号存在时，关联字段为空也能返回）
    query = query.outerjoin(AIXiangBaoBaoXing, AIXiangBaoKuanHao.xbbxId == AIXiangBaoBaoXing.xbbxId)

    # 过滤条件
    query = query.filter(
        AIXiangBaoKuanHao.xbkhId == xbkhId,
        AIXiangBaoKuanHao.del_flag == False
    )

    # 获取结果
    query_result = query.first()

    # 拆分结果：款号实例 + 包型名称 + 上传人名称
    aiXiangBaoKuanHao, baoXingMingCheng = query_result

    # 款号不存在则抛异常
    if not query_result:
        raise NotFoundException(
            message=f"查询款号信息失败：未找到款号ID={xbkhId}的有效记录",
            details={"xbkhId": xbkhId, "filter_conditions": "del_flag=False"}
        )

    # ========== 查询该款号下的所有裁片 ==========
    aiXiangBaoCaiPian_list = db.query(AIXiangBaoCaiPian).filter(
        AIXiangBaoCaiPian.xbkhId == xbkhId,  # 关联款号ID
        AIXiangBaoCaiPian.del_flag == False
    ).all()

    # ========== 批量查询工艺（解决N+1问题） ==========
    # 提取所有有效裁片ID（空值防护）
    valid_xbcpIds = [
        aiXiangBaoCaiPian.xbcpId for aiXiangBaoCaiPian in aiXiangBaoCaiPian_list
        if aiXiangBaoCaiPian.xbcpId and isinstance(aiXiangBaoCaiPian.xbcpId, int)
    ]

    # 根据所有有效裁片ID批量查询所有工艺（仅1次SQL）
    aiCaiPianGongYi_all = []
    if valid_xbcpIds:
        aiCaiPianGongYi_all = db.query(AICaiPianGongYi).filter(
            AICaiPianGongYi.xbcpId.in_(valid_xbcpIds),
            AICaiPianGongYi.del_flag == False
        ).all()

    # 构建裁片ID到工艺列表的映射字典
    xbcpId_to_gongyi = {}
    for aiCaiPianGongYi in aiCaiPianGongYi_all:
        if aiCaiPianGongYi.xbcpId not in xbcpId_to_gongyi:
            xbcpId_to_gongyi[aiCaiPianGongYi.xbcpId] = []
        xbcpId_to_gongyi[aiCaiPianGongYi.xbcpId].append(aiCaiPianGongYi)#加入字典

    # ========== 组装嵌套数据 ==========
    aiXiangBaoCaiPianResponse_list: List[AIXiangBaoCaiPianResponse] = []#声明裁片response列表

    for aiXiangBaoCaiPian in aiXiangBaoCaiPian_list:#遍历orm裁片列表
        # 从映射字典取工艺（不需要多层for循环查询数据库）
        aiCaiPianGongYi_list = xbcpId_to_gongyi.get(aiXiangBaoCaiPian.xbcpId, [])

        # 转换工艺列表为响应体
        AICaiPianGongYiResponse_list = [
            AICaiPianGongYiResponse.model_validate(aiCaiPianGongYi)
            for aiCaiPianGongYi in aiCaiPianGongYi_list
        ]

        #TODO预签名生成规则有待完善
        aiXiangBaoCaiPian.presigned_url = generate_caipian_presigned_url(object_name=aiXiangBaoCaiPian.imgURL)  # 【裁片场景专用】生成预签名URL（自动使用裁片桶 cutting_pieces_bucket）

        # 转换裁片为响应体，并嵌套工艺列表
        aiXiangBaoCaiPianResponse = AIXiangBaoCaiPianResponse.model_validate(aiXiangBaoCaiPian)#裁片orm转换
        aiXiangBaoCaiPianResponse.gongYiLieBiao = AICaiPianGongYiResponse_list#为所有的裁片赋值工艺列表
        aiXiangBaoCaiPianResponse_list.append(aiXiangBaoCaiPianResponse)#将所有裁片插入裁片response列表

    # ========== 组装最终的款号响应体==========
    aiXiangBaoKuanHaoResponse = AIXiangBaoKuanHaoResponse.model_validate(aiXiangBaoKuanHao)#款号orm转换
    aiXiangBaoKuanHaoResponse.baoXingMingCheng= baoXingMingCheng#为款号赋值包型名称
    aiXiangBaoKuanHaoResponse.caiPianLieBiao = aiXiangBaoCaiPianResponse_list#为款号赋值裁片列表

    # ========== 返回响应体 ==========
    return aiXiangBaoKuanHaoResponse


def batch_logic_delete_aiXiangBaoKuanHao(db: Session,gsId: int,aiXiangBaoKuanHao_ids: list[int],del_userid: int) -> int:
    """
    批量逻辑删除纸格记录（数据访问层核心方法）
    :param db: 数据库会话
    :param gsId: 企业ID（数据隔离，仅删除当前企业数据）
    :param aiXiangBaoKuanHao_ids: 要删除的纸格ID列表
    :param del_userid: 操作人ID
    :return: 删除数量
    """

    # 定义通用的更新字段（避免重复代码）
    delete_update_fields = {
        "del_flag": True,
        "del_time": datetime.now().replace(microsecond=0),
        "up_userid": del_userid,
        "up_time": datetime.now().replace(microsecond=0),
    }

    # 执行批量逻辑删除（仅更新字段，不物理删除）
    aiXiangBaoCaiPian_delete_count = db.query(AIXiangBaoKuanHao).filter(
        AIXiangBaoKuanHao.xbkhId.in_(aiXiangBaoKuanHao_ids), # 批量匹配ID
        AIXiangBaoKuanHao.gsId == gsId, # 仅删除当前企业的数据（数据隔离）
        AIXiangBaoKuanHao.del_flag == False # 仅删除未被删除的记录
    ).update(
        # {
        #     AIXiangBaoKuanHao.del_flag: True,# 标记为已删除
        #     AIXiangBaoKuanHao.del_time: datetime.now().replace(microsecond=0),# 删除时间
        #     AIXiangBaoKuanHao.up_userid: del_userid,#更新人id
        #     AIXiangBaoKuanHao.up_time: datetime.now().replace(microsecond=0),# 更新时间
        # },
        delete_update_fields,
        synchronize_session=False  # 提升批量更新性能
    )

    # 2. 查询当前企业下，关联这些纸格ID的所有未删除裁片ID
    if aiXiangBaoCaiPian_delete_count > 0:
        cp_ids = db.query(AIXiangBaoCaiPian.xbcpId).filter(
            AIXiangBaoCaiPian.xbkhId.in_(aiXiangBaoKuanHao_ids),
            AIXiangBaoCaiPian.gsId == gsId,
            AIXiangBaoCaiPian.del_flag == False
        ).all()
        # 提取裁片ID列表（转换为[int]格式）
        cp_id_list = [cp_id[0] for cp_id in cp_ids] if cp_ids else []

        # 3. 批量逻辑删除裁片记录
        if cp_id_list:
            cp_delete_count = db.query(AIXiangBaoCaiPian).filter(
                AIXiangBaoCaiPian.xbcpId.in_(cp_id_list),
                AIXiangBaoCaiPian.gsId == gsId,
                AIXiangBaoCaiPian.del_flag == False
            ).update(
                delete_update_fields,
                synchronize_session=False
            )

            # 4. 查询当前企业下，关联这些裁片ID的所有未删除工艺记录ID
            craft_ids = db.query(AICaiPianGongYi.cpgyId).filter(  # 请替换为工艺表的主键字段
                AICaiPianGongYi.xbcpId.in_(cp_id_list),
                AICaiPianGongYi.gsId == gsId,
                AICaiPianGongYi.del_flag == False
            ).all()
            # 提取工艺ID列表
            craft_id_list = [craft_id[0] for craft_id in craft_ids] if craft_ids else []

            # 5. 批量逻辑删除工艺记录
            if craft_id_list:
                db.query(AICaiPianGongYi).filter(
                    AICaiPianGongYi.cpgyId.in_(craft_id_list),  # 请替换为工艺表的主键字段
                    AICaiPianGongYi.gsId == gsId,
                    AICaiPianGongYi.del_flag == False
                ).update(
                    delete_update_fields,
                    synchronize_session=False
                )


    return aiXiangBaoCaiPian_delete_count


def admin_batch_logic_delete_aiXiangBaoKuanHao(db: Session,aiXiangBaoKuanHao_ids: list[int],del_userid: int) -> int:
    """
    批量逻辑删除纸格记录（数据访问层核心方法）
    :param db: 数据库会话
    :param aiXiangBaoKuanHao_ids: 要删除的纸格ID列表
    :param del_userid: 操作人ID
    :return: 删除数量
    """

    # 定义通用的更新字段（避免重复代码）
    delete_update_fields = {
        "del_flag": True,
        "del_time": datetime.now().replace(microsecond=0),
        "up_userid": del_userid,
        "up_time": datetime.now().replace(microsecond=0),
    }

    # 执行批量逻辑删除（仅更新字段，不物理删除）
    aiXiangBaoCaiPian_delete_count = db.query(AIXiangBaoKuanHao).filter(
        AIXiangBaoKuanHao.xbkhId.in_(aiXiangBaoKuanHao_ids), # 批量匹配ID
        AIXiangBaoKuanHao.del_flag == False # 仅删除未被删除的记录
    ).update(
        delete_update_fields,
        synchronize_session=False  # 提升批量更新性能
    )

    # 2. 查询当前企业下，关联这些纸格ID的所有未删除裁片ID
    if aiXiangBaoCaiPian_delete_count > 0:
        cp_ids = db.query(AIXiangBaoCaiPian.xbcpId).filter(
            AIXiangBaoCaiPian.xbkhId.in_(aiXiangBaoKuanHao_ids),
            AIXiangBaoCaiPian.del_flag == False
        ).all()
        # 提取裁片ID列表（转换为[int]格式）
        cp_id_list = [cp_id[0] for cp_id in cp_ids] if cp_ids else []

        # 3. 批量逻辑删除裁片记录
        if cp_id_list:
            cp_delete_count = db.query(AIXiangBaoCaiPian).filter(
                AIXiangBaoCaiPian.xbcpId.in_(cp_id_list),
                AIXiangBaoCaiPian.del_flag == False
            ).update(
                delete_update_fields,
                synchronize_session=False
            )

            # 4. 查询当前企业下，关联这些裁片ID的所有未删除工艺记录ID
            craft_ids = db.query(AICaiPianGongYi.cpgyId).filter(  # 工艺表的主键字段
                AICaiPianGongYi.xbcpId.in_(cp_id_list),
                AICaiPianGongYi.del_flag == False
            ).all()
            # 提取工艺ID列表
            craft_id_list = [craft_id[0] for craft_id in craft_ids] if craft_ids else []

            # 5. 批量逻辑删除工艺记录
            if craft_id_list:
                db.query(AICaiPianGongYi).filter(
                    AICaiPianGongYi.cpgyId.in_(craft_id_list),  # 工艺表的主键字段
                    AICaiPianGongYi.del_flag == False
                ).update(
                    delete_update_fields,
                    synchronize_session=False
                )


    return aiXiangBaoCaiPian_delete_count





def update_aiXiangBaoKuanHao(db: Session,aiXiangBaoKuanHaoRequest: AIXiangBaoKuanHaoRequest):
    """
    更新纸格信息
    :param db: 数据库会话
    :param aiXiangBaoKuanHaoRequest: 纸格信息请求对象
    :raise DataUpdateFailedException: 更新失败（无匹配记录/更新行数为0）
    """
    update_count = 0

    update_count= db.query(AIXiangBaoKuanHao).filter(
        AIXiangBaoKuanHao.xbkhId == aiXiangBaoKuanHaoRequest.xbkhId,
        AIXiangBaoKuanHao.gsId == aiXiangBaoKuanHaoRequest.gsId,
        AIXiangBaoKuanHao.del_flag == False
    ).update(
        {
            AIXiangBaoKuanHao.kuanHaoMingCheng: aiXiangBaoKuanHaoRequest.kuanHaoMingCheng,#产品款式编号
            AIXiangBaoKuanHao.banBenHao: aiXiangBaoKuanHaoRequest.banBenHao,#产品版本号
            AIXiangBaoKuanHao.xbbxId: aiXiangBaoKuanHaoRequest.xbbxId,#箱包包型id
            AIXiangBaoKuanHao.dqbmId: aiXiangBaoKuanHaoRequest.dqbmId,#地区编码
            AIXiangBaoKuanHao.up_userid: aiXiangBaoKuanHaoRequest.up_userid,#最后更新人员
            AIXiangBaoKuanHao.up_time: datetime.now().replace(microsecond=0),#最后更新时间
            AIXiangBaoKuanHao.beiZhu: aiXiangBaoKuanHaoRequest.beiZhu#备注
    })

    # 4. 校验更新结果
    if update_count == 0:
        raise DataUpdateFailedException(
            message=f"更新纸格信息失败：未找到箱包款号id={aiXiangBaoKuanHaoRequest.xbkhId}、公司id={aiXiangBaoKuanHaoRequest.gsId}的有效记录",
            details={
                "xbkhId": aiXiangBaoKuanHaoRequest.xbkhId,
                "gsId": aiXiangBaoKuanHaoRequest.gsId,
                "filter_conditions": "del_flag=False"
            }
        )


def update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(db: Session,aiXiangBaoCaiPianRequest: AIXiangBaoCaiPianRequest) -> Tuple[int, int]:
    """
    更新裁片信息 + 批量更新裁片工艺信息（仅裁片类型为料格时更新工艺）
    :param db: 数据库会话
    :param aiXiangBaoCaiPianRequest: 裁片信息请求对象
    :return: Tuple[int, int] - (裁片更新行数, 工艺更新总行数)
    :raise DataUpdateFailedException: 裁片/工艺更新失败（无匹配记录）
    """
    aiXiangBaoCaiPian_update_count = 0

    aiXiangBaoCaiPian_update_count= db.query(AIXiangBaoCaiPian).filter(
        AIXiangBaoCaiPian.xbcpId == aiXiangBaoCaiPianRequest.xbcpId,
        AIXiangBaoCaiPian.gsId == aiXiangBaoCaiPianRequest.gsId,
        AIXiangBaoCaiPian.del_flag == False
    ).update(
        {
            AIXiangBaoCaiPian.caiPianLeiXing: aiXiangBaoCaiPianRequest.caiPianLeiXing,#裁片类型（0=料格/1=资料卡/2=正格/3=工艺格/4=其他）
            AIXiangBaoCaiPian.xbbwId: aiXiangBaoCaiPianRequest.xbbwId,#裁片所属部位ID
            AIXiangBaoCaiPian.xbczId: aiXiangBaoCaiPianRequest.xbczId,#裁片材质ID
            AIXiangBaoCaiPian.caiPianHouDu: aiXiangBaoCaiPianRequest.caiPianHouDu,#裁片厚度(单位：mm)
            AIXiangBaoCaiPian.up_userid: aiXiangBaoCaiPianRequest.up_userid,#最后更新人员
            AIXiangBaoCaiPian.up_time: datetime.now().replace(microsecond=0),#最后更新时间
    })

    # ----------批量更新裁片工艺信息 ----------
    gongyi_update_total = 0  # 工艺更新总行数

    if aiXiangBaoCaiPianRequest.gongYiLieBiao and aiXiangBaoCaiPianRequest.caiPianLeiXing == 0:#只有裁片类型是料格的时候才更新工艺(工艺列表不为空)
        for gongyi_req in aiXiangBaoCaiPianRequest.gongYiLieBiao:
            # 单条工艺更新（按主键+公司ID过滤）
            update_count = db.query(AICaiPianGongYi).filter(
                AICaiPianGongYi.cpgyId == gongyi_req.cpgyId,  # 工艺表主键
                AICaiPianGongYi.gsId == gongyi_req.gsId,# 仅更新当前企业的数据（数据隔离）
                AICaiPianGongYi.xbcpId == aiXiangBaoCaiPianRequest.xbcpId,# 保证关联的裁片与传入的裁片id相匹配
                AICaiPianGongYi.del_flag == False # 仅更新未被删除的记录
            ).update(
                {
                    AICaiPianGongYi.gongYiLeiXing: gongyi_req.gongYiLeiXing,  #工艺类型（0=工艺/1=备注）
                    AICaiPianGongYi.up_userid: gongyi_req.up_userid,  # 最后更新人员
                    AICaiPianGongYi.up_time: datetime.now().replace(microsecond=0),  # 最后更新时间
                },
                synchronize_session=False
            )
            gongyi_update_total += update_count


    # 4. 校验更新结果
    if aiXiangBaoCaiPian_update_count == 0:#裁片更新成功的数量
        raise DataUpdateFailedException(
            message=f"更新裁片信息失败：未找到裁片id={aiXiangBaoCaiPianRequest.xbcpId}、公司id={aiXiangBaoCaiPianRequest.gsId}的有效记录",
            details={
                "xbcpId": aiXiangBaoCaiPianRequest.xbcpId,
                "gsId": aiXiangBaoCaiPianRequest.gsId,
                "filter_conditions": "del_flag=False"
            }
        )


    # 校验工艺批量更新结果（如果工艺列表不为空且裁片类型为料格，但全部更新0行则抛异常）
    if aiXiangBaoCaiPianRequest.gongYiLieBiao and aiXiangBaoCaiPianRequest.caiPianLeiXing == 0 and gongyi_update_total == 0:
        raise DataUpdateFailedException(
            message="批量更新裁片工艺失败：所有工艺记录均未找到匹配的有效记录",
            details={
                "gongyi_list": [item.dict() for item in aiXiangBaoCaiPianRequest.gongYiLieBiao],
                "filter_conditions": "del_flag=False"
            }
        )

    # ========== 4. 返回两个受影响的行数 ==========
    return aiXiangBaoCaiPian_update_count, gongyi_update_total


















