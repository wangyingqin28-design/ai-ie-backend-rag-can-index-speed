from datetime import datetime, timezone
from sonyflake import Sonyflake

sf = Sonyflake(
    start_time=datetime(2024, 1, 1, tzinfo=timezone.utc)   # 任意你系统部署前的时间
)

unique_id = sf.next_id()
print(unique_id)