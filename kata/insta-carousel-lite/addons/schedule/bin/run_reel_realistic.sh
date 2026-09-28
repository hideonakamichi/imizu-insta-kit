#!/usr/bin/env bash
# run_reel_realistic.sh - リール投稿パイプラインを realistic スタイルで1回実行する
# 実体は bin/run-agent.sh と .claude/orchestrators/reel-realistic-orchestrator.md にある。
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run-agent.sh" reel-realistic-orchestrator
