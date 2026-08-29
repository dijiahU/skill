#!/bin/bash
#
# Tri-AI Collaborative Analysis Orchestrator
# Coordinates Claude (subagents), Gemini CLI, and Codex CLI for comprehensive analysis
#
# Usage: bash analyze.sh "objective description"
#

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

OBJECTIVE="${1:-No objective specified}"
ANALYSIS_DIR=".analysis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SKILL_DIR=".claude/skills/multi-ai-research"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_phase() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
    echo ""
}

log_step() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_dependencies() {
    local missing=0

    # Check for gemini CLI
    if ! command -v gemini &> /dev/null; then
        log_error "Gemini CLI not found. Install with: npm install -g @google/gemini-cli"
        missing=1
    fi

    # Check for codex CLI
    if ! command -v codex &> /dev/null; then
        log_error "Codex CLI not found. Install with: npm install -g @openai/codex"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        log_error "Missing dependencies. Please install and try again."
        exit 1
    fi

    log_step "All dependencies available"
}

# ============================================================================
# SETUP
# ============================================================================

setup_environment() {
    log_phase "SETUP: Creating Analysis Environment"

    # Create directory structure
    mkdir -p "$ANALYSIS_DIR"/{research,analysis,verification,iterations,gap-fills}

    log_step "Created directory structure"

    echo "Objective: $OBJECTIVE"
    echo "Timestamp: $TIMESTAMP"
    echo "Analysis Dir: $ANALYSIS_DIR"
    echo ""
}

# ============================================================================
# PHASE 1: PLANNING
# ============================================================================

phase_1_planning() {
    log_phase "PHASE 1: PLANNING & STRATEGY"

    log_info "Creating comprehensive analysis plan..."

    # Note: In a real implementation, this would use Claude to create the plan
    # For now, we use the template and ask user or Claude to fill it in

    # Copy template and customize
    cp "$SKILL_DIR/templates/ANALYSIS_PLAN_TEMPLATE.md" "$ANALYSIS_DIR/ANALYSIS_PLAN.md"

    # Replace placeholders
    sed -i "s/\[OBJECTIVE\]/$OBJECTIVE/g" "$ANALYSIS_DIR/ANALYSIS_PLAN.md"
    sed -i "s/\[TIMESTAMP\]/$TIMESTAMP/g" "$ANALYSIS_DIR/ANALYSIS_PLAN.md"

    log_step "Analysis plan template created"
    log_info "Plan location: $ANALYSIS_DIR/ANALYSIS_PLAN.md"

    echo ""
    log_info "Please review and customize the analysis plan, then press Enter to continue..."
    read -r

    if [ ! -f "$ANALYSIS_DIR/ANALYSIS_PLAN.md" ]; then
        log_error "Analysis plan not found. Exiting."
        exit 1
    fi

    log_step "Analysis plan ready"
    echo ""
}

# ============================================================================
# PHASE 2: PARALLEL RESEARCH
# ============================================================================

phase_2_research() {
    log_phase "PHASE 2: PARALLEL RESEARCH (All 3 AI Systems)"

    log_info "Launching research agents in parallel..."
    echo ""

    # ====================
    # Claude Research Subagent
    # ====================
    log_info "Starting Claude research subagent..."

    # Note: In actual implementation, this would use the Task tool via Claude Code
    # For this script, we simulate with a placeholder
    cat > "$ANALYSIS_DIR/research/claude-docs.md" << 'EOF'
# Claude Research Findings

## Note
This is a placeholder. In actual implementation, Claude subagent via Task tool
would research documentation and codebase using progressive disclosure.

## Process
1. Glob to map structure
2. Grep to find patterns
3. Read targeted files

## Findings
[Research findings would appear here with file:line citations]
EOF

    log_step "Claude research subagent output: $ANALYSIS_DIR/research/claude-docs.md"

    # ====================
    # Gemini CLI Research
    # ====================
    log_info "Starting Gemini web research..."

    # Check if gemini is available
    if command -v gemini &> /dev/null; then
        # Run Gemini research (with --yolo for automation)
        gemini --yolo --output-format json -p "Research best practices for: $OBJECTIVE

Tasks:
1. Search for latest best practices (2024-2025)
2. Find community patterns and trends
3. Identify popular libraries and frameworks
4. Discover common pitfalls and anti-patterns

Return structured JSON:
{
  \"best_practices\": [{\"practice\": \"...\", \"source\": \"URL\", \"confidence\": \"high|medium|low\"}],
  \"trends\": [{\"trend\": \"...\", \"evidence\": \"...\", \"source\": \"URL\"}],
  \"libraries\": [{\"name\": \"...\", \"purpose\": \"...\", \"popularity\": \"...\"}],
  \"pitfalls\": [{\"issue\": \"...\", \"solution\": \"...\", \"source\": \"URL\"}]
}" > "$ANALYSIS_DIR/research/gemini-web.json" 2>&1 || {
            log_error "Gemini research failed - creating placeholder"
            echo '{"best_practices": [], "error": "Gemini research failed"}' > "$ANALYSIS_DIR/research/gemini-web.json"
        }

        log_step "Gemini research output: $ANALYSIS_DIR/research/gemini-web.json"
    else
        log_error "Gemini CLI not available - skipping web research"
        echo '{"error": "Gemini CLI not available"}' > "$ANALYSIS_DIR/research/gemini-web.json"
    fi

    # ====================
    # Codex CLI Research
    # ====================
    log_info "Starting Codex code research..."

    # Check if codex is available
    if command -v codex &> /dev/null; then
        # Run Codex research
        codex exec -m gpt-5.1-codex --search --json \
            --dangerously-bypass-approvals-and-sandbox \
            "Research code patterns for: $OBJECTIVE

Tasks:
1. Search GitHub for popular implementation patterns
2. Collect code examples from top repositories
3. Analyze API design patterns
4. Review testing strategies

Return JSON:
{
  \"patterns\": [{\"pattern\": \"...\", \"examples\": [...], \"repos\": [\"user/repo\"]}],
  \"code_examples\": [{\"description\": \"...\", \"code\": \"...\", \"source\": \"URL\"}],
  \"api_patterns\": [{\"pattern\": \"...\", \"usage\": \"...\"}],
  \"testing\": [{\"approach\": \"...\", \"tools\": [...]}]
}" > "$ANALYSIS_DIR/research/codex-github.json" 2>&1 || {
            log_error "Codex research failed - creating placeholder"
            echo '{"patterns": [], "error": "Codex research failed"}' > "$ANALYSIS_DIR/research/codex-github.json"
        }

        log_step "Codex research output: $ANALYSIS_DIR/research/codex-github.json"
    else
        log_error "Codex CLI not available - skipping code research"
        echo '{"error": "Codex CLI not available"}' > "$ANALYSIS_DIR/research/codex-github.json"
    fi

    echo ""
    log_step "All research agents completed"
    echo ""
}

# ============================================================================
# PHASE 3: DEEP ANALYSIS
# ============================================================================

phase_3_analysis() {
    log_phase "PHASE 3: DEEP ANALYSIS & PATTERN RECOGNITION"

    log_info "Performing pattern analysis on research findings..."

    # Note: In actual implementation, this would use Claude with extended thinking
    # For now, create a placeholder that would be filled by analysis agent
    cat > "$ANALYSIS_DIR/analysis/code-patterns.md" << 'EOF'
# Code Pattern Analysis

## Note
This is a placeholder. In actual implementation, Claude analysis agent with
extended thinking would synthesize all research findings and perform deep
pattern recognition.

## Process
1. Read all research files
2. Perform progressive disclosure on codebase
3. Identify patterns across sources
4. Map architecture
5. Generate insights

## Patterns Identified
[Patterns would appear here with file:line evidence]

## Architecture Map
[Architecture insights]

## Recommendations
[Specific recommendations]
EOF

    log_step "Pattern analysis output: $ANALYSIS_DIR/analysis/code-patterns.md"
    echo ""
}

# ============================================================================
# PHASE 4: SYNTHESIS & VERIFICATION
# ============================================================================

phase_4_synthesis() {
    log_phase "PHASE 4: SYNTHESIS & CROSS-VERIFICATION"

    # ====================
    # Synthesis
    # ====================
    log_info "Synthesizing findings from all sources..."

    # Copy synthesis template
    cp "$SKILL_DIR/templates/SYNTHESIS_TEMPLATE.md" "$ANALYSIS_DIR/SYNTHESIS_REPORT.md"

    # Replace placeholders
    sed -i "s/\[OBJECTIVE\]/$OBJECTIVE/g" "$ANALYSIS_DIR/SYNTHESIS_REPORT.md"
    sed -i "s/\[TIMESTAMP\]/$TIMESTAMP/g" "$ANALYSIS_DIR/SYNTHESIS_REPORT.md"

    log_step "Synthesis template created: $ANALYSIS_DIR/SYNTHESIS_REPORT.md"

    # Note: In actual implementation, Claude with extended thinking would:
    # 1. Read all research files
    # 2. Identify themes across sources
    # 3. Resolve contradictions
    # 4. Create unified narrative with citations

    # ====================
    # Verification
    # ====================
    log_info "Running cross-validation and completeness checks..."

    # Copy verification checklist
    cp "$SKILL_DIR/templates/VERIFICATION_CHECKLIST.md" "$ANALYSIS_DIR/verification/cross-check.md"

    # Replace placeholders
    sed -i "s/\[OBJECTIVE\]/$OBJECTIVE/g" "$ANALYSIS_DIR/verification/cross-check.md"
    sed -i "s/\[TIMESTAMP\]/$TIMESTAMP/g" "$ANALYSIS_DIR/verification/cross-check.md"

    log_step "Verification checklist created: $ANALYSIS_DIR/verification/cross-check.md"

    # Note: In actual implementation, verification agent would:
    # 1. Check all objectives addressed
    # 2. Verify all citations traceable
    # 3. Cross-validate between sources
    # 4. Calculate quality score
    # 5. Identify gaps

    echo ""
}

# ============================================================================
# PHASE 5: ITERATION CHECK
# ============================================================================

phase_5_iteration() {
    log_phase "PHASE 5: ITERATION & QUALITY CHECK"

    log_info "Checking quality gates..."

    # In actual implementation, read verification results and check:
    # - Quality score >= 95?
    # - Citation coverage = 100%?
    # - Critical gaps = 0?

    # For now, simulate quality check
    QUALITY_SCORE=85  # Simulated score (would come from verification)

    echo "Quality Score: $QUALITY_SCORE/100"

    if [ "$QUALITY_SCORE" -lt 95 ]; then
        log_info "Quality threshold not met (need ≥95)"
        log_info "Iteration 2 would be triggered to fill gaps..."

        # Create iteration marker
        cat > "$ANALYSIS_DIR/iterations/ITERATION_1.md" << EOF
# Iteration 1 Results

Quality Score: $QUALITY_SCORE/100
Status: NEEDS ITERATION

Gaps identified:
1. [Gap would be listed here]
2. [Gap would be listed here]

Next steps:
- Iteration 2 to address gaps
- Re-verify after improvements
EOF

        log_step "Iteration 1 results saved"
        log_info "In production, iteration 2 would run automatically"
    else
        log_step "Quality threshold met! ($QUALITY_SCORE/100)"
    fi

    echo ""
}

# ============================================================================
# PHASE 6: FINAL REPORT
# ============================================================================

phase_6_final_report() {
    log_phase "PHASE 6: FINAL COMPREHENSIVE REPORT"

    log_info "Creating final report..."

    # In actual implementation, Claude would synthesize everything into final report
    cat > "$ANALYSIS_DIR/ANALYSIS_FINAL.md" << EOF
# Comprehensive Analysis: $OBJECTIVE

**Date**: $TIMESTAMP
**Status**: Analysis Complete

---

## Executive Summary

This analysis was conducted using a tri-AI collaborative approach with Claude
(subagents), Gemini CLI (web research), and Codex CLI (code research).

[In production, comprehensive synthesis would appear here]

---

## Methodology

### AI Systems Used
1. **Claude Research Subagent**: Documentation and codebase analysis
2. **Gemini CLI**: Web research and best practices
3. **Codex CLI**: GitHub patterns and code examples
4. **Claude Analysis Agent**: Pattern synthesis
5. **Claude Verification Agent**: Cross-validation

### Analysis Phases
1. Planning & Strategy
2. Parallel Research (all 3 systems)
3. Deep Analysis & Pattern Recognition
4. Synthesis & Cross-Verification
5. Iteration & Quality Check
6. Final Report

---

## Main Findings

[Complete findings from synthesis would appear here]

---

## Verification Summary

- Completeness: ___%
- Citation Coverage: ___%
- Quality Score: ___/100
- Iterations: [count]

---

## Detailed Analysis

See supporting files:
- Research: .analysis/research/*.md
- Analysis: .analysis/analysis/*.md
- Verification: .analysis/verification/*.md
- Synthesis: .analysis/SYNTHESIS_REPORT.md

---

## Recommendations

[Prioritized recommendations would appear here]

---

**Analysis Complete**: $TIMESTAMP
**Location**: $ANALYSIS_DIR/ANALYSIS_FINAL.md
EOF

    log_step "Final report created: $ANALYSIS_DIR/ANALYSIS_FINAL.md"
    echo ""
}

# ============================================================================
# SUMMARY
# ============================================================================

print_summary() {
    log_phase "ANALYSIS COMPLETE"

    echo "Objective: $OBJECTIVE"
    echo "Timestamp: $TIMESTAMP"
    echo ""
    echo "Generated Files:"
    echo "  📋 Analysis Plan:     $ANALYSIS_DIR/ANALYSIS_PLAN.md"
    echo "  🔍 Research:"
    echo "     - Claude:          $ANALYSIS_DIR/research/claude-docs.md"
    echo "     - Gemini:          $ANALYSIS_DIR/research/gemini-web.json"
    echo "     - Codex:           $ANALYSIS_DIR/research/codex-github.json"
    echo "  📊 Analysis:          $ANALYSIS_DIR/analysis/code-patterns.md"
    echo "  🔄 Synthesis:         $ANALYSIS_DIR/SYNTHESIS_REPORT.md"
    echo "  ✅ Verification:      $ANALYSIS_DIR/verification/cross-check.md"
    echo "  📄 Final Report:      $ANALYSIS_DIR/ANALYSIS_FINAL.md"
    echo ""
    echo -e "${GREEN}To view final report:${NC}"
    echo "  cat $ANALYSIS_DIR/ANALYSIS_FINAL.md"
    echo ""
    echo -e "${YELLOW}Note: This is a demonstration script.${NC}"
    echo -e "${YELLOW}In production, Claude Code would orchestrate actual agents via Task tool.${NC}"
    echo ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║   TRI-AI COLLABORATIVE ANALYSIS SYSTEM                    ║"
    echo "║   Claude + Gemini + Codex                                 ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""

    # Check dependencies
    check_dependencies

    # Setup environment
    setup_environment

    # Execute 6-phase pipeline
    phase_1_planning
    phase_2_research
    phase_3_analysis
    phase_4_synthesis
    phase_5_iteration
    phase_6_final_report

    # Print summary
    print_summary
}

# Run main function
main
