// internal/feishu/bot.go
package feishu

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	"github.com/larksuite/oapi-sdk-go/v3/event/dispatcher"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"
	"github.com/liushiju/go-tiny-claw/internal/engine"
)

// FeishuBot 封装了飞书机器人的配置与核心业务流
type FeishuBot struct {
	client    *lark.Client
	appID     string
	appSecret string
	engine    *engine.AgentEngine // 持有核心引擎引用
}

func NewFeishuBot(eng *engine.AgentEngine) *FeishuBot {
	appID := strings.TrimSpace(os.Getenv("FEISHU_APP_ID"))
	appSecret := strings.TrimSpace(os.Getenv("FEISHU_APP_SECRET"))

	if appID == "" || appSecret == "" {
		log.Fatal("请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
	}

	// 实例化飞书官方客户端
	client := lark.NewClient(appID, appSecret)

	return &FeishuBot{
		client:    client,
		appID:     appID,
		appSecret: appSecret,
		engine:    eng,
	}
}

// GetEventDispatcher 用于注册到 HTTP 服务器，处理来自飞书的 POST 事件
func (b *FeishuBot) GetEventDispatcher() *dispatcher.EventDispatcher {
	encryptKey := strings.TrimSpace(os.Getenv("FEISHU_ENCRYPT_KEY"))
	verifyToken := strings.TrimSpace(os.Getenv("FEISHU_VERIFY_TOKEN"))

	if verifyToken == "" {
		log.Fatal("请设置 FEISHU_VERIFY_TOKEN，并确保它与飞书事件订阅配置页中的 Verification Token 完全一致")
	}

	// 使用官方 SDK 构建调度器，监听 "接收消息" 事件
	handler := dispatcher.NewEventDispatcher(verifyToken, encryptKey).
		OnP2MessageReceiveV1(func(ctx context.Context, event *larkim.P2MessageReceiveV1) error {
			if event == nil || event.Event == nil || event.Event.Message == nil {
				log.Printf("[Feishu] 收到空消息事件，忽略\n")
				return nil
			}

			rawContent := derefString(event.Event.Message.Content)
			contentStr := parseTextContent(rawContent)
			chatID := derefString(event.Event.Message.ChatId)
			messageType := derefString(event.Event.Message.MessageType)

			log.Printf("[Feishu] 收到消息事件: chat_id=%s, message_type=%s, raw_content=%s\n", chatID, messageType, rawContent)

			if chatID == "" {
				log.Printf("[Feishu] 消息事件缺少 chat_id，忽略\n")
				return nil
			}
			if strings.TrimSpace(contentStr) == "" {
				log.Printf("[Feishu] 暂不处理空文本或非 text 消息, chat_id=%s\n", chatID)
				return nil
			}

			// 【驾驭并发】：收到消息后，绝不能阻塞 HTTP 回调。
			// 我们要为每个请求开启一个独立的 Goroutine 跑 Agent 任务！
			go b.handleAgentRun(chatID, contentStr)

			return nil
		}).
		OnP2MessageReadV1(func(ctx context.Context, event *larkim.P2MessageReadV1) error {
			// 消息已读事件，静默忽略（避免日志干扰）
			return nil
		})

	return handler
}

// handleAgentRun 是连接飞书与底层引擎的桥梁
func (b *FeishuBot) handleAgentRun(chatId string, prompt string) {
    // 为当前聊天窗口实例化一个专属的 Reporter
    reporter := &FeishuReporter{
        client: b.client,
        chatId: chatId,
    }

    // 启动引擎！
    err := b.engine.Run(context.Background(), prompt, reporter)
    if err != nil {
        reporter.sendMsg(fmt.Sprintf("❌ Agent 运行崩溃: %v", err))
    }
}

// ==========================================
// FeishuReporter: 将引擎的输出格式化后发给飞书
// ==========================================
type FeishuReporter struct {
    client *lark.Client
    chatId string
}

// sendMsg 封装了调用飞书 OpenAPI 发送卡片/文本的操作
func (r *FeishuReporter) sendMsg(text string) {
	// 构建文本消息内容
	textContent := map[string]string{
		"text": text,
	}
	contentBytes, err := json.Marshal(textContent)
	if err != nil {
		log.Printf("[Feishu] 序列化消息失败: %v\n", err)
		return
	}

	msgReq := larkim.NewCreateMessageReqBuilder().
		ReceiveIdType(larkim.CreateMessageV1ReceiveIDTypeChatId).
		Body(larkim.NewCreateMessageReqBodyBuilder().
			ReceiveId(r.chatId).
			MsgType(larkim.MsgTypeText).
			Content(string(contentBytes)).
			Build()).
		Build()

	resp, err := r.client.Im.Message.Create(context.Background(), msgReq)
	if err != nil {
		log.Printf("[Feishu] 发送消息请求失败, chat_id=%s: %v\n", r.chatId, err)
		return
	}
	if !resp.Success() {
		log.Printf("[Feishu] 发送消息失败, chat_id=%s, code=%d, msg=%s, request_id=%s\n", r.chatId, resp.Code, resp.Msg, resp.RequestId())
		return
	}
	log.Printf("[Feishu] 发送消息成功, chat_id=%s, message_id=%s\n", r.chatId, derefString(resp.Data.MessageId))
}

func (r *FeishuReporter) OnThinking(ctx context.Context) {
    // 仅发一个轻量级提示，避免飞书刷屏
    r.sendMsg("🤔 模型正在慢思考 (Thinking)...")
}

func (r *FeishuReporter) OnToolCall(ctx context.Context, toolName string, args string) {
    r.sendMsg(fmt.Sprintf("🛠️ **正在执行工具**：`%s`\n参数：`%s`", toolName, args))
}

func (r *FeishuReporter) OnToolResult(ctx context.Context, toolName string, result string, isError bool) {
    if isError {
        r.sendMsg(fmt.Sprintf("⚠️ **执行报错** (%s)：\n%s", toolName, result))
    } else {
        // 成功时仅汇报成功，不刷全量日志
        r.sendMsg(fmt.Sprintf("✅ **执行成功** (%s)", toolName))
    }
}

func (r *FeishuReporter) OnMessage(ctx context.Context, content string) {
    // 将模型最终的纯文本回答发给用户
    r.sendMsg(content)
}

// 编译时类型检查：确保 FeishuReporter 实现了 Reporter 接口
var _ engine.Reporter = (*FeishuReporter)(nil)

type textMessageContent struct {
	Text string `json:"text"`
}

func parseTextContent(raw string) string {
	var content textMessageContent
	if err := json.Unmarshal([]byte(raw), &content); err == nil && content.Text != "" {
		return content.Text
	}

	raw = strings.TrimPrefix(raw, `{"text":"`)
	raw = strings.TrimSuffix(raw, `"}`)
	return raw
}

func derefString(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}
