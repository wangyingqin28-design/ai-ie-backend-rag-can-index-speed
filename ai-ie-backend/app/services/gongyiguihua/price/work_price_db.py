# 数据库查询模块 查（工种名称，工资）

from typing import Dict, List, Tuple, Optional
from fastapi import Request
from app.services.system_manage.GongSiGongJia_crud import GongSiGongJiaCRUD
from app.services.system_manage.QuYuGongJia_crud import QuYuGongJiaCRUD
from app.utils.exceptions import AppException, NotFoundException
from app.services.dxf.dxf_crud import query_aiXiangBaoKuanHao_by_xbkhId


def get_work_prices(xbkhId: int, request:Request) -> Tuple[Dict[str, float], Optional[str]]:
    """
    根据 khId 返回格式为 {gongZhongMingCheng: price} 的字典。
    """
    try:
        db = request.state.db

        # 1. 获取款号信息
        xiangbao_kuanhao = query_aiXiangBaoKuanHao_by_xbkhId(db, xbkhId)
        #print(f"企业ID: {xiangbao_kuanhao.gsId}")

        # 2. 业务逻辑判断
        dqbmId = xiangbao_kuanhao.dqbmId
        gsId = xiangbao_kuanhao.gsId
        kuanHaoMingCheng = xiangbao_kuanhao.kuanHaoMingCheng

        work_price_dict = {}

        if dqbmId is not None and len(dqbmId) == 6 and dqbmId.isdigit():
            try:
                # 3.1 查询区域工资（CRUD操作）
                quyu_gongjia_list,_ = QuYuGongJiaCRUD.search(db, dqbmId, 1, 10, include_deleted=False)
                for item in quyu_gongjia_list:
                    if not isinstance(item, dict):
                        raise ValueError(f"区域工资查询返回的数据项不是字典格式: {item}")
                    if 'GongZhong' not in item or 'gongJia' not in item:
                        raise ValueError( f"区域工资查询返回的数据项缺少必要字段 'GongZhong' 或 'gongJia':{item}")
                    work_price_dict[item["GongZhong"]] = float(item["gongJia"])
            except Exception as e:
                print(f"查询区域工资失败 (dqbmId={dqbmId}): {e}")
                raise ValueError(f"查询区域工资失败, dqbmId={dqbmId}, 原因: {e}") from e



        elif gsId is not None:
            try:
                gongsi_gongjia_list,_ = GongSiGongJiaCRUD.search(db,  gsId,  None, 1,10,include_deleted=False)
                for item in gongsi_gongjia_list:
                    if not isinstance(item, dict):
                        raise ValueError(f"企业工资查询返回的数据项不是字典格式: {item}")
                    if 'GongZhong' not in item or 'gongJia' not in item:
                        raise ValueError( f"企业工资查询返回的数据项缺少必要字段 'GongZhong' 或 'gongJia': {item}")
                    work_price_dict[item["GongZhong"]] = float(item["gongJia"])
            except Exception as e:
                print(f"查询企业工资操作失败 (gsId={gsId}): {e}")
                raise ValueError(f"查询企业工资失败, gsId={gsId}, 原因: {e}") from e

        return work_price_dict, kuanHaoMingCheng

    except AppException as e:
        # 捕获CRUD层抛出的数据库异常
        raise ValueError(f"计算工价数据库操作失败: {e.message}")
    except Exception as e:
        raise ValueError(f"计算工价获取工种工资信息失败: {str(e)}")
