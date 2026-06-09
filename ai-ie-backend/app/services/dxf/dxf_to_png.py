import io
import os
import tempfile

import ezdxf
import matplotlib.pyplot as plt
from fastapi import Request
from loguru import logger
from minio import Minio

from app.services.dxf import str_transform
from app.utils.exceptions import AppException
from app.utils.minio_config import MinIOConfig


class DrawDxfService:

    #初始化
    def __init__(self):
        self.config = MinIOConfig.get_config()
        self.bucket_name = self.config["cutting_pieces_bucket"]#获取裁片桶名
        self.dxf_bucket_name = self.config["bucket"]#获取dxf桶名
        self.minio_client = None
        # 2026-06-02 09:21:45 修改：MinIO 是 DXF 绘图输出依赖，不应在服务启动时阻断 SQL_RAG/Qdrant 后端。
        try:
            self._init_minio_client()
        except Exception as exc:
            logger.warning(f"MinIO 初始化失败，DXF 绘图接口将延迟到实际调用时再报错: {exc}")

    def _init_minio_client(self):
        """初始化 MinIO 客户端"""
        self.minio_client = Minio(
            self.config["endpoint"],
            access_key=self.config["access_key"],
            secret_key=self.config["secret_key"],
            secure=self.config["secure"]
        )
        # 确保桶存在
        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)

    def _ensure_minio_client(self):
        # 2026-06-02 09:21:45 修改：实际绘图上传前检查 MinIO，避免启动阶段外部存储不可用导致整个后端退出。
        if self.minio_client is None:
            raise AppException(
                code=503,
                message="MinIO 文件服务当前不可用，请检查 MinIO endpoint 配置和服务状态",
                details={"endpoint": self.config.get("endpoint"), "bucket": self.bucket_name},
                status_code=503,
            )
        return self.minio_client

    def draw(self,request:Request,file:bytes,file_name,dpi=1000):
        # =================================================================================================================
        CONFIG = {
            "figsize": (10, 8),
            "line_width": 0.2,
            "font_family": "Microsoft YaHei",
            "margin_ratio": 0.01,  # 画布边距比例
            "default_lim": (-10, 10),  # 空图形默认画布范围
            "text_size": 0.5,  # 文本字号与高度的比例
            "rotation_invert": True,  # 是否反转文本旋转角度
        }
        # 存储所有图片的MinIO访问链接
        png_url_list = []
        object_name_list = []
        i = 0
        db = request.state.db
        # 创建临时文件（自动删除，二进制模式）
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.dxf', delete=False) as temp_f:
            temp_f.write(file)  # 把字节数据写入临时文件
            temp_path = temp_f.name  # 获取临时文件路径
        # =================================================================================================================
        try:
            # 用readfile读取临时文件路径
            doc = ezdxf.readfile(temp_path)
        except Exception as e:
            raise RuntimeError(f"处理DXF文件失败: , 错误: {str(e)}")

        finally:
            # 删除临时文件，避免残留
            os.unlink(temp_path)

        msp = doc.modelspace()
        blocks = doc.blocks
        # =================================================================================================================
        for entity in msp:
            entity_type = entity.dxftype()

            if entity_type != "INSERT":  # 不是块直接一个跳过
                continue

            block_name = entity.dxf.name  # 引用的块名
            # 2. 根据块名查找对应的块定义
            block = blocks.get(block_name)
            if not block:
                print(f"警告：未找到块定义 '{block_name}'")
                continue
            # =================================================================================================================

            # 2. 准备绘图画布
            fig, ax = plt.subplots(figsize=CONFIG["figsize"])
            ax.set_aspect('equal')  # 保证图形比例不失真
            ax.axis('off')  # 隐藏坐标轴
            # 存储所有图形的坐标，用于自动调整画布范围
            all_points = []
            # =================================================================================================================
            i = 1  # 当i为1时需要把裁片图的名改了
            PNG_name = None  # 初始化
            for sub_entity in block:
                sub_entity_type = sub_entity.dxftype()
                if sub_entity_type == "LINE":
                    x1, y1, _ = sub_entity.dxf.start
                    x2, y2, _ = sub_entity.dxf.end
                    ax.plot([x1, x2], [y1, y2], color='black', linewidth=CONFIG["line_width"])
                    all_points.extend([(x1, y1), (x2, y2)])

                elif sub_entity_type == "POLYLINE":
                    points = [(p.dxf.location.x, p.dxf.location.y) for p in sub_entity.vertices]
                    if points:
                        if sub_entity.is_closed:
                            points.append(points[0])
                        x = [p[0] for p in points]
                        y = [p[1] for p in points]
                        ax.plot(x, y, color='black', linewidth=CONFIG["line_width"])
                        all_points.extend(points)

                elif sub_entity_type == "TEXT":
                    # 提取文本属性
                    raw_text = sub_entity.dxf.text
                    text = str_transform.str_transform(raw_text)
                    if i == 1:
                        PNG_name = text
                        i += 1
                    insert_x, insert_y, _ = sub_entity.dxf.insert
                    text_height = sub_entity.dxf.height
                    rotation = sub_entity.dxf.rotation if hasattr(sub_entity.dxf, 'rotation') else 0
                    # 坐标系适配
                    draw_x = insert_x
                    draw_y = insert_y
                    draw_rotation = -rotation  # 旋转角度取反

                    # 绘制文本
                    ax.text(
                        draw_x, draw_y,
                        text,
                        fontsize=text_height * CONFIG["text_size"],
                        rotation=draw_rotation,
                        color='black',
                        ha='left',
                        va='bottom',
                        family='Microsoft YaHei'
                    )
                    all_points.append((insert_x, insert_y))

            # =================================================================================================================
            # 4. 自动调整画布范围
            if all_points:
                xs = [p[0] for p in all_points]
                ys = [p[1] for p in all_points]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
                x_margin = (x_max - x_min) * CONFIG["margin_ratio"] if x_max != x_min else 1
                y_margin = (y_max - y_min) * CONFIG["margin_ratio"] if y_max != y_min else 1
                ax.set_xlim(x_min - x_margin, x_max + x_margin)
                ax.set_ylim(y_min - y_margin), (y_max + y_margin)
            else:
                ax.set_xlim(CONFIG["default_lim"])
                ax.set_ylim(CONFIG["default_lim"])
            # =================================================================================================================

            if PNG_name != None:
                if "*" in PNG_name:
                    PNG_name = PNG_name.replace("*", "x")
            else:
                PNG_name = block_name

            # 4. 生成PNG字节流（无本地保存）
            img_buffer = io.BytesIO()
            plt.tight_layout()
            plt.savefig(img_buffer, dpi=dpi, bbox_inches='tight', pad_inches=0.1, format='png')

            # 计算PNG流的真实长度
            img_buffer.seek(0, os.SEEK_END)  # 指针移到流末尾
            png_length = img_buffer.tell()  # 获取PNG流的真实字节长度
            img_buffer.seek(0)  # 重置指针到起始位置

            # 给文件名添加.png后缀
            if PNG_name is not None:
                if not PNG_name.lower().endswith('.png'):
                    object_name = f"{PNG_name}.png"
                else:
                    object_name = PNG_name
            else:
                object_name = f"{block_name}.png"

            #将裁片图片存入MinIo裁片桶
            self._ensure_minio_client().put_object(
                bucket_name=self.bucket_name,#裁片桶名
                object_name=object_name,#文件名
                data=img_buffer,#图片流
                length=png_length#字节长度

            )

            object_name_list.append(object_name)

            # 释放资源
            img_buffer.close()
            plt.close(fig)
            print(f"裁片{PNG_name}处理并上传MinIO成功")

        #将dxf文件存入dxf桶
        self._ensure_minio_client().put_object(
            bucket_name=self.dxf_bucket_name,  # dxf桶名
            object_name=file_name,  # 文件名
            data=io.BytesIO(file),  # dxf文件流
            length=len(file)  # 字节长度
        )

        return object_name_list
