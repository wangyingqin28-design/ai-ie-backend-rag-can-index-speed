from typing import List, Dict, Any
from sqlalchemy.orm import Session

# 导入数据库配置和模型
from app.models.orm_models import AIXiangBaoCaiPian, AICaiPianGongYi


def fetch_cai_pian_gong_yi_data(request, xbkh_id: int) -> List[Dict[str, Any]]:
    """
    从数据库获取指定箱包款式ID的裁片和工艺信息

    参数:
        request: FastAPI请求对象，用于获取数据库会话
        xbkh_id (int): 箱包款式ID

    返回:
        List[Dict[str, Any]]: 处理后的结果列表，格式为 [
            {"款号": "xxx"},
            {"裁片名称": "裁片1", "部位工艺": ["工艺1", "工艺2", ...]},
            ...
        ]
        注意：会过滤掉"部位工艺"为空的裁片
    """
    # 从请求状态中获取数据库会话
    db = request.state.db

    # 查询该款式ID下的所有裁片（排除已删除的）
    cai_pian_list = db.query(AIXiangBaoCaiPian).filter(
        AIXiangBaoCaiPian.xbkhId == xbkh_id,
        AIXiangBaoCaiPian.del_flag == 0
    ).all()

    if not cai_pian_list:
        return [{"款号": str(xbkh_id)}, []]

    # 获取款号（从第一个裁片获取）
    xbkh_id_value = cai_pian_list[0].xbkhId

    # 创建一个字典来按裁片名称分组
    grouped_data = {}

    # 遍历所有裁片
    for cai_pian in cai_pian_list:
        cai_pian_name = cai_pian.caiPianMingCheng or "未命名裁片"

        # 初始化裁片条目
        if cai_pian_name not in grouped_data:
            grouped_data[cai_pian_name] = {
                "裁片名称": cai_pian_name,
                "部位工艺": []
            }

        # 查询该裁片对应的所有工艺（排除已删除的）
        gong_yi_list = db.query(AICaiPianGongYi).filter(
            AICaiPianGongYi.xbcpId == cai_pian.xbcpId,
            AICaiPianGongYi.del_flag == 0
        ).all()

        # 添加工艺描述
        for gong_yi in gong_yi_list:
            if gong_yi.gongYiMiaoShu and gong_yi.gongYiMiaoShu.strip():
                grouped_data[cai_pian_name]["部位工艺"].append(gong_yi.gongYiMiaoShu.strip())

    # ===== 新增：过滤掉"部位工艺"为空的裁片 =====
    filtered_data = {}
    for name, data in grouped_data.items():
        # 只保留有工艺的裁片
        if data["部位工艺"]:  # 非空列表
            filtered_data[name] = data

    # 如果过滤后没有裁片，返回款号和空列表
    if not filtered_data:
        return [{"款号": str(xbkh_id_value)}, []]

    # 将过滤后的字典值转换为列表
    data_list = list(filtered_data.values())

    # 在列表开头添加款号信息
    return  data_list