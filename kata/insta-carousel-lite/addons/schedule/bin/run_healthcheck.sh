#!/usr/bin/env bash
# run_healthcheck.sh - 週次システム点検を1回実行する（run-agent.sh への薄いラッパー）
# 実体は bin/run-agent.sh と .claude/orchestrators/healthcheck-orchestrator.md にある。
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run-agent.sh" healthcheck-orchestrator
