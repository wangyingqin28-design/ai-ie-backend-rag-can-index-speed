
import json

from pydantic import PositiveInt

# from uuid_extensions import uuid7
# for i in range(6):
#     print(type(uuid7()),len(str(uuid7())),uuid7())


# a_list = [{'a':1,'b':2},{'a':3,'b':4}]
# b_list = [{'a':1,'b':2},{'a':3,'b':4}]
# a_list_str = json.dumps(a_list)
# b_list_str = json.dumps(b_list)
# print(type(a_list_str),a_list_str)
# print(type(b_list_str),b_list_str)
# print(a_list_str == b_list_str)

# b = {'key1':{'key11':'value11','key12':'value12'},'key2':{'key21':'value21','key22':'value22'}}
# a_dict= b
# a_dict1 = a_dict['key1']
# a_dict1.pop('key11')
# print(a_dict)

# b = {'key1':{'key11':'value11','key12':'value12'},'key2':{'key11':'value21','key22':'value22'}}
# a_dict= b
# a_dict1 = a_dict['key1']
# for key,value in a_dict1.items():
#     for tmp1,tmp2 in a_dict['key2'].items():
#         if key == tmp1:
#             a_dict1.pop(key)

# print(b)
# print(a_dict)

# a_list = [{'a':1,'b':2},{'a':3,'b':4}]

# for item in a_list:
#     if item['a'] == 3:
#         a_list.remove(item)

# print(a_list)


from app.schemas.mssql_qdrant.constant import IndexAction
a_str = 'create'

print(a_str == IndexAction.CREATE)

print(type(a_str))
print(type(IndexAction.CREATE))
