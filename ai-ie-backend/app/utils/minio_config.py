class MinIOConfig:
    """MinIO 配置管理类"""
    MINIO_ENDPOINT = "krauss:9000"
    MINIO_ACCESS_KEY = "root"
    MINIO_SECRET_KEY = "12345678"
    MINIO_SECURE = False
    CUTTING_PIECES_BUCKET = "cutting-pieces"  # 裁片桶名
    MINIO_BUCKET = "dxf-files" # dxf桶名

    @classmethod
    def get_config(cls):
        """获取配置字典"""
        return {
            "endpoint": cls.MINIO_ENDPOINT,
            "access_key": cls.MINIO_ACCESS_KEY,
            "secret_key": cls.MINIO_SECRET_KEY,
            "bucket": cls.MINIO_BUCKET, # dxf桶名
            "secure": cls.MINIO_SECURE,
            "cutting_pieces_bucket": cls.CUTTING_PIECES_BUCKET,# 裁片桶名
        }


