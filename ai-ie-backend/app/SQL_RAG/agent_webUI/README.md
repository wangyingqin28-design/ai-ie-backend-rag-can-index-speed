# SQL_RAG agent_webUI

这个目录是 SQL_RAG 智能客服业务脑的前端工作台。

启动前需要先启动业务脑后端：

```powershell
.\.venv\Scripts\python.exe app\SQL_RAG\main.py business-brain-service --host 127.0.0.1 --port 18180
```

启动前端 WebUI：

```powershell
.\.venv\Scripts\python.exe app\SQL_RAG\agent_webUI\webui_server.py --host 127.0.0.1 --port 18181 --backend-url http://127.0.0.1:18180
```

浏览器访问：

```text
http://127.0.0.1:18181
```

前端会先逐字展示公开执行链路，后端返回后主动折叠解析过程，再逐字输出最终答案和业务执行结果。
