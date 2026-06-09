


from app.utils.utils import calculate_file_hash, random_id

test_content = "插袋必须先车拉链，且仅顶部与其他部件缝合，其余三边自由"
print(calculate_file_hash(test_content.encode()))
print(calculate_file_hash('规则3'.encode()))
print(calculate_file_hash('规则33'.encode()))

a = 4444444444444444444444444444444444444444444444444444444444
print(type(a))

random_id = random_id()
print(random_id)

