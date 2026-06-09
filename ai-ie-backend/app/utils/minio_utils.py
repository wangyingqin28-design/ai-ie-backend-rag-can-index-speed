from minio import Minio
from minio.error import S3Error
from datetime import timedelta
from typing import Optional
from app.utils.minio_config import MinIOConfig


class MinioUtils:
    """MinIO工具类，集成项目统一配置，封装预签名URL生成等操作"""

    def __init__(self):
        """初始化MinIO客户端（直接读取MinIOConfig中的配置）"""
        # 从配置类获取完整配置
        self.config = MinIOConfig.get_config()

        # 初始化MinIO客户端
        self.minio_client = Minio(
            endpoint=self.config["endpoint"],
            access_key=self.config["access_key"],
            secret_key=self.config["secret_key"],
            secure=self.config["secure"]
        )

    def generate_presigned_url(
            self,
            object_name: str,
            bucket_name: Optional[str] = None,
            expires: timedelta = timedelta(minutes=3)
    ) -> str:
        """
        生成MinIO预签名访问链接（前端可直接访问）

        Args:
            object_name: MinIO中的对象名（带.png/.jpg等后缀）
            bucket_name: 存储桶名称（不传则默认使用dxf桶；裁片场景传cutting_pieces_bucket）
            expires: 链接有效期（datetime.timedelta类型），默认3分钟

        Returns:
            str: 预签名URL字符串

        Raises:
            RuntimeError: 生成链接失败时抛出
        """
        try:
            # 优先级：传入的桶名 > 裁片桶 > 默认dxf桶
            target_bucket = (
                    bucket_name
                    or self.config.get("cutting_pieces_bucket")
                    or self.config["bucket"]
            )

            # 生成预签名GET链接
            presigned_url = self.minio_client.presigned_get_object(
                bucket_name=target_bucket,
                object_name=object_name,
                expires=expires  # 直接传timedelta对象，类型完全匹配
            )
            return presigned_url

        except S3Error as e:
            raise RuntimeError(
                f"生成MinIO预签名链接失败（桶：{target_bucket}，对象名：{object_name}）: {str(e)}"
            )

    # 扩展常用操作（基于配置类）
    def check_bucket_exists(self, bucket_name: Optional[str] = None) -> bool:
        """检查存储桶是否存在"""
        target_bucket = bucket_name or self.config["bucket"]
        return self.minio_client.bucket_exists(target_bucket)


# ------------------------------
# 全局单例（避免重复初始化客户端）
# ------------------------------
def get_minio_utils() -> MinioUtils:
    """获取MinIO工具类单例（项目全局复用）"""
    if not hasattr(get_minio_utils, "_instance"):
        get_minio_utils._instance = MinioUtils()
    return get_minio_utils._instance


# ------------------------------
# 快捷函数（简化调用）
# ------------------------------
def generate_cutting_pieces_presigned_url(
        object_name: str,
        expires: timedelta = timedelta(minutes=3)
) -> str:
    """
    【裁片场景专用】生成预签名URL（自动使用裁片桶 cutting-pieces）
    """
    return get_minio_utils().generate_presigned_url(
        object_name=object_name,
        bucket_name=MinIOConfig.CUTTING_PIECES_BUCKET,
        expires=expires
    )


def generate_dxf_presigned_url(
        object_name: str,
        expires: timedelta = timedelta(minutes=3)
) -> str:
    """
    【DXF场景专用】生成预签名URL（自动使用DXF桶 dxf-files）
    """
    return get_minio_utils().generate_presigned_url(
        object_name=object_name,
        bucket_name=MinIOConfig.MINIO_BUCKET,
        expires=expires
    )

def generate_caipian_presigned_url(
        object_name: str,
        expires: timedelta = timedelta(minutes=3)
) -> str:
    """
    【裁片场景专用】生成预签名URL（自动使用裁片桶 cutting_pieces_bucket）
    """
    return get_minio_utils().generate_presigned_url(
        object_name=object_name,
        bucket_name=MinIOConfig.CUTTING_PIECES_BUCKET,
        expires=expires
    )