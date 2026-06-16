#!/bin/bash
################################################################################
# EDT Configuration Analysis - Full Pipeline Orchestrator
# 
# Purpose: Automate and parallelize 6-step EDT analysis pipeline
# Version: 1.0.0
# Date: 2025-11-06
#
# Pipeline:
# 1. Parse EDT configuration (sequential, 10-15 min)
# 2-5. Run 4 parallel analyses (parallel, 8-12 min total)
#    - Architecture analysis
#    - ML dataset creation
#    - Dependencies analysis
#    - Best practices extraction
# 6. Generate documentation (sequential, 1-2 min)
#
# Time savings: 30-47 min → 15-20 min (-35-50%)
#
# Usage:
#   ./scripts/orchestrate_edt_analysis.sh
#   ./scripts/orchestrate_edt_analysis.sh --config ERPCPM
#   ./scripts/orchestrate_edt_analysis.sh --help
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Pipe failures are errors

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs/edt_analysis"
OUTPUT_DIR="$PROJECT_ROOT/output"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_ID="edt_analysis_$TIMESTAMP"
LOG_FILE="$LOG_DIR/${RUN_ID}.log"

# Default configuration (can be overridden via CLI)
CONFIG_NAME="ERPCPM"
CONFIG_PATH=""
SKIP_PARSE=false
RUN_ARCH=true
RUN_DATASET=true
RUN_DEPS=true
RUN_BP=true
RUN_DOC=true
QUICK_MODE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# FUNCTIONS
# ============================================================================

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    local color=""
    
    case "$level" in
        "INFO")  color="$BLUE" ;;
        "SUCCESS") color="$GREEN" ;;
        "WARNING") color="$YELLOW" ;;
        "ERROR") color="$RED" ;;
        *) color="$NC" ;;
    esac
    
    echo -e "${color}[$timestamp] [$level] $message${NC}" | tee -a "$LOG_FILE"
}

print_header() {
    local title="$1"
    log "INFO" "========================================="
    log "INFO" "$title"
    log "INFO" "========================================="
}

print_footer() {
    log "INFO" "========================================="
}

check_requirements() {
    log "INFO" "Checking requirements..."
    
    # Check Python
    if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
        log "ERROR" "Python not found. Please install Python 3.11.x"
        exit 1
    fi
    
    PYTHON_CMD=$(command -v python3 || command -v python)
    
    # Check configuration directory
    if [ ! -d "$CONFIG_PATH" ]; then
        log "ERROR" "Configuration not found: $CONFIG_PATH"
        log "INFO" "Available configurations:"
        ls -1 "$PROJECT_ROOT/1c_configurations/" 2>/dev/null || echo "  None"
        exit 1
    fi
    
    # Check required scripts
    local required_scripts=(
        "parsers/edt/edt_parser_with_metadata.py"
        "analysis/analyze_architecture.py"
        "dataset/create_ml_dataset.py"
        "analysis/analyze_dependencies.py"
        "analysis/extract_best_practices.py"
        "analysis/generate_documentation.py"
    )
    
    for script in "${required_scripts[@]}"; do
        if [ ! -f "$SCRIPT_DIR/$script" ]; then
            log "ERROR" "Required script not found: $script"
            exit 1
        fi
    done
    
    log "SUCCESS" "✅ All requirements OK"
}

create_directories() {
    mkdir -p "$LOG_DIR"
    mkdir -p "$OUTPUT_DIR/edt_parser"
    mkdir -p "$OUTPUT_DIR/analysis"
    mkdir -p "$OUTPUT_DIR/dataset"
    mkdir -p "$PROJECT_ROOT/docs/generated"
}

run_step() {
    local step_num="$1"
    local step_name="$2"
    local command="$3"
    local timeout_seconds="${4:-1800}"  # Default 30 min
    
    log "INFO" "Step $step_num: $step_name..."
    local start_time=$(date +%s)
    
    # Run with timeout
    timeout $timeout_seconds bash -c "$command" >> "$LOG_FILE" 2>&1
    local exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $exit_code -eq 124 ]; then
        log "ERROR" "❌ $step_name TIMEOUT (>${timeout_seconds}s)"
        return 1
    elif [ $exit_code -ne 0 ]; then
        log "ERROR" "❌ $step_name FAILED (exit code: $exit_code, duration: ${duration}s)"
        return 1
    else
        log "SUCCESS" "✅ $step_name complete (${duration}s)"
        return 0
    fi
}

show_usage() {
    cat << EOF
EDT Analysis Pipeline Orchestrator

Usage:
  $0 [OPTIONS] [CONFIG_NAME]

Arguments:
  CONFIG_NAME    Configuration name (default: ERPCPM)
                 Must exist in 1c_configurations/ directory

Options:
  -h, --help        Show this help message
  --config NAME     Specify configuration explicitly (default: ERPCPM)
  --skip-parse      Skip parsing step (use existing parse results)
  --quick           Run only parsing step and exit
  --only-deps       Run only dependencies analysis (requires parse results)
  --only-bp         Run only best practices extraction (requires parse results)

Examples:
  $0                    # Analyze ERPCPM (default)
  $0 ERP                # Analyze ERP configuration
  $0 --skip-parse       # Skip parsing, run only analysis
  $0 --only-deps --skip-parse

Output:
  Logs: $LOG_DIR/
  Results: $OUTPUT_DIR/

EOF
}

# ============================================================================
# MAIN PIPELINE
# ============================================================================

main() {
    local CONFIG_SPECIFIED=false
    local ARG
    
    while [[ $# -gt 0 ]]; do
        ARG="$1"
        case "$ARG" in
            -h|--help)
                show_usage
                exit 0
                ;;
            --config)
                if [[ -z "${2:-}" ]]; then
                    log "ERROR" "--config requires a value"
                    exit 1
                fi
                CONFIG_NAME="$2"
                CONFIG_SPECIFIED=true
                shift 2
                continue
                ;;
            --skip-parse)
                SKIP_PARSE=true
                shift
                continue
                ;;
            --quick)
                QUICK_MODE=true
                RUN_ARCH=false
                RUN_DATASET=false
                RUN_DEPS=false
                RUN_BP=false
                RUN_DOC=false
                shift
                continue
                ;;
            --only-deps)
                RUN_ARCH=false
                RUN_DATASET=false
                RUN_DEPS=true
                RUN_BP=false
                RUN_DOC=false
                shift
                continue
                ;;
            --only-bp)
                RUN_ARCH=false
                RUN_DATASET=false
                RUN_DEPS=false
                RUN_BP=true
                RUN_DOC=false
                shift
                continue
                ;;
            --*)
                log "WARNING" "Unknown option: $ARG"
                shift
                continue
                ;;
            *)
                if [[ "$CONFIG_SPECIFIED" = false ]]; then
                    CONFIG_NAME="$ARG"
                    CONFIG_SPECIFIED=true
                else
                    log "WARNING" "Ignoring extra argument: $ARG"
                fi
                shift
                continue
                ;;
        esac
    done
    
    CONFIG_PATH="$PROJECT_ROOT/1c_configurations/$CONFIG_NAME"
    
    print_header "EDT ANALYSIS PIPELINE"
    log "INFO" "Run ID: $RUN_ID"
    log "INFO" "Configuration: $CONFIG_NAME"
    log "INFO" "Log file: $LOG_FILE"
    print_footer
    
    # Setup
    create_directories
    check_requirements
    
    # Determine Python command
    PYTHON_CMD=$(command -v python3 || command -v python)
    
    # Global start time
    PIPELINE_START=$(date +%s)
    local TOTAL_STEPS_LABEL=1
    if [ "$QUICK_MODE" = false ] && [ "$RUN_DOC" = true ]; then
        TOTAL_STEPS_LABEL=2
    fi
    local PARSE_STEP_LABEL="1/${TOTAL_STEPS_LABEL}"
    local DOC_STEP_LABEL="${TOTAL_STEPS_LABEL}/${TOTAL_STEPS_LABEL}"
    
    if [ "$QUICK_MODE" = true ]; then
        log "INFO" "Mode: QUICK (parsing only)"
    else
        log "INFO" "Selected analyses:"
        log "INFO" "  - Architecture:      $( [ "$RUN_ARCH" = true ] && echo "ON" || echo "OFF" )"
        log "INFO" "  - ML Dataset:        $( [ "$RUN_DATASET" = true ] && echo "ON" || echo "OFF" )"
        log "INFO" "  - Dependencies:      $( [ "$RUN_DEPS" = true ] && echo "ON" || echo "OFF" )"
        log "INFO" "  - Best Practices:    $( [ "$RUN_BP" = true ] && echo "ON" || echo "OFF" )"
        log "INFO" "  - Documentation:     $( [ "$RUN_DOC" = true ] && echo "ON" || echo "OFF" )"
    fi
    
    # ========================================================================
    # STEP 1: Parsing (обязательно первым)
    # ========================================================================
    
    if [ "$SKIP_PARSE" = false ]; then
        if ! run_step "$PARSE_STEP_LABEL" \
            "Parsing EDT configuration" \
            "cd '$PROJECT_ROOT' && $PYTHON_CMD scripts/parsers/edt/edt_parser_with_metadata.py" \
            1200; then
            log "ERROR" "Pipeline aborted at parsing step"
            exit 1
        fi
    else
        log "WARNING" "Skipping parsing step (using existing results)"
        log "INFO" "Step ${PARSE_STEP_LABEL}: Skipping parsing (existing results)"
    fi
    
    if [ "$QUICK_MODE" = true ]; then
        log "INFO" "Quick mode enabled – skipping analysis and documentation."
        PIPELINE_END=$(date +%s)
        TOTAL_DURATION=$((PIPELINE_END - PIPELINE_START))
        
        print_header "QUICK MODE SUMMARY"
        log "SUCCESS" "✅ Parsing data ready"
        log "INFO" "Results stored in: $OUTPUT_DIR/edt_parser/"
        log "INFO" "Elapsed: ${TOTAL_DURATION}s ($(echo "scale=1; $TOTAL_DURATION/60" | bc) min)"
        print_footer
        
        rm -f "$LOG_DIR/${RUN_ID}"_*.exit
        exit 0
    fi
    # ========================================================================
    # STEPS 2-5: Parallel Analysis (динамический набор задач)
    # ========================================================================
    
    declare -a TASK_LABELS=()
    declare -a TASK_SUFFIX=()
    declare -a TASK_COMMANDS=()
    
    if [ "$RUN_ARCH" = true ]; then
        TASK_LABELS+=("Architecture analysis")
        TASK_SUFFIX+=("arch")
        TASK_COMMANDS+=("$PYTHON_CMD scripts/analysis/analyze_architecture.py")
    fi
    if [ "$RUN_DATASET" = true ]; then
        TASK_LABELS+=("ML dataset creation")
        TASK_SUFFIX+=("dataset")
        TASK_COMMANDS+=("$PYTHON_CMD scripts/dataset/create_ml_dataset.py")
    fi
    if [ "$RUN_DEPS" = true ]; then
        TASK_LABELS+=("Dependencies analysis")
        TASK_SUFFIX+=("deps")
        TASK_COMMANDS+=("$PYTHON_CMD scripts/analysis/analyze_dependencies.py")
    fi
    if [ "$RUN_BP" = true ]; then
        TASK_LABELS+=("Best practices extraction")
        TASK_SUFFIX+=("bp")
        TASK_COMMANDS+=("$PYTHON_CMD scripts/analysis/extract_best_practices.py")
    fi
    
    TASK_COUNT=${#TASK_LABELS[@]}
    
    if [ "$TASK_COUNT" -gt 0 ]; then
        print_header "PARALLEL ANALYSIS (${TASK_COUNT} task(s))"
        
        PARALLEL_START=$(date +%s)
        
        declare -a TASK_PIDS=()
        declare -a TASK_EXIT_FILES=()
        
        for idx in "${!TASK_LABELS[@]}"; do
            label="${TASK_LABELS[$idx]}"
            suffix="${TASK_SUFFIX[$idx]}"
            command="${TASK_COMMANDS[$idx]}"
            
            log "INFO" "Starting: $label"
            
            (
                cd "$PROJECT_ROOT"
                bash -c "$command" > "$LOG_DIR/${RUN_ID}_${suffix}.log" 2>&1
                EXIT_CODE=$?
                echo $EXIT_CODE > "$LOG_DIR/${RUN_ID}_${suffix}.exit"
                exit $EXIT_CODE
            ) &
            TASK_PIDS[$idx]=$!
            TASK_EXIT_FILES[$idx]="$LOG_DIR/${RUN_ID}_${suffix}.exit"
        done
        
        log "INFO" "Waiting for analysis tasks to complete..."
        for pid in "${TASK_PIDS[@]}"; do
            wait "$pid"
        done
        
        PARALLEL_END=$(date +%s)
        PARALLEL_DURATION=$((PARALLEL_END - PARALLEL_START))
        
        FAILED_COUNT=0
        
        for idx in "${!TASK_LABELS[@]}"; do
            label="${TASK_LABELS[$idx]}"
            exit_file="${TASK_EXIT_FILES[$idx]}"
            EXIT_CODE=$(cat "$exit_file" 2>/dev/null || echo "1")
            if [ "$EXIT_CODE" -eq 0 ]; then
                log "SUCCESS" "  ✅ $label complete"
            else
                log "ERROR" "  ❌ $label FAILED"
                FAILED_COUNT=$((FAILED_COUNT + 1))
            fi
        done
        
        log "INFO" "Analysis tasks completed in ${PARALLEL_DURATION}s"
        
        if [ $FAILED_COUNT -gt 0 ]; then
            log "ERROR" "Pipeline failed: $FAILED_COUNT task(s) failed"
            log "INFO" "Check detailed logs in: $LOG_DIR/"
            exit 1
        fi
        
        print_footer
    else
        log "INFO" "No analysis tasks selected (quick or selective mode)."
    fi
    
    # ========================================================================
    # STEP 6: Documentation (после всех анализов)
    # ========================================================================
    
    if [ "$RUN_DOC" = true ]; then
        if ! run_step "$DOC_STEP_LABEL" \
            "Generating documentation" \
            "cd '$PROJECT_ROOT' && $PYTHON_CMD scripts/analysis/generate_documentation.py" \
            300; then
            log "ERROR" "Documentation generation failed (non-critical)"
            # Не останавливаем pipeline, документация - не критична
        fi
    else
        log "WARNING" "Skipping documentation step."
    fi
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    PIPELINE_END=$(date +%s)
    TOTAL_DURATION=$((PIPELINE_END - PIPELINE_START))
    
    print_header "PIPELINE COMPLETE"
    log "SUCCESS" "✅✅✅ ALL STEPS COMPLETED ✅✅✅"
    print_footer
    
    log "INFO" "Summary:"
    log "INFO" "  Total time: ${TOTAL_DURATION}s ($(echo "scale=1; $TOTAL_DURATION/60" | bc) min)"
    log "INFO" ""
    log "INFO" "Results:"
    log "INFO" "  📊 Parse results:     $OUTPUT_DIR/edt_parser/"
    if [ "$RUN_ARCH" = true ]; then
        log "INFO" "  🏗️  Architecture:      $OUTPUT_DIR/analysis/architecture_analysis.json"
    fi
    if [ "$RUN_DEPS" = true ]; then
        log "INFO" "  🔗 Dependencies:      $OUTPUT_DIR/analysis/dependency_graph.json"
    fi
    if [ "$RUN_DATASET" = true ]; then
        log "INFO" "  💾 ML Dataset:        $OUTPUT_DIR/dataset/ml_training_dataset.json"
    fi
    if [ "$RUN_BP" = true ]; then
        log "INFO" "  📖 Best practices:    $OUTPUT_DIR/analysis/best_practices.json"
    fi
    if [ "$RUN_DOC" = true ]; then
        log "INFO" "  📝 Documentation:     docs/generated/"
    fi
    log "INFO" ""
    log "INFO" "Logs:"
    log "INFO" "  Main log:             $LOG_FILE"
    log "INFO" "  Architecture:         $LOG_DIR/${RUN_ID}_arch.log"
    log "INFO" "  ML Dataset:           $LOG_DIR/${RUN_ID}_dataset.log"
    log "INFO" "  Dependencies:         $LOG_DIR/${RUN_ID}_deps.log"
    log "INFO" "  Best practices:       $LOG_DIR/${RUN_ID}_bp.log"
    
    print_footer
    
    # Cleanup temporary exit code files
    rm -f "$LOG_DIR/${RUN_ID}"_*.exit
}

# ============================================================================
# ENTRY POINT
# ============================================================================

# Show help
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_usage
    exit 0
fi

# Run pipeline
main "$@"


