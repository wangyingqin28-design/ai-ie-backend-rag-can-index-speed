



a =(upsert_id
   for upsert_id, _ in {'key1': 'value1', 'key2': 'value2'}.items()
   for index_type in ['vector', 'fulltext', 'graph'])
print(type(a))