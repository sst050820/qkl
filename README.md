# 区块链多品类捐赠全流程溯源系统

基于 Python Flask 的公益捐赠溯源系统，结合本地链上账本与 Hyperledger Fabric 链码查询，支持捐赠登记、验收、分发、签收、溯源查询等业务流程。

## 项目结构

- `app.py` - Flask 应用入口，包含前端页面路由与业务流程。
- `blockchain.py` - 本地区块链仿真核心，包含区块结构、哈希计算、PoW 链式存储与数据持久化。
- `contracts.py` - 业务状态机规则，定义捐赠物品状态流转、校验与脱敏逻辑。
- `database.py` - 链下 SQLite 存储，保存捐赠者信息、签收信息与用户账户。
- `config.py` - 全局配置与 Fabric 环境参数。
- `data/chain_data.json` - 本地链上账本数据。
- `data/app.db` - 链下 SQLite 数据库文件。
- `templates/` - 前端页面模板。
- `static/` - 静态资源及上传照片目录。
- `fabric/Donation.go` - 自定义 Hyperledger Fabric 链码源代码。

## 快速开始

### 1. Python 环境准备

```bash
cd /home/sitong/qkl
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动 Flask 应用

```bash
cd /home/sitong/qkl
python app.py
```

在浏览器打开：

```
http://127.0.0.1:5000
```

### 3. 访问页面

- 首页：`/`
- 捐赠登记：`/donate`
- 机构管理：`/admin`
- 签收确认：`/receive`
- 溯源查询：`/track`

## Fabric 环境搭建与链码部署

本项目使用 `~/HyperledgerFabric/fabric-samples/test-network` 作为 Fabric 运行时，链码目录位于 `~/qkl/fabric`。

### 1. 准备 Fabric 网络目录

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
```

### 2. 启动测试网络

```bash
./network.sh up createChannel -c mychannel -ca
```

如果网络已启动，可跳过此步。

### 3. 打包并部署自定义链码

当前环境中，链码名称为 `donation`。使用如下命令部署 `qkl/fabric/Donation.go`：

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
./network.sh deployCC -ccn donation -ccv 3.0 -c mychannel -ccp /home/sitong/qkl/fabric -ccl go
```

> 注：当前已部署版本为 `3.0`，如果你希望使用其它版本，请将 `-ccv` 改为对应版本；确保 `peer lifecycle chaincode querycommitted` 返回正确提交信息。

### 4. 验证链码提交

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
setGlobals 1
~/HyperledgerFabric/fabric-samples/bin/peer lifecycle chaincode querycommitted --channelID mychannel --name donation
```

你应当看到类似：

```
Committed chaincode definition for chaincode 'donation' on channel 'mychannel':
Version: 3.0, Sequence: 2, Endorsement Plugin: escc, Validation Plugin: vscc, Approvals: [Org1MSP: true, Org2MSP: true]
```

## Fabric 链码调用与查询命令

### 1. 查询链码元数据

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
setGlobals 1
~/HyperledgerFabric/fabric-samples/bin/peer chaincode query -C mychannel -n donation -c '{"Args":["org.hyperledger.fabric:GetMetadata"]}'
```

### 2. 查询所有捐赠记录

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
setGlobals 1
~/HyperledgerFabric/fabric-samples/bin/peer chaincode query -C mychannel -n donation -c '{"function":"GetAllDonations","Args":[]}'
```

### 3. 通过链码写入一条测试捐赠记录

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
setGlobals 1
~/HyperledgerFabric/fabric-samples/bin/peer chaincode invoke \
  -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --tls \
  --cafile /home/sitong/HyperledgerFabric/fabric-samples/test-network/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem \
  --peerAddresses localhost:7051 \
  --tlsRootCertFiles /home/sitong/HyperledgerFabric/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem \
  -C mychannel -n donation \
  -c '{"function":"CreateDonation","Args":["TEST01","衣物","完好","张三","abc123","测试捐赠"]}'
```

> 如果部署时启用了 TLS，请务必传入 `--tls`、`--cafile`、`--peerAddresses` 以及 `--tlsRootCertFiles`。

### 4. 查询 Fabric 账本中的指定捐赠记录

如果你的链码实现支持以 `GetDonation` 或类似函数查询单条记录，可以使用：

```bash
~/HyperledgerFabric/fabric-samples/bin/peer chaincode query -C mychannel -n donation -c '{"Args":["GetDonation","TEST01"]}'
```

如果链码只支持 `GetAllDonations`，则直接查询所有记录并在结果中查找即可。

## qkl 应用中的 Fabric 集成

### 1. 打开 `config.py`

确认以下配置项正确：

- `FABRIC_ENABLED = True`
- `FABRIC_PEER_BIN_PATH` 指向 `~/HyperledgerFabric/fabric-samples/bin/peer`
- `FABRIC_CHANNEL` 为 `mychannel`
- `FABRIC_CHAINCODE_NAME` 为 `donation`
- `FABRIC_LOCALMSPID` 为 `Org1MSP`
- `FABRIC_MSPCONFIGPATH` 为 `/home/sitong/HyperledgerFabric/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp`
- `FABRIC_TLS_ROOTCERT_FILE` 为 `/home/sitong/HyperledgerFabric/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem`

### 2. 启动前设置环境变量

```bash
cd /home/sitong/qkl
export FABRIC_PEER_BIN_PATH=/home/sitong/HyperledgerFabric/fabric-samples/bin/peer
export FABRIC_CHANNEL=mychannel
export FABRIC_CHAINCODE_NAME=donation
export FABRIC_LOCALMSPID=Org1MSP
export FABRIC_MSPCONFIGPATH=/home/sitong/HyperledgerFabric/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export FABRIC_TLS_ROOTCERT_FILE=/home/sitong/HyperledgerFabric/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem
export FABRIC_TLS_ENABLED=true
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
```

然后启动应用：

```bash
python app.py
```

### 3. 验证应用是否连接 Fabric

- 在 `app.py` 中访问链码查询接口或 `ledger` 页面
- 检查终端日志，确认 `peer` 命令调用成功
- 如果出现 `Function ... not found in contract SmartContract`，说明当前链码包与调用函数不匹配，需重新部署 `Donation.go` 并确认 `donation` 合约名称

## 业务测试流程

### 1. 捐赠登记流程

1. 登录或注册捐赠者用户
2. 在 `/donate` 提交捐赠信息与照片
3. 记录页面返回的溯源码
4. 观察 `data/chain_data.json` 中新增块与交易日志

### 2. 机构验收 & 状态更新

1. 使用管理员账号登录 `/admin`
2. 搜索溯源码或按状态筛选
3. 点击“更新为下一状态”按钮，完成状态流转
4. 检查本地链上账本 `data/chain_data.json` 是否新增状态变更记录

### 3. 受赠者签收

1. 登录受赠者账号访问 `/receive`
2. 输入溯源码查询记录
3. 仅当状态为“运送中”时，填写签收信息并提交
4. 验证状态变更为“已签收”并生成完整溯源纪录

### 4. 溯源查询

1. 访问 `/track`
2. 输入溯源码
3. 查看全流程时间轴、当前状态、照片和签收信息

## 本地账本与 Fabric 账本对比

- `data/chain_data.json`：应用本地链上账本，保存捐赠与状态变更记录。
- Fabric `donation` 链码账本：如果启用 Fabric，可在 `peer chaincode query` 中查询 Fabric 账本内容。

### Fabric 账本查询命令示例

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
setGlobals 1
~/HyperledgerFabric/fabric-samples/bin/peer chaincode query -C mychannel -n donation -c '{"function":"GetAllDonations","Args":[]}'
```

如果链码已正确部署，输出中会包含当前所有捐赠记录。

## 常见问题

### 1. 为什么 Fabric 查询报 `Function ... not found in contract SmartContract`？

这通常表示当前安装的链码不是你期望的 `Donation.go` 合约，或者链码包仍然是旧的 sample 合约。

解决方法：

1. 重新打包并部署 `~/qkl/fabric/Donation.go`
2. 确保 `peer lifecycle chaincode querycommitted` 返回 `donation` 的版本与序列号正确
3. 使用 `org.hyperledger.fabric:GetMetadata` 验证当前链码合约名称

### 2. 如何确认 Fabric 环境变量正确？

- `FABRIC_CFG_PATH` 应指向 `~/HyperledgerFabric/fabric-samples/config`
- `FABRIC_MSPCONFIGPATH` 应指向 Admin MSP
- `FABRIC_TLS_ROOTCERT_FILE` 应指向 org1 TLS CA 证书
- 运行 `. scripts/envVar.sh` 与 `setGlobals 1` 后，`peer` 命令应正常执行

### 3. 如何重置 Fabric 网络？

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
./network.sh down
rm -rf organizations/peerOrganizations organizations/ordererOrganizations channel-artifacts
./network.sh up createChannel -c mychannel -ca
```

## 贡献与反馈

如果你对系统功能、Fabric 集成或链码实现有改进建议，欢迎提交 issue 或 PR。
---

**最后更新**：2026 年 5 月 8 日

## 关闭运行中的代码与环境

在开发或演示结束后，可以使用以下命令安全地停止应用程序、Fabric 测试网络及清理环境变量与临时文件。

- 停止 Flask 应用（如果在前台运行，直接按 Ctrl+C；若在后台运行可用 pid 停止）:

```bash
# 在前台运行时（按 Ctrl+C）
# 若通过 nohup 或 & 后台启动，可用下面方式查找并终止
ps aux | grep 'python.*app.py' | grep -v grep
kill <PID>
# 或强制结束
kill -9 <PID>
```

- 退出 Python 虚拟环境:

```bash
deactivate
```

- 清理并停止 Fabric test-network:

```bash
cd /home/sitong/HyperledgerFabric/fabric-samples/test-network
export FABRIC_CFG_PATH=/home/sitong/HyperledgerFabric/fabric-samples/config
. scripts/envVar.sh
# 停止并清理网络（会删除渠道和组织证书等本地产物）
./network.sh down
# 可选：完全移除生成的组织与通道产物（谨慎）
rm -rf organizations/peerOrganizations organizations/ordererOrganizations channel-artifacts crypto-config
```

- 若使用 peer 进程或 orderer 进程残留（很少见），终止它们：

```bash
ps aux | egrep 'orderer|peer' | grep -v grep
kill <ORDERER_OR_PEER_PID>
```

- 取消导出的 Fabric 相关环境变量（仅当前 shell 会话）：

```bash
unset FABRIC_CFG_PATH
unset FABRIC_PEER_BIN_PATH
unset FABRIC_MSPCONFIGPATH
unset FABRIC_TLS_ROOTCERT_FILE
unset FABRIC_CHANNEL
unset FABRIC_CHAINCODE_NAME
unset FABRIC_LOCALMSPID
unset FABRIC_TLS_ENABLED
```

- 额外：如果链码已安装并需要重新部署，可在 test-network 中使用 `network.sh` 的相关命令重新安装/升级链码（见上面的部署步骤）。
