#!/usr/bin/env bash
# run_banner.sh - バナー投稿パイプラインを1回実行する（run-agent.sh への薄いラッパー）
# 実体は bin/run-agent.sh と .claude/orchestrators/banner-orchestrator.md にある。
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run-agent.sh" banner-orchestrator
