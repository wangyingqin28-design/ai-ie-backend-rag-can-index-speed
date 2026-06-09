import re
def str_transform(text):
    if not text:
        return ""
    try:
        
        pattern = re.compile(r'\\U\+([0-9a-fA-F]{4})([0-9a-fA-F]*)')# 匹配 \U+ 开头，后面跟至少4位十六进制数
        def replace_match(match):
                # 分组1：前4位十六进制数（需要转换的部分）
                # 分组2：剩余的十六进制数（需要保留的部分）
            code_str = match.group(1)
            rest_str = match.group(2)
            try:
                code = int(code_str, 16)  #前四位Unicode十六进制转成十进制
                if 0 <= code <= 0x10FFFF:   #判断是否在范围内
                        # 转换前4位为字符，拼接剩余部分
                    return chr(code) + rest_str
                else:
                        # 编码无效时，返回原始序列
                    return f"\\U+{code_str}{rest_str}"
            except ValueError:
                return f"\\U+{code_str}{rest_str}"  
        str = pattern.sub(replace_match, text)  #转换每一个匹配的字符串，并保留没匹配上的原字符串
        return str.encode("latin-1").decode("gbk")  #转换gbk编码的文本
    
    except Exception:
        return str
        