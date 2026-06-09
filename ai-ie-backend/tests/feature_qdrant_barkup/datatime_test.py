
from datetime import datetime

datetime_date = datetime.now()

print("原始 datetime:", datetime_date)
print("原始 isoformat:", datetime_date.isoformat())

# 方法1: 使用 strftime 格式化（推荐）
formatted_str = datetime_date.strftime("%Y-%m-%d %H:%M:%S")
print("方法1 strftime:", formatted_str)

# 方法2: 使用 replace 去除微秒后转字符串
no_microsecond = datetime_date.replace(microsecond=0)
formatted_str2 = str(no_microsecond)
print("方法2 replace:", formatted_str2)

# 方法3: 字符串分割（如果已经有 isoformat 字符串）
iso_str = datetime_date.isoformat()
formatted_str3 = iso_str.split('.')[0]
print("方法3 字符串分割:", formatted_str3)
