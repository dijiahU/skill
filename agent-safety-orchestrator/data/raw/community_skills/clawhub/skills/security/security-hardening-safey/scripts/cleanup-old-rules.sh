#!/usr/bin/env bash
# cleanup-old-rules.sh
# 清理第一版注入的无块标记旧规则，保留 SECURITY-HARDENING:START/END 块 + 原始内容

set -euo pipefail

OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
AGENTS_DIR="$OPENCLAW_DIR/agents"
START_MARKER="<!-- SECURITY-HARDENING:START -->"
END_MARKER="<!-- SECURITY-HARDENING:END -->"
OLD_MARKER="## \[安全红线\] 最高优先级"

fixed=0
clean=0

for agents_md in "$AGENTS_DIR"/*/agent/AGENTS.md; do
  agent_name=$(echo "$agents_md" | sed "s|$AGENTS_DIR/||;s|/agent/AGENTS.md||")

  # 检查是否存在旧规则（有 START 标记但 END 后还有第二个 安全红线 节）
  if ! grep -qF "$START_MARKER" "$agents_md"; then
    echo "[SKIP]  $agent_name — 无块标记，跳过"
    ((clean++)) || true
    continue
  fi

  # 统计 安全红线 出现次数：> 1 说明有重复
  count=$(grep -cF "[安全红线]" "$agents_md" || true)
  if [ "$count" -le 1 ]; then
    echo "[OK]    $agent_name — 无重复"
    ((clean++)) || true
    continue
  fi

  tmp="$(mktemp)"

  # 策略：保留 START~END 块，然后跳过紧接着的旧规则块，直到遇到原始内容的一级标题
  awk -v start="$START_MARKER" -v end="$END_MARKER" '
    BEGIN { in_new=0; after_new=0; found_orig=0 }

    # 进入新规则块
    $0 ~ start { in_new=1; print; next }

    # 离开新规则块
    $0 ~ end   { in_new=0; after_new=1; print; next }

    # 在新规则块内：原样输出
    in_new { print; next }

    # 新规则块结束后、原始内容开始前：跳过旧规则（以 ## [安全红线] 开头的节，及其后到原始 # 标题前的内容）
    after_new && !found_orig {
      # 一级标题（# 开头，不是 ## 或 <!-- ）= 原始内容开始
      if (/^# [^#]/ && !/^\[安全/) {
        found_orig=1
        print
      }
      # 否则跳过（旧规则 + 分隔符）
      next
    }

    # 原始内容：原样输出
    found_orig { print }
  ' "$agents_md" > "$tmp"

  mv "$tmp" "$agents_md"
  echo "[FIXED] $agent_name — 旧规则已清理"
  ((fixed++)) || true
done

echo ""
echo "============================="
echo "  修复: $fixed  无需修复: $clean"
echo "============================="
