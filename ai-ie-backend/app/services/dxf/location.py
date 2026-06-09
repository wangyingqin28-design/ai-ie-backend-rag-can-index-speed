import math

def getPosition(center, point):
    #为什么是字符串的坐标?
    # 移除括号和空格，然后按逗号分割
    center_cleaned = center.strip()[1:-1]  # 移除外层的括号
    center_parts = center_cleaned.split(',')
    x0, y0 = float(center_parts[0].strip()), float(center_parts[1].strip())
        
    # 处理目标点坐标字符串
    point_cleaned = point.strip()[1:-1]  # 移除外层的括号
    point_parts = point_cleaned.split(',')
    x1, y1 = float(point_parts[0].strip()), float(point_parts[1].strip())

    #x0, y0 = float(center[0]), float(center[1])
    #x1, y1 = float(point[0]), float(point[1])

#提取坐标

    dx = x1-x0
    dy = y1-y0
    #计算相对向量


    """
    #当有x或者y向量为0时,返回特殊值 
    if dx == 0 or dy == 0:
        if dy == 0 and dx == 0 :
            return "重合"
        
        if dx == 0 :
            if dy > 0 :
                return "正上方"
            else :
                return "正下方"
        
        if dy == 0 :
            if dx > 0 :
                return "正右"
            else :
                return "正左"
     """  

    #计算tan值(有0的情况已经被返回了不用担心会出现0的情况)
    degress =  math.degrees(math.atan2(dy,dx))  #转化为角度

    #返回特殊值
    if x0==x1 and y0==y1:
        return "(0.0 , 0.0 , 0.0)"
    elif degress == 0:
        return "正右方"
    elif degress == 90:
        return "正上方"
    elif degress == 180:
        return "正左方"
    elif degress == -90:
        return "正下方"
    
    elif -15 <= degress <= 15 :
        return "右方"
    
    elif 15 < degress < 75 :
        return "右上方"
    
    elif 75 <= degress <= 105 :
        return "上方"
    
    elif 105 < degress <= 165 :
        return "左上方"
    
    elif 165 <= degress <180 or -180 < degress <= -165 :
        return "左方"
    
    elif -165 < degress < -105 :  
        return "左下方"
    
    elif -105 <= degress <= -75 :
        return "下方"
    
    elif -75 <= degress <= -15 :
        return "右下方"
    else:
        return "解析失败"