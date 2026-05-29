package main

import (
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// DonationChaincode 公益捐赠溯源链码
type DonationChaincode struct {
	contractapi.Contract
}

// DonationEvent 捐赠事件，对应区块链上的每条记录
type DonationEvent struct {
	TrackingID string `json:"tracking_id"` // 溯源码（唯一跟踪 ID）
	ItemType   string `json:"item_type"`   // 物品类型
	Condition  string `json:"condition"`   // 物品状况
	DonorName  string `json:"donor_name"`  // 脱敏后的捐赠者姓名
	PhotoHash  string `json:"photo_hash"`  // 照片 SHA-256 哈希（链下文件完整性验证）
	Status     string `json:"status"`      // 当前流转状态
	Note       string `json:"note"`        // 操作备注
	Receiver   string `json:"receiver"`    // 脱敏后的受赠者姓名（签收后写入）
	Timestamp  string `json:"timestamp"`   // 链码写入时间（UTC）
	EventType  string `json:"event_type"`  // 事件类型：donation / status_update / receipt
}

// 允许的状态集合（按正向流转顺序）
var validStates = []string{"待接收", "处理中", "已分拣", "运送中", "已签收"}

// validTransitions 定义合法的单向状态迁移
var validTransitions = map[string][]string{
	"待接收": {"处理中"},
	"处理中": {"运送中"},
	"运送中": {"已分拣", "已签收"},
	"已分拣": {"运送中"},
}

// nowUTC 返回当前 UTC 时间字符串
func nowUTC() string {
	return time.Now().UTC().Format("2006-01-02 15:04:05")
}

// isValidState 检查状态是否在合法集合中
func isValidState(state string) bool {
	for _, s := range validStates {
		if s == state {
			return true
		}
	}
	return false
}

// validateTransition 验证状态迁移合法性（单向、不可逆）
func validateTransition(current, next string) bool {
	allowed, ok := validTransitions[current]
	if !ok {
		return false
	}
	for _, status := range allowed {
		if status == next {
			return true
		}
	}
	return false
}

// ─────────────────────────────────────────────
// 链码函数
// ─────────────────────────────────────────────

// InitLedger 初始化账本
// 调用方式：peer chaincode invoke ... -c '{"function":"InitLedger","Args":[]}'
func (d *DonationChaincode) InitLedger(ctx contractapi.TransactionContextInterface) error {
	log.Println("[InitLedger] 公益捐赠溯源链码已初始化")
	return nil
}

// CreateDonation 新增捐赠登记事件（对应 CreateAsset）
// 调用方式：peer chaincode invoke ... -c '{"function":"CreateDonation","Args":["ID","衣物","完好","张**","abc123hash","备注"]}'
func (d *DonationChaincode) CreateDonation(
	ctx contractapi.TransactionContextInterface,
	trackingID, itemType, condition, donorName, photoHash, note string,
) error {
	// 幂等检查：同一 trackingID 不能重复创建
	existing, err := ctx.GetStub().GetState(trackingID)
	if err != nil {
		return fmt.Errorf("读取账本失败: %v", err)
	}
	if existing != nil {
		return fmt.Errorf("溯源码 %s 已存在，不能重复创建", trackingID)
	}

	event := DonationEvent{
		TrackingID: trackingID,
		ItemType:   itemType,
		Condition:  condition,
		DonorName:  donorName,
		PhotoHash:  photoHash,
		Status:     "待接收",
		Note:       note,
		Receiver:   "",
		Timestamp:  nowUTC(),
		EventType:  "donation",
	}

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("序列化失败: %v", err)
	}

	return ctx.GetStub().PutState(trackingID, data)
}

// UpdateStatus 更新捐赠物品状态（对应 UpdateAsset / TransferAsset）
// 调用方式：peer chaincode invoke ... -c '{"function":"UpdateStatus","Args":["ID","处理中","机构验收"]}'
func (d *DonationChaincode) UpdateStatus(
	ctx contractapi.TransactionContextInterface,
	trackingID, newStatus, note string,
) error {
	if !isValidState(newStatus) {
		return fmt.Errorf("非法状态: %s", newStatus)
	}

	data, err := ctx.GetStub().GetState(trackingID)
	if err != nil {
		return fmt.Errorf("读取账本失败: %v", err)
	}
	if data == nil {
		return fmt.Errorf("溯源码 %s 不存在", trackingID)
	}

	var event DonationEvent
	if err := json.Unmarshal(data, &event); err != nil {
		return fmt.Errorf("反序列化失败: %v", err)
	}

	// 状态机校验：只允许单向迁移
	if !validateTransition(event.Status, newStatus) {
		return fmt.Errorf("非法状态迁移: %s → %s", event.Status, newStatus)
	}

	event.Status = newStatus
	event.Note = note
	event.Timestamp = nowUTC()
	event.EventType = "status_update"

	updated, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("序列化失败: %v", err)
	}

	return ctx.GetStub().PutState(trackingID, updated)
}

// ConfirmReceipt 受赠方签收
// 调用方式：peer chaincode invoke ... -c '{"function":"ConfirmReceipt","Args":["ID","李**","签收确认"]}'
func (d *DonationChaincode) ConfirmReceipt(
	ctx contractapi.TransactionContextInterface,
	trackingID, receiverName, note string,
) error {
	data, err := ctx.GetStub().GetState(trackingID)
	if err != nil {
		return fmt.Errorf("读取账本失败: %v", err)
	}
	if data == nil {
		return fmt.Errorf("溯源码 %s 不存在", trackingID)
	}

	var event DonationEvent
	if err := json.Unmarshal(data, &event); err != nil {
		return fmt.Errorf("反序列化失败: %v", err)
	}

	if event.Status != "运送中" {
		return fmt.Errorf("物品尚未进入运送状态，当前状态：%s", event.Status)
	}

	event.Status = "已签收"
	event.Receiver = receiverName
	event.Note = note
	event.Timestamp = nowUTC()
	event.EventType = "receipt"

	updated, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("序列化失败: %v", err)
	}

	return ctx.GetStub().PutState(trackingID, updated)
}

// GetDonation 按溯源码查询最新状态
// 调用方式：peer chaincode query ... -c '{"Args":["GetDonation","ID"]}'
func (d *DonationChaincode) GetDonation(
	ctx contractapi.TransactionContextInterface,
	trackingID string,
) (*DonationEvent, error) {
	data, err := ctx.GetStub().GetState(trackingID)
	if err != nil {
		return nil, fmt.Errorf("读取账本失败: %v", err)
	}
	if data == nil {
		return nil, fmt.Errorf("溯源码 %s 不存在", trackingID)
	}

	var event DonationEvent
	if err := json.Unmarshal(data, &event); err != nil {
		return nil, fmt.Errorf("反序列化失败: %v", err)
	}
	return &event, nil
}

// GetAllDonations 查询账本中全部捐赠记录
// 调用方式：peer chaincode query ... -c '{"Args":["GetAllDonations"]}'
func (d *DonationChaincode) GetAllDonations(
	ctx contractapi.TransactionContextInterface,
) ([]*DonationEvent, error) {
	// 空键范围迭代器：返回账本中所有 KV
	iter, err := ctx.GetStub().GetStateByRange("", "")
	if err != nil {
		return nil, fmt.Errorf("获取迭代器失败: %v", err)
	}
	defer iter.Close()

	var results []*DonationEvent
	for iter.HasNext() {
		kv, err := iter.Next()
		if err != nil {
			return nil, fmt.Errorf("迭代失败: %v", err)
		}
		var event DonationEvent
		if err := json.Unmarshal(kv.Value, &event); err != nil {
			continue // 跳过无法解析的记录
		}
		results = append(results, &event)
	}
	return results, nil
}

// GetDonationHistory 查询某溯源码的完整历史记录
// 调用方式：peer chaincode query ... -c '{"Args":["GetDonationHistory","ID"]}'
// 利用 Fabric 原生的 GetHistoryForKey API，返回该 Key 上所有历史版本
func (d *DonationChaincode) GetDonationHistory(
	ctx contractapi.TransactionContextInterface,
	trackingID string,
) ([]map[string]interface{}, error) {
	iter, err := ctx.GetStub().GetHistoryForKey(trackingID)
	if err != nil {
		return nil, fmt.Errorf("获取历史记录失败: %v", err)
	}
	defer iter.Close()

	var history []map[string]interface{}
	for iter.HasNext() {
		mod, err := iter.Next()
		if err != nil {
			return nil, fmt.Errorf("迭代历史记录失败: %v", err)
		}

		entry := map[string]interface{}{
			"tx_id":     mod.TxId, // 交易 ID（Fabric 原生字段）
			"timestamp": time.Unix(mod.Timestamp.Seconds, 0).UTC().Format("2006-01-02 15:04:05"),
			"is_delete": mod.IsDelete,
		}

		if !mod.IsDelete {
			var event DonationEvent
			if err := json.Unmarshal(mod.Value, &event); err == nil {
				entry["event"] = event
				entry["status"] = event.Status
				entry["note"] = event.Note
			}
		}
		history = append(history, entry)
	}
	return history, nil
}

// ─────────────────────────────────────────────
// 入口
// ─────────────────────────────────────────────

func main() {
	cc, err := contractapi.NewChaincode(&DonationChaincode{})
	if err != nil {
		log.Fatalf("创建链码失败: %v", err)
	}
	if err := cc.Start(); err != nil {
		log.Fatalf("启动链码失败: %v", err)
	}
}
