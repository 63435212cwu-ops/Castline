#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 模块模型与地址兼容性全面单元测试套件"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import serve


def run_tests():
    passed = 0
    total = 0

    def check(name, cond):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            assert False, f"Test failed: {name}"

    print("\n--- 1. 地址智能规范化 (normalize_base_url) ---")
    check("OpenAI 域名自动补 /v1", serve.normalize_base_url("https://api.openai.com") == "https://api.openai.com/v1")
    check("OpenAI 已带 /v1 不重复", serve.normalize_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1")
    check("去除末尾 /chat/completions", serve.normalize_base_url("https://api.openai.com/v1/chat/completions") == "https://api.openai.com/v1")
    check("DeepSeek 域名自动补 /v1", serve.normalize_base_url("https://api.deepseek.com") == "https://api.deepseek.com/v1")
    check("Ollama 11434 自动补 /v1", serve.normalize_base_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434/v1")
    check("Groq 域名自动补 /v1", serve.normalize_base_url("https://api.groq.com/openai") == "https://api.groq.com/openai")
    check("Anthropic 去除 /v1/messages", serve.normalize_base_url("https://api.anthropic.com/v1/messages", "anthropic") == "https://api.anthropic.com")
    check("Anthropic 去除 /v1", serve.normalize_base_url("https://api.anthropic.com/v1", "anthropic") == "https://api.anthropic.com")

    print("\n--- 2. OpenAI 完整 Chat 请求地址构建 (build_chat_url) ---")
    check("标准 /v1 接入", serve.build_chat_url("https://api.openai.com/v1") == "https://api.openai.com/v1/chat/completions")
    check("用户误粘 /chat/completions 不重复", serve.build_chat_url("https://api.openai.com/v1/chat/completions") == "https://api.openai.com/v1/chat/completions")
    check("去除引号与尾部斜杠", serve.build_chat_url(" 'https://my-proxy.com/v1/' ") == "https://my-proxy.com/v1/chat/completions")

    print("\n--- 3. Anthropic 完整 Messages 请求地址构建 (build_anthropic_url) ---")
    check("官方根域名", serve.build_anthropic_url("https://api.anthropic.com") == "https://api.anthropic.com/v1/messages")
    check("带 /v1 地址", serve.build_anthropic_url("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1/messages")
    check("用户误粘 /v1/messages 不重复", serve.build_anthropic_url("https://api.anthropic.com/v1/messages") == "https://api.anthropic.com/v1/messages")

    print("\n--- 4. 模型类别智能推断优先级 (model_class) ---")
    check("gpt-4o 为通用型", serve.model_class("gpt-4o") == "standard")
    check("gpt-4o-mini 为快速型", serve.model_class("gpt-4o-mini") == "flash")
    check("o1 为推理型", serve.model_class("o1") == "reasoning")
    check("o3-mini 为推理型", serve.model_class("o3-mini") == "reasoning")
    check("deepseek-chat 为通用型", serve.model_class("deepseek-chat") == "standard")
    check("deepseek-reasoner 为推理型", serve.model_class("deepseek-reasoner") == "reasoning")
    check("gemini-2.5-flash 为快速型", serve.model_class("gemini-2.5-flash") == "flash")
    check("gemini-2.0-flash-thinking-exp 思考型优先判定为推理型", serve.model_class("gemini-2.0-flash-thinking-exp") == "reasoning")
    check("claude-3-7-sonnet 为推理型", serve.model_class("claude-3-7-sonnet-20250219") == "reasoning")
    check("claude-3-5-haiku 为快速型", serve.model_class("claude-3-5-haiku-20241022") == "flash")
    check("qwq-32b 为推理型", serve.model_class("qwq-32b-preview") == "reasoning")
    check("qwen-max 为推理型", serve.model_class("qwen-max") == "reasoning")
    check("qwen-turbo 为快速型", serve.model_class("qwen-turbo") == "flash")

    print(f"\n结果: {passed}/{total} 全部通过 ✅\n")


if __name__ == "__main__":
    run_tests()
