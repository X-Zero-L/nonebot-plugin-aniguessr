<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-aniguessr ✨

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/X-Zero-L/nonebot-plugin-aniguessr.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-aniguessr">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-aniguessr.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">
<a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json" alt="ruff">
</a>
<a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
</a>
</div>

> [!IMPORTANT] > **收藏项目** ～ ⭐️

<img width="100%" src="https://starify.komoridevs.icu/api/starify?owner=X-Zero-L&repo=nonebot-plugin-aniguessr" alt="starify" />

## 📖 介绍

猜角色游戏！一个模仿 [anime-character-guessr](https://github.com/kennylimz/anime-character-guessr) 项目的 NoneBot2 插件，让你在聊天环境中猜二次元角色。

游戏规则：

1. 机器人会随机选择一个动漫角色
2. 玩家通过猜测角色名来识别这个神秘角色
3. 每次猜测后会显示角色的特征比较，帮助玩家缩小范围
4. 成功猜对或放弃时游戏结束

插件特点：

- 数据来源于 Bangumi 和萌娘百科
- 丰富的角色库和特征标签
- 简单易用的命令系统
- 直观的反馈提示（使用颜色和方向指示符）

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-aniguessr --upgrade

使用 **pypi** 源安装

    nb plugin install nonebot-plugin-aniguessr --upgrade -i "https://pypi.org/simple"

使用**清华源**安装

    nb plugin install nonebot-plugin-aniguessr --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-aniguessr

安装仓库 master 分支

    uv add git+https://github.com/X-Zero-L/nonebot-plugin-aniguessr@master

</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-aniguessr

安装仓库 master 分支

    pdm add git+https://github.com/X-Zero-L/nonebot-plugin-aniguessr@master

</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-aniguessr

安装仓库 master 分支

    poetry add git+https://github.com/X-Zero-L/nonebot-plugin-aniguessr@master

</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_aniguessr"]

</details>

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的配置项（全部为可选）：

|         配置项         | 必填 | 默认值 |                  说明                  |
| :--------------------: | :--: | :----: | :------------------------------------: |
|   aniguessr_data_dir   |  否  |   ""   | 角色数据目录路径，留空使用插件内置数据 |
|  aniguessr_max_hints   |  否  |   3    |        游戏开始时提供的提示数量        |
| aniguessr_max_attempts |  否  |   10   |    最大猜测次数，超过后游戏自动结束    |
|   aniguessr_timeout    |  否  |  300   |   游戏超时时间（秒），超过后自动结束   |
|  aniguessr_min_attrs   |  否  |   5    | 角色最少需要有多少个属性才会被纳入游戏 |

## 🎉 使用

### 指令表

|     指令      |  权限  | 需要@ |   范围    |          说明          |
| :-----------: | :----: | :---: | :-------: | :--------------------: |
|  /aniguessr   | 所有人 |  否   | 私聊/群聊 | 开始一个新的猜角色游戏 |
| /aniguessr -h | 所有人 |  否   | 私聊/群聊 |      显示帮助信息      |
| /guess 角色名 | 所有人 |  否   | 私聊/群聊 |      猜测一个角色      |
|    /giveup    | 所有人 |  否   | 私聊/群聊 | 放弃当前游戏并显示答案 |

### 别名

- /aniguessr: /角色猜猜, /猜角色, /猜猜角色
- /guess: /猜, /g
- /giveup: /放弃, /gg

### 🎨 游戏效果

游戏流程示例：

1. 用户发送 `/aniguessr` 开始游戏
2. 机器人随机选择一个角色，并提供初始提示：

   ```
   游戏开始！我已经选择了一个神秘角色，请使用 /guess 角色名 来猜测。
   提示：这个角色可能的特征包括：学生, 双马尾, 傲娇
   ```

3. 用户发送 `/guess 御坂美琴` 进行猜测
4. 机器人返回猜测结果：

   ```
   第 1 次猜测：御坂美琴

   🟢 学生: 学生
   🟡 双马尾: 双马尾
   ❌ 傲娇: 目标角色不具有此特征
   🟢 电系能力: 电系能力
   ❌ 三无: 目标角色不具有此特征
   ```

5. 用户继续猜测，直到猜对或放弃：
   ```
   恭喜你猜对了！正确角色是：白井黑子
   你总共猜了 3 次
   ```

### 反馈指示符说明

- 🟢 绿色：完全匹配的特征
- 🟡 黄色：类似但不完全相同的特征
- ⬆️ 向上：目标角色的数值属性更高（例如年龄、身高等）
- ⬇️ 向下：目标角色的数值属性更低
- ❌ 红色：完全不同或不存在的特征
