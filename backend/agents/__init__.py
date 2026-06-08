# -*- coding: utf-8 -*-
"""
agents 包
=========
这个文件夹用来存放平台上所有的硬件相关 agent。

【以后怎么加新 agent？】
  1. 在这个文件夹里新建一个 .py 文件（例如 wcca_agent.py），写好这个 agent 的功能；
  2. 打开 registry.py，把新 agent 的信息登记进去；
  3. 前端网页会自动显示出来，无需改动界面代码。

（这个 __init__.py 文件的存在，是为了让 Python 把 agents 文件夹识别成一个"包"，
  里面的代码才能被 main.py 导入。内容可以为空。）
"""
