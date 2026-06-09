# 计算工价模块
import json

from app.utils.exceptions import NotFoundException
from .work_price_db import get_work_prices
from fastapi import Request


# 各工种缝纫针距（毫米/针）
STITCH_LENGTH = {
    "平车": 3.0,
    "电脑车": 4.0,
    "高车": 4.0,
    "柱车": 3.0,
    "锤机": 2.0,
}

# 各工种缝纫速度（针/秒）
SEWING_SPEED = {
    "平车": 10.0,
    "电脑车": 12.0,
    "高车": 6.0,
    "柱车": 6.5,
    "锤机": 6.0,
}

# 工作制度       
WORK_DAYS_MON = 30
WORK_HOURS_DAY = 10

# 台面工序的固定单价 （元）
MANUAL_PRICE = {
    "穿拉头": 0.03,
    "剪介子": 0.01,
    "翻介子": 0.02,
    "挂吊牌": 0.03,
    "扎手挽": 0.05,
    "成品吹线": 0.1,
    "成品剪线": 0.1,
    "成品清洁": 0.1,
    " 放干燥剂":0.03  ,
    " 塞纸":0.02,
    " 扎长肩带":0.05  ,
    " 挂吊饰  ":0.05,
    " 装箱  ":0.07,
    "写箱号贴箱贴":0.03
}

# 台面工种的基础单价
BENCHWORK_BASE_PRICE = 0.08




def calculate_labor_cost(ops_data_json: str, xbkhId: int, request: Request) -> str:
    """
    计算工序工价。
    Args:
            输入：
            {"工序名1": {"长度": float, "难度系数": float, "工种": str},}
            xbkhId (int): 款号表ID，用于从数据库获取 企业id 地区编码信息
    Returns:
        str: 包含总工价和各工序详细信息的 JSON 字符串。
             格式为: {
                 "款号": xbkhId,
                 "总工价": float,
                 "工序详情": [
                     {"工序名称": str, "工种": str, "工价": float},
                ]}
    """
    try:
         operations_data = json.loads(ops_data_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"输入的JSON格式错误: {e}")

    try:
        work_price, xiangBaoMingCheng = get_work_prices(xbkhId,request)
        if not work_price :
            raise NotFoundException(
                message="未能从数据库中提取到有效工种工资列表",
                details={
                    "数据库返回内容：": work_price,
                }
            )
        #print(f"-----工种工资: {work_price}")
    except ValueError as e:
        raise ValueError(f"根据 xbkhId {xbkhId} 获取工种工资信息失败: {e}")

    total_cost = 0.0
    details = [] 

    #  "工序名1": {"长度": float, "难度系数": float, "工种": str},
    for op_name, info in operations_data.items():

        if not isinstance(info, dict):
            raise ValueError(f"工序 '{op_name}' 的信息必须是dict字典格式")

        length = info.get("长度", 0)
        difficulty = info.get("难度系数", 1.0)
        job_type = info.get("工种")

        if not job_type:
            raise ValueError(f"工序 '{op_name}' 缺少 '工种' 参数")

        #  计算成本
        if job_type == "台面":
            fixed_price = MANUAL_PRICE.get(op_name)
            if fixed_price is not None:
                unit_price = fixed_price

            else:
                unit_price = BENCHWORK_BASE_PRICE * difficulty

            total_cost += unit_price
            details.append({
                "工序名称": op_name,
                "工种": job_type,
                "工价": round(unit_price, 4)
            })

        elif job_type in STITCH_LENGTH and job_type in SEWING_SPEED:
            #  车位
            monthly_wage = work_price.get(job_type)
            stitch_distance = STITCH_LENGTH.get(job_type)
            sew_speed = SEWING_SPEED.get(job_type)

            if monthly_wage is None:
                raise ValueError(f"数据库中未找到工种 '{job_type}' 的工资数据")
            if stitch_distance is None or sew_speed is None:
                raise ValueError(f"未知机器工种 '{job_type}' 或其配置（针距/速度）缺失")

            if stitch_distance <= 0 or sew_speed <= 0:
                raise ValueError(f"工种 '{job_type}' 的针距和缝纫速度必须大于0")

            # 计算该工种每秒的工资
            seconds_per_month = WORK_DAYS_MON * WORK_HOURS_DAY * 3600
            wage_per_second = monthly_wage / seconds_per_month

            # 设备每秒前进的距离（cm）
            cm_per_second = (stitch_distance * sew_speed) / 10

            # 计算该工序所需的时间（秒）
            if length == 0:
                process_time_seconds = 0  # 长度为0，时间也为0
            else:
                if cm_per_second == 0:
                    raise ValueError(f"工种 '{job_type}' 的计算速度为0，无法完成长度为 {length} 的工序")
                process_time_seconds = length / cm_per_second

            # 工价
            unit_price = wage_per_second * process_time_seconds * difficulty

            total_cost += unit_price
            details.append({
                "工序名称": op_name,
                "工种": job_type,
                "工价": round(unit_price, 4)
            })

        else:
            raise ValueError(f"未知工种 '{job_type}'，必须是 '台面', '平车', '电脑车', '高车', '柱车', '锤机' 中的一种")

    result = {

        "箱包款号": xiangBaoMingCheng,
        #"总工价": round(total_cost, 4),
        "工序详情": details
    }
    return result





