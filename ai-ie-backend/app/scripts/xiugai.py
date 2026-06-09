import json

# 1. 读取原始 JSON 文件
with open('规则表.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# 2. 仅保留每个规则的 text 字段（保留原始顶层结构）
data["通用规则库"] = [{"text": rule["text"]} for rule in data["通用规则库"]]


with open('rules.json', 'w', encoding='utf-8') as file:  # 保存为新文件（取消注释使用）
    json.dump(data, file, ensure_ascii=False, indent=2)

