// cmd/claw/main.go
package main

import (
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/larksuite/oapi-sdk-go/v3/core/httpserverext"
	"github.com/liushiju/go-tiny-claw/internal/engine"
	"github.com/liushiju/go-tiny-claw/internal/feishu"
	"github.com/liushiju/go-tiny-claw/internal/provider"
	"github.com/liushiju/go-tiny-claw/internal/tools"
)

func main() {
	// 1. 初始化引擎依赖
	workDir, _ := os.Getwd()

	// 默认使用智谱 GLM-4
	if strings.TrimSpace(os.Getenv("ZHIPU_API_KEY")) == "" {
		log.Fatal("请先导出 ZHIPU_API_KEY 环境变量")
	}
	llmProvider := provider.NewZhipuOpenAIProvider("glm-4.5-air")

	registry := tools.NewRegistry()
	registry.Register(tools.NewReadFileTool(workDir))
	registry.Register(tools.NewWriteFileTool(workDir))
	registry.Register(tools.NewBashTool(workDir))
	registry.Register(tools.NewEditFileTool(workDir))

	// 开启慢思考
	eng := engine.NewAgentEngine(llmProvider, registry, workDir, true)

	// 2. 初始化飞书 Bot 调度器
	bot := feishu.NewFeishuBot(eng)
	handler := httpserverext.NewEventHandlerFunc(bot.GetEventDispatcher())

	// 3. 注册路由并启动 HTTP 服务
	http.HandleFunc("/webhook/event", func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			log.Printf("[Webhook] 读取请求体失败: method=%s path=%s err=%v\n", r.Method, r.URL.Path, err)
			http.Error(w, "failed to read request body", http.StatusInternalServerError)
			return
		}

		log.Printf("[Webhook] 收到请求: method=%s path=%s content_length=%d headers=%v body=%s\n", r.Method, r.URL.Path, len(body), r.Header, string(body))

		r.Body = io.NopCloser(strings.NewReader(string(body)))
		handler(w, r)
	})

	port := ":48080"
	log.Printf("🚀 go-tiny-claw 飞书服务端已启动，正在监听 %s 端口\n", port)

	err := http.ListenAndServe(port, nil)
	if err != nil {
		log.Fatalf("服务器启动失败: %v", err)
	}
}
