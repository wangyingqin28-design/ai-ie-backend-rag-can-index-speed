# 地区编码存储进数据库

import pandas as pd
import pyodbc

# --- 请根据您的实际情况修改以下配置 ---
# 1. Excel 文件路径
excel_file_path = r'C:\Users\DELL\Desktop\地区.xlsx'


server = 'YULITH'
database = 'getai'
username = 'dev'
password = '123456'
driver = '{ODBC Driver 17 for SQL Server}'


def calculate_level_and_parent(code):
    """
    根据地区编码计算层级和父级编码
    """
    code_str = str(code).strip() # 确保是字符串并去除空格
    if len(code_str) != 6 or not code_str.isdigit():
        raise ValueError(f"Invalid code format for '{code}', expected 6-digit numeric string.")

    level = 0
    parent_code = None

    if code_str.endswith('0000'):
        level = 1
        parent_code = '0'  # 省级为顶级
    elif code_str.endswith('00'):
        level = 2
        parent_code = code_str[:2] + '0000' # 市级父级是省级
    else:
        level = 3
        parent_code = code_str[:4] + '00' # 区/县级父级是市级

    return level, parent_code


try:
    # 假设列名为 '编码' 和 '名称'，请根据实际情况调整
    df = pd.read_excel(excel_file_path, sheet_name=0, dtype=str) # 读取为字符串以保持编码格式

    # 检查必要的列是否存在
    required_columns = ['行政区划代码', '单位名称']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Excel 文件中缺少必要的列: {missing_cols}. 实际列名为: {list(df.columns)}")

    print(f"成功读取 Excel 文件，共 {len(df)} 行数据。")

    # 计算层级和父级编码
    calculated_data = []
    for index, row in df.iterrows():
        code = row['行政区划代码'].strip() # <--- 使用对应的列名
        name = row['单位名称'].strip() # <--- 使用对应的列名
        if not code or not name:
             print(f"警告: 第 {index+2} 行 (数据行) 编码或名称为空，跳过。")
             continue
        try:
            level, parent_code = calculate_level_and_parent(code)
            calculated_data.append((code, name, parent_code, level))
        except ValueError as ve:
            print(f"警告: 处理第 {index+2} 行 (数据行) 时遇到无效编码 '{code}': {ve}")
            continue # 跳过无效行

    print(f"处理完成，有效数据 {len(calculated_data)} 条。")

    if not calculated_data:
        print("没有有效的数据行可以插入数据库。")
        exit()

    # 建立数据库连接
    conn = pyodbc.connect(
        f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    )
    cursor = conn.cursor()

    # 准备插入语句
    insert_sql = """
    INSERT INTO [dbo].[AI_DiQuBianMa] ([dqbmId], [diQuMingCheng], [fuJiDiquBianMaId], [diQuChengJi])
    VALUES (?, ?, ?, ?)
    """

    # 执行批量插入
    cursor.executemany(insert_sql, calculated_data)

    # 提交事务
    conn.commit()

    print(f"成功插入 {len(calculated_data)} 条记录到 AI_DiQuBianMa 表。")

except FileNotFoundError:
    print(f"错误: 找不到指定的Excel文件: {excel_file_path}")
except KeyError as ke:
    print(f"错误: {ke}")
except pd.errors.EmptyDataError:
    print("错误: Excel 文件是空的或没有数据。")
except pd.errors.ParserError as pe:
    print(f"错误: 解析Excel文件时出现问题: {pe}")
except pyodbc.Error as e:
    print("数据库错误:", e)
    if 'conn' in locals():
        conn.rollback() # 发生错误时回滚
except Exception as e:
    print("发生未知错误:", e)
    if 'conn' in locals():
        conn.rollback()
finally:
    # 关闭游标和连接
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()
    print("数据库连接已关闭。")