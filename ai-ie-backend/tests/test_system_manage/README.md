# 系统管理后端使用指南

## 1、后端代码结构：

```
back-|--app--|--__pycahche__-|--(不用管)

​    |		 |--__init__.py

​	 |		 |--crud.py

​	 |		 |--database.py

​	 |		 |--main.py

​	 |		 |--model.py

​	 |		 |--schemas.py

​    |--.env

​	 |--main.py

​	 |--README.md

​	 |--requirements.txt

​	 |--run.py
```



## 2、启动方式

**第一次才做**：**在目录back\下输入以下代码运行（安装运行所需的库）**

```
pip install -r requirements.txt
```

**然后再输入（后面直接做）**

```
python run.py
```

## 3、想要知道请求体和响应体的最便捷方式和注明

**打开任意浏览器，输入网址（需要等待一段时间）：**
**http://localhost:8000/docs**

**就可以看到所有API的请求体的响应体结构了**

**在此注明：**

> **1、fetch批量导入结构为一个集合**
>
> **2、使用JSON格式传进来时要记得给JSON里面的双引号做转义动作**
>
> **3、JSON格式要求最后一项键值对后面没有逗号**

## 4、功能详情

**.env:存储敏感隐私信息**

**main.py:负责API创建**

**README.md:说明书（在这里！）**

**requirements.txt:运行所需的库**

**run.py:运行脚本**

**app\__pycache__:运行代码的中间产物**

**app\__init__.py:起到python库的识别的作用**

**app\crud.py:增删查改方法（CRUD:Create,Read,Update,Delete)**

**app\database.py:数据库连接配置**

**app\models.py:表结构模型**

**app\schemas.py:请求体、响应体设置**

## 5、补充

**1、更新请求体已设置成可以只传一个键值对，也可以传完整的**
**2、**

