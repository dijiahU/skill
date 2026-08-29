#!/usr/bin/env bash
# security-hardening-safey/scripts/uninstall.sh
# 从所有 Agent 的 AGENTS.md 移除安全规则块，从 SOUL.md 移除安全边界注入
# 幂等安全，可重复运行

set -euo pipefail

OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
AGENTS_DIR="$OPENCLAW_DIR/agents"
START_MARKER="<!-- SECURITY-HARDENING:START -->"
END_MARKER="<!-- SECURITY-HARDENING:END -->"
SOUL_MARKER="## 安全边界（不可协商）"

removed=0
soul_removed=0
skipped=0

echo "========================================"
echo "  security-hardening-safey 卸载"
echo "========================================"
echo ""

for agent_dir in "$AGENTS_DIR"/*/; do
  [ -d "$agent_dir" ] || continue
  agent_name="$(basename "$agent_dir")"
  agents_md="$agent_dir/agent/AGENTS.md"
  soul_md="$agent_dir/agent/SOUL.md"

  # --- 处理 AGENTS.md ---
  if [ -f "$agents_md" ]; then
    if grep -qF "$START_MARKER" "$agents_md"; then
      tmp="$(mktemp)"
      # 删除从 START 到 END（含）之间的所有行，以及前后可能的空行
      awk -v start="$START_MARKER" -v end="$END_MARKER" '
        $0 == start { skip=1; next }
        skip && $0 == end { skip=0; next }
        !skip { print }
      ' "$agents_md" > "$tmp"
      # 去掉文件开头多余空行
      sed -i '/./,$!d' "$tmp"
      mv "$tmp" "$agents_md"
      echo "[REMOVED]  $agent_name/AGENTS.md"
      ((removed++)) || true
    else
      echo "[SKIP]     $agent_name/AGENTS.md（未注入，跳过）"
      ((skipped++)) || true
    fi
  fi

  # --- 处理 SOUL.md（注入始终在文件末尾，截断到标记行前即可）---
  if [ -f "$soul_md" ] && grep -qF "$SOUL_MARKER" "$soul_md"; then
    tmp="$(mktemp)"
    line_num=$(grep -n "$SOUL_MARKER" "$soul_md" | tail -1 | cut -d: -f1)
    # 若标记行前一行是空行，一并删除
    prev=$((line_num - 1))
    if [ "$prev" -gt 0 ] && [ -z "$(sed -n "${prev}p" "$soul_md")" ]; then
      line_num=$prev
    fi
    head -n $((line_num - 1)) "$soul_md" > "$tmp"
    mv "$tmp" "$soul_md"
    echo "[REMOVED]  $agent_name/SOUL.md（安全边界已移除）"
    ((soul_removed++)) || true
  fi

done

# 移除初始化标记
flag_file="$(dirname "$0")/../.initialized"
if [ -f "$flag_file" ]; then
  rm "$flag_file"
  echo ""
  echo "[REMOVED]  .initialized 标记"
fi

echo ""
echo "========================================"
echo "  AGENTS.md 已清理: $removed  SOUL.md 已清理: $soul_removed  跳过: $skipped"
echo "========================================"
echo ""
echo "规则注入已全部移除。如需重新注入，运行："
echo "  bash ~/.openclaw/skills/security-hardening-safey/scripts/init.sh"
