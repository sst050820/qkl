# 区块链多品类捐赠全流程溯源系统

基于 Python Flask 的公益捐赠溯源系统，采用本地链上/链下结合设计，实现捐赠物资从发起、验收、分发、签收、查询的全流程记录与不可篡改校验。

## 项目结构

- `app.py` - Flask 应用入口，包含前端页面路由和业务流程。
- `blockchain.py` - 区块链仿真核心，包含区块结构、hash 计算、PoW 链式存储和数据持久化。
- `contracts.py` - 业务状态机规则，定义捐赠物品状态流转、状态校验和脱敏规则。
- `database.py` - 链下 SQLite 数据库操作，存储捐赠者信息和签收记录。
- `config.py` - 全局配置文件。
- `data/chain_data.json` - 本地保存区块链账本。
- `data/app.db` - 链下数据库文件。
- `templates/` - 前端页面模板。
- `static/` - 静态资源文件，包括样式与上传照片目录。

## 运行步骤

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 启动服务：

```bash
python app.py
```

3. 在浏览器访问：

```
http://127.0.0.1:5000
```

## 完整运行与测试步骤

### 环境准备

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 启动应用

```bash
# 方式1：开发模式（支持热重载）
python app.py

# 方式2：使用 Flask 命令行
export FLASK_APP=app.py
flask run
```

启动成功后，终端显示：
```
WARNING: This is a development server. Do not use it in production deployments.
Running on http://127.0.0.1:5000
```

### 完整业务流程测试

系统包含用户注册与登录模块：
- `/register` - 新用户注册，支持 `donor` 或 `recipient` 角色
- `/login` - 登录
- `/logout` - 退出登录
- `/user-portal` - 用户门户，根据登录角色显示不同入口

系统默认内置账号：
- 管理员：`admin` / `admin123`
- 捐赠者：`donor` / `donor123`
- 受赠者：`recipient` / `recipient123`

系统提供快捷入口：
- `/donor` 重定向到 `/donate`
- `/recipient` 重定向到 `/receive`

#### 1. 捐赠登记 (`/donate`)
- 登录后访问 http://127.0.0.1:5000/donate
- 填写捐赠者姓名（可选，支持匿名）
- 输入联系电话
- 选择物品类别（例如衣物、图书、生活用品、综合捐赠）
- 选择物品状况
- 上传物品照片（支持 PNG/JPG/GIF，单张≤5MB）
- 点击"提交捐赠"
- **预期结果**：页面显示"捐赠提交成功"与唯一的**溯源码**（10位大写字母数字组合）

#### 2. 首页查看 (`/`)
- 访问 http://127.0.0.1:5000/
- 可查看：
  - 当前区块高度
  - 已登记物品总数
  - 各状态物品数量统计
  - 链完整性校验状态
  - 最新链上活动时间轴

#### 3. 机构管理 (`/admin`)
- 登录管理员账号后访问 http://127.0.0.1:5000/admin
- 按溯源码、物品类型或捐赠者搜索
- 按状态筛选（待接收、处理中、已分拣、运送中、已签收）
- 点击对应物品的"更新为 [下一状态]"按钮逐步推进
- **预期流转**：待接收 → 处理中 → 已分拣 → 运送中 → 已签收

#### 4. 签收确认 (`/receive`)
- 登录受赠者账号后访问 http://127.0.0.1:5000/receive
- 输入溯源码查询物品
- 查看物品照片、状态、捐赠者信息
- **仅当物品状态为"运送中"时**，表单才可用于签收
- 填写受赠方姓名、编号、地址
- 点击"确认签收"完成闭环
- **预期结果**：物品状态变为"已签收"，流程完成

#### 5. 实时溯源 (`/track`)
- 访问 http://127.0.0.1:5000/track
- 输入溯源码查询
- 查看：
  - 物品照片
  - 完整流转时间轴（从捐赠至签收）
  - 每个节点的时间戳、状态、备注
  - 链完整性校验标志
  - 签收方信息（如已签收）

### 数据持久化

系统生成的数据存储位置：

```
blockchain/
├── data/
│   ├── chain_data.json      # 区块链账本（不可篡改）
│   └── app.db               # SQLite 数据库（捐赠者、受赠方信息）
├── static/uploads/          # 上传的物品照片
```

清除测试数据：

```bash
# 完全重置系统（谨慎操作）
rm -rf data/chain_data.json data/app.db static/uploads/*
```

## 网络访问与部署

### 本地网络访问

`app.py` 默认已配置为监听 `0.0.0.0:5000`，如果使用 `python app.py` 启动，局域网内其他设备即可访问。

如果使用 Flask CLI 启动，请指定主机地址：

```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5000
```

启动后，其他设备可通过以下方式访问：

```
http://192.168.140.133:5000
```

获取IP地址：

```bash
# Linux/Mac
ip addr | grep 'inet ' | grep -v 127.0.0.1

# Windows
ipconfig
```

### 生产环境建议

```bash
# 使用 Gunicorn（推荐）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 使用 uWSGI
pip install uwsgi
uwsgi --http :5000 --wsgi-file app.py --callable app
```


## 功能说明

- `donate.html` - 捐赠登记页面，上传照片并生成唯一溯源码。
- `admin.html` - 公益机构验收与状态更新页面，支持溯源码搜索和状态筛选。
- `receive.html` - 受赠方签收确认页面，完成多方闭环并展示当前签收条件。
- `track.html` - 溯源查询页面，展示物品全流程时间轴、捐赠照片与签收详情。

## 核心特色

- **链上链下分离**：大文件与隐私信息链下保存，链上只存哈希与状态。
- **状态机流转**：物品状态只能由 `待接收 → 处理中 → 已分拣 → 运送中 → 已签收` 单向流转，防止逆向篡改。
- **数据脱敏**：捐赠方/受赠方信息在链上展示脱敏结果，真实信息仅保存在链下数据库，保护隐私。
- **本地持久化**：区块链账本保存为 `data/chain_data.json`，链下数据保存为 `data/app.db`。
- **哈希校验**：每个物品照片计算 SHA-256 哈希，链上存储哈希值，确保照片完整性。
- **工作量证明（PoW）**：链上每个区块需完成 3 位难度的 PoW，增加防篡改难度。
- **可视化时间轴**：溯源查询支持时间轴展示，直观呈现物品全流程。
- **搜索与筛选**：机构管理端支持按溯源码、物品类型、捐赠者搜索，按状态筛选。

## 技术栈

- **后端**：Python Flask
- **数据库**：SQLite（链下数据）、JSON（区块链账本）
- **前端**：HTML5 + CSS3 + JavaScript
- **加密**：SHA-256（哈希）
- **状态管理**：有限状态机（FSM）

## 依赖

- Flask
- Werkzeug（文件上传安全处理）

查看完整依赖：

```bash
cat requirements.txt
```

## 常见问题

### Q1: 系统能处理多少捐赠记录？
A: 本地系统基于 JSON 账本存储，理论上无限制。但建议单个账本≤1000 个物品时归档新账本以保证性能。

### Q2: 能否修改已上链的记录？
A: **不能**。区块链的不可篡改特性保证了每条记录的真实性。若需更正，只能添加新的操作记录。

### Q3: 照片存在哪里？
A: 照片存储在 `static/uploads/` 目录，文件名为 `[溯源码]_[原始文件名]`。链上只存储照片的 SHA-256 哈希值。

### Q4: 如何备份数据？
A: 备份 `data/` 文件夹与 `static/uploads/` 文件夹即可完整备份所有数据。

### Q5: 支持多用户并发吗？
A: 开发模式不支持。生产环境需使用 Gunicorn + Nginx 等部署方案实现并发支持。

## 贡献与反馈

本项目为公益捐赠溯源系统原型。欢迎提出改进意见或代码贡献！

---

**最后更新**：2026 年 5 月 8 日