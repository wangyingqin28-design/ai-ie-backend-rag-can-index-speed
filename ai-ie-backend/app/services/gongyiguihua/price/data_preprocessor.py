# 数据预处理模块

import json
import random
import re
from typing import Dict, Any, List
from app.utils.exceptions import  NotFoundException


def process_rag_response(ai_response_text: str) -> str:

    """合并调用两个函数预处理数据。 """
    operations_dict = extract_operations_from_text(ai_response_text)

    if not operations_dict:
        raise NotFoundException(
            message="预处理：未能从大模型响应文本中提取到有效的工序列表",
            details={"ai_response_text": ai_response_text}
        )

    raw_operations_json = json.dumps(operations_dict, ensure_ascii=False)
    final_processed_json = preprocess_data(raw_operations_json)

    return final_processed_json


def extract_operations_from_text(ai_response_text: str) -> Dict[str, Any]:

    """
    从 AI 生成的文本响应中提取工序列表，并构建字典（工序-工种）。
    """

    lines = ai_response_text.split('\n')
    operations_dict = {}
    collecting_operations = False  # 标志位，用于判断是否开始收集工序

    for line in lines:
        stripped_line = line.strip()
        if "组装工序列表：" in stripped_line:
            collecting_operations = True
            continue

        if collecting_operations:
            if not stripped_line: # 空行结束收集
                break

            # 尝试匹配 "数字. 工序名称-工种" 的格式
            match = re.match(r'^\s*\d+\.\s*(.+?)\s*-\s*(.+)$', stripped_line)

            if match:
                operation_name = match.group(1).strip()
                work_type = match.group(2).strip()
                operations_dict[operation_name] = {"工种": work_type}

            else:
                # 如果某行不符合格式，即ai生成的文本中包含了其他信息，如说明
                if stripped_line.startswith("**说明**") or stripped_line.startswith("说明"):
                    break

    return operations_dict


def preprocess_data(raw_data_json: str) -> str:

    """预处理原始工序数据 JSON 字符串，补充缺失的 "长度" 和 "难度系数" 字段。"""
    try:
        raw_data = json.loads(raw_data_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"输入的原始JSON格式错误: {e}")

    preprocessed_data = {}

    # 键赋给 op_name，工序名   值赋给 op_info。
    for op_name, op_info in raw_data.items():
        
        processed_op_info = op_info.copy() # 复制工种信息  { "工种": "手工" },

        if "长度" not in processed_op_info:
            job_type = processed_op_info.get("工种")
            if job_type in ["平车", "电脑车", "高车", "柱车", "锤机"]: 
                processed_op_info["长度"] = round(random.uniform(5.0, 50.0), 2) 
            else: 
                processed_op_info["长度"] = 1.0 
            
           
        if "难度系数" not in processed_op_info:
            processed_op_info["难度系数"] = round(random.uniform(0.8, 3.0), 2)
            
        preprocessed_data[op_name] = processed_op_info

    return json.dumps(preprocessed_data, ensure_ascii=False)