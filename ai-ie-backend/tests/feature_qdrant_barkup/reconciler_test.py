



# a_dict = {'1': {'a':[1,2,3], 'b':[4,5,6],'c':[7,8,9]},
#             '2': {'a':[10,11,12], 'b':[13,14,15],'c':[]},
#         }

# b_list = []

# for key, value in a_dict.items():
#     b_list.append((key, value))
# print(b_list)    

# b_list[1][1]['c'] = [100,101,102]
# # b_list[1][0]= '22'
# print(a_dict)

# print(b_list)

# print('========')
# c_list = []
# for key, value in a_dict.items():
#     c_list.append({key:value})
# print(c_list)
# c_list[1]['2']['c'] = [1000,1001,1002]
# print(c_list)
# print(a_dict)
# a_dict.pop('2')
# print(a_dict)
# print(c_list)
# c_list.pop(0)
# print(c_list)
# print(a_dict)

print('========')
d_dict = {'1': {'a':[1,2,3], 'b':[4,5,6],'c':[7,8,9]},
            '2': {'a':[10,11,12], 'b':[13,14,15],'c':[]},
        }
e_list = {'create':[],'update':[],'delete':[]}
tmp_list = [ (key, value) for key, value in d_dict.items() ]
e_list['create'].extend(tmp_list)
print(e_list)

