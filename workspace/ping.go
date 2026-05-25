package main

import (
	"encoding/json"
	"fmt"
	"net/http"
)

func main() {
	http.HandleFunc("/ping", pingHandler)
	
	fmt.Println("HTTP 服务器启动在端口 8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Println("服务器启动失败: " + err.Error())
	}
}

func pingHandler(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"code":    200,
		"message": "pong",
	}
	
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}