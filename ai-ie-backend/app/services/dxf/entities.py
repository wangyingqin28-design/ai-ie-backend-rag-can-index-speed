from app.services.dxf import str_transform


def dxf_entities(entity):
     # 获取实体类型
    entity_type = entity.dxftype()

    print(f"\n实体类型: {entity_type}")
    print(f"实体所在图层：{entity.dxf.layer}")

        
        # 解析点(POINT)
    if entity_type == "POINT":
        pass
        # print(f"点的坐标：{entity.dxf.location}")

        # 解析直线（LINE）
    elif entity_type == "LINE":
        pass
        # print(f"起点坐标: {entity.dxf.start}")  # (x, y, z)
        # print(f"终点坐标: {entity.dxf.end}")
        # print(f"颜色: {entity.dxf.color}")  # 0=随层，256=随块

        # 解析文本（TEXT）
    elif entity_type == "TEXT":        # 先暂时提取这个，只做这个返回值  <<<<<<<<=============
        raw_text = entity.dxf.text
        text = str_transform.str_transform(raw_text)#解决乱码
        # print(f"文本内容: {text}")
        # print(f"文本位置: {entity.dxf.insert}")  # 文本位置
        # print(f"字体高度: {entity.dxf.height}")
        # print(f"旋转角度: {entity.dxf.rotation}°")
        if text == "":
            text = " "
        data = [text,f"{entity.dxf.insert}"]
        return data        


        # 解析多段线（POLYLINE，多段线）
    elif entity_type == "POLYLINE":
        pass
        # print(f"顶点数量: {len(entity)}")
        #
        # m=2  #创建两行三列的数组，存储首顶点和尾顶点的坐标，判断是否闭合
        # n=3
        # arr = np.zeros((m,n))  #初始化数组
        #
        # for i, vertex in enumerate(entity.vertices):   #遍历实体中的所有点
        #     location = vertex.dxf.location
        #
        #     if i==0 :               #录入首顶点
        #         arr [0][0]=location.x
        #         arr [0][1]=location.y
        #         arr [0][2]=location.z
        #     elif i==len(entity)-1:    #录入尾顶点
        #         arr [1][0]=location.x
        #         arr [1][1]=location.y
        #         arr [1][2]=location.z
        #
        #     print(f"顶点 {i + 1}: ({location.x}, {location.y}，{location.z})") #列出各个顶点
        #
        # is_closed1 = (entity.dxf.flags & 1) == 1  # 第0位为1表示闭合
        # is_closed2 = all(arr[0]==arr[1])
        # print(f"多段线闭合状态: {'是' if is_closed1 or is_closed2 else '否'}")


#============================================================没用👇        
        # 解析圆（CIRCLE）
    elif entity_type == "CIRCLE":
        pass
        # print(f"圆心坐标: {entity.dxf.center}")
        # print(f"半径: {entity.dxf.radius}")
        # print(f"颜色: {entity.dxf.color}")

        #解析椭圆（ELLIPSE)
    elif entity_type == "ELLIPSE":
        pass
        # print(f"中心坐标：{entity.dxf.center}")
        # print(f"长轴向量：{entity.dxf.major_axis}")
        # print(f"短轴/长轴比例:{entity.dxf.ratio}")
        # print(f"起始参数：{entity.dxf.start_param}")
        # print(f"终止参数：{entity.dxf.end_param}")
            
        #解析圆弧（ARC)
    elif entity_type == "ARC":
        pass
        # print(f"圆心坐标：{entity.dxf.center}")
        # print(f"半径：{entity.dxf.radius}")
        # print(f"起始角度: {entity.dxf.start_angle}")
        # print(f"起始角度: {entity.dxf.end_angle}")
        # print(f"颜色: {entity.dxf.color}")
        #解析样条曲线（SPLINE)
    elif entity_type == "SPLINE":
        pass
        # print(f"阶数：{entity.dxf.degree}")
        # print(f"闭合状态: {'是' if entity.dxf.closed else '否'}")
        # print(f"控制点数量：{len(entity.dxf.control_points)}")
        #     # 打印所有控制点坐标
        # for i, vertex in enumerate(entity.dxf.control_points):
        #     print(f"控制点 {i + 1}: ({vertex.x}, {vertex.y})")
    
    return ""
