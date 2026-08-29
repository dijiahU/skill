#!/bin/bash
# Script: run-scans.sh
# Runs available security scanning tools and outputs structured markdown.
# Usage: run-scans.sh [--full] [--strict] [directory]
#   --full      Explicitly scan the entire directory tree (default behaviour).
#               Pass this flag to make the intent clear when calling from a
#               larger workflow that also uses diff-scoped reviews.
#   --strict    Exit with non-zero code when findings are detected.
#               Useful for CI gates and pre-commit hooks.
# Exit code: 0 for scan results/findings; non-zero for invalid invocation or findings (with --strict)

set -uo pipefail

FULL_SCAN=false
STRICT_MODE=false
SCAN_DIR="."

# --- Argument parsing ---

while [[ $# -gt 0 ]]; do
	case "$1" in
	--full)
		FULL_SCAN=true
		shift
		;;
	--strict)
		STRICT_MODE=true
		shift
		;;
	-*)
		echo "Unknown option: $1" >&2
		exit 1
		;;
	*)
		if [[ "${SCAN_DIR}" != "." ]]; then
			echo "Error: only one directory argument is allowed (got extra: $1)" >&2
			exit 1
		fi
		SCAN_DIR="$1"
		shift
		;;
	esac
done

cd "${SCAN_DIR}" || exit 0

TOOLS_RUN=0
TOOLS_SKIPPED=0
TOOLS_WITH_FINDINGS=0
SKIPPED_TOOLS=()

# --- Helpers ---

run_tool() {
	local name="$1"
	shift
	local cmd=("$@")

	if ! command -v "${cmd[0]}" >/dev/null 2>&1; then
		TOOLS_SKIPPED=$((TOOLS_SKIPPED + 1))
		SKIPPED_TOOLS+=("${name}")
		echo ""
		echo "## Tool: ${name}"
		echo ""
		echo "**Status**: Skipped (not installed)"
		echo ""
		return
	fi

	TOOLS_RUN=$((TOOLS_RUN + 1))
	echo ""
	echo "## Tool: ${name}"
	echo ""
	echo "**Status**: Ran"
	echo ""

	local output
	local exit_code
	output=$("${cmd[@]}" 2>&1) || exit_code=$?
	exit_code=${exit_code:-0}

	if [[ -z ${output} ]]; then
		echo "No issues found."
	else
		echo '```'
		echo "${output}"
		echo '```'
		# Only count as findings if tool exited non-zero (indicates actual issues)
		if [[ ${exit_code} -ne 0 ]]; then
			TOOLS_WITH_FINDINGS=$((TOOLS_WITH_FINDINGS + 1))
		fi
	fi
	echo ""
}

is_skipped() {
	local needle="$1"
	local item
	for item in "${SKIPPED_TOOLS[@]}"; do
		[[ ${item} == "${needle}" ]] && return 0
	done
	return 1
}

# --- Header ---

SCAN_PWD="$(pwd)"
SCAN_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SCAN_MODE="full"
if [[ "${FULL_SCAN}" == "true" ]]; then
	SCAN_MODE="full (--full)"
fi

echo "# Security Scan Results"
echo ""
echo "**Directory**: \`${SCAN_PWD}\`"
echo "**Date**: ${SCAN_DATE}"
echo "**Mode**: ${SCAN_MODE}"

# --- Universal Scanners ---

# gitleaks - secret detection in git history and working tree
run_tool "gitleaks" gitleaks detect --no-banner --no-git -v

# semgrep - static analysis with auto-configured OWASP rules
run_tool "semgrep" semgrep scan --config=auto --quiet --no-git-ignore --error

# grype - filesystem vulnerability scanning
run_tool "grype" grype dir:. -q

# --- Language-Specific Scanners ---

# Node.js / TypeScript
if [[ -f "package.json" ]]; then
	run_tool "npm audit" npm audit --omit=dev
fi

# Python
if [[ -f "requirements.txt" ]] || [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]]; then
	run_tool "bandit" bandit -r . -q --severity-level medium
	run_tool "pip-audit" pip-audit
fi

# Go
if [[ -f "go.mod" ]]; then
	run_tool "gosec" gosec -quiet ./...
	run_tool "govulncheck" govulncheck ./...
fi

# Rust
if [[ -f "Cargo.toml" ]]; then
	run_tool "cargo audit" cargo audit
fi

# Ruby
if [[ -f "Gemfile" ]]; then
	run_tool "bundle-audit" bundle-audit check --update
fi

# --- Summary ---

echo "---"
echo ""
echo "## Summary"
echo ""
echo "- **Tools run**: ${TOOLS_RUN}"
echo "- **Tools skipped**: ${TOOLS_SKIPPED}"
echo "- **Tools with findings**: ${TOOLS_WITH_FINDINGS}"

if [[ ${#SKIPPED_TOOLS[@]} -gt 0 ]]; then
	echo ""
	echo "### Install missing tools"
	echo ""
	for tool in gitleaks semgrep grype bandit pip-audit gosec govulncheck "cargo audit" bundle-audit; do
		if is_skipped "${tool}"; then
			# shellcheck disable=SC2016
			case "${tool}" in
			gitleaks) echo '- `gitleaks`: `brew install gitleaks`' ;;
			semgrep) echo '- `semgrep`: `brew install semgrep` or `pip install semgrep`' ;;
			grype) echo '- `grype`: `brew install grype`' ;;
			bandit) echo '- `bandit`: `pip install bandit`' ;;
			pip-audit) echo '- `pip-audit`: `pip install pip-audit`' ;;
			gosec) echo '- `gosec`: `go install github.com/securego/gosec/v2/cmd/gosec@latest`' ;;
			govulncheck) echo '- `govulncheck`: `go install golang.org/x/vuln/cmd/govulncheck@latest`' ;;
			"cargo audit") echo '- `cargo audit`: `cargo install cargo-audit`' ;;
			bundle-audit) echo '- `bundle-audit`: `gem install bundler-audit`' ;;
			*) ;;
			esac
		fi
	done
fi

echo ""
echo "---"
echo "*Scan complete. Review findings above for false positives before acting.*"

# Exit with non-zero code in strict mode if findings were detected
if [[ "${STRICT_MODE}" == "true" ]] && [[ ${TOOLS_WITH_FINDINGS} -gt 0 ]]; then
	echo ""
	echo "WARNING: STRICT MODE: ${TOOLS_WITH_FINDINGS} tool(s) reported findings. Exiting with code 1."
	exit 1
fi

exit 0
