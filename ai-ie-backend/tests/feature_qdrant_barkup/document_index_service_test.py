


import asyncio
from app.services.index.document_index_service import document_service

async def main():
    # document_id = await document_service.create_document(
    #     user_id=1326383987953952,
    #     rules=["规则9", "规则10"],
    #     enterprise_id=1,
    #     standard_id=1,
    # )
    # print(f"Created document with ID: {document_id}")

    # ids = ['0696dcf9-d64d-7f03-8000-9363ebc69bdc','0696dcf9-d67d-715d-8000-fdb4f92291b5',]
    # await document_service.delete_document(
    #     ids=ids,
    # )
    # print(f"Deleted document with ID: {ids}")

    id_rule_dict = {'0696dcf9-d64d-7f03-8000-9363ebc69bdc': "规则77", '0696dcf9-d67d-715d-8000-fdb4f92291b5': "规则88"}
    await document_service.update_document(
        id_rule_dict=id_rule_dict,
    )
    print(f"Updated document with ID: {id_rule_dict}")


    pass


if __name__ == "__main__":

    # id_rule_dict = { None:None , None:1, 2:None}
    # print(id_rule_dict)
    # if 0:
    #     print(000)

    asyncio.run(main())


    pass
