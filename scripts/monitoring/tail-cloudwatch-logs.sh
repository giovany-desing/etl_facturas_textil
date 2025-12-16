#!/bin/bash
#
# Script para seguir logs de CloudWatch en tiempo real
# Similar a tail -f pero para CloudWatch Logs
#

set -e

# ========== COLORES ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========== FUNCIONES ==========
function help() {
    cat << EOF
Uso: $0 [OPTIONS]

Sigue logs de CloudWatch Logs en tiempo real (similar a tail -f).

Opciones:
    -g, --log-group GROUP     Nombre del log group (default: /ecs/fastapi)
    -s, --stream STREAM        Nombre del log stream (opcional, sigue todos si no se especifica)
    -r, --region REGION        Región AWS (default: us-east-1)
    -f, --filter PATTERN       Filtrar logs por patrón (opcional)
    --since MINUTES            Mostrar logs desde hace X minutos (default: 10)
    -h, --help                 Muestra esta ayuda

Ejemplos:
    $0 --log-group /ecs/fastapi
    $0 -g /ecs/model-training --filter "ERROR"
    $0 -g /ecs/mlflow --stream mlflow-2024-12-16
    $0 -g /ecs/fastapi --since 30

EOF
}

function log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 no está instalado o no está en PATH"
        exit 1
    fi
}

# ========== VALIDACIÓN ==========
check_command aws

# ========== PARÁMETROS ==========
LOG_GROUP="/ecs/fastapi"
LOG_STREAM=""
AWS_REGION="${AWS_REGION:-us-east-1}"
FILTER_PATTERN=""
SINCE_MINUTES=10
FOLLOW=true

while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--log-group)
            LOG_GROUP="$2"
            shift 2
            ;;
        -s|--stream)
            LOG_STREAM="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -f|--filter)
            FILTER_PATTERN="$2"
            shift 2
            ;;
        --since)
            SINCE_MINUTES="$2"
            shift 2
            ;;
        --no-follow)
            FOLLOW=false
            shift
            ;;
        -h|--help)
            help
            exit 0
            ;;
        *)
            log_error "Opción desconocida: $1"
            help
            exit 1
            ;;
    esac
done

# ========== VERIFICAR LOG GROUP ==========
log_info "Verificando log group: $LOG_GROUP"

if ! aws logs describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP" \
    --region "$AWS_REGION" \
    --query "logGroups[?logGroupName=='$LOG_GROUP'].logGroupName" \
    --output text | grep -q "$LOG_GROUP"; then
    log_error "Log group no encontrado: $LOG_GROUP"
    exit 1
fi

log_info "Log group encontrado: $LOG_GROUP"

# ========== CALCULAR TIMESTAMP DE INICIO ==========
START_TIME=$(($(date +%s) - (SINCE_MINUTES * 60)))000

# ========== SEGUIR LOGS ==========
log_info "Siguiendo logs desde hace $SINCE_MINUTES minutos..."
log_info "Presiona Ctrl+C para salir"
echo ""

if [ -n "$LOG_STREAM" ]; then
    # Seguir un stream específico
    if [ "$FOLLOW" = true ]; then
        aws logs tail "$LOG_GROUP" \
            --log-stream-names "$LOG_STREAM" \
            --since "${SINCE_MINUTES}m" \
            --format short \
            --region "$AWS_REGION" \
            --follow \
            ${FILTER_PATTERN:+--filter-pattern "$FILTER_PATTERN"}
    else
        aws logs tail "$LOG_GROUP" \
            --log-stream-names "$LOG_STREAM" \
            --since "${SINCE_MINUTES}m" \
            --format short \
            --region "$AWS_REGION" \
            ${FILTER_PATTERN:+--filter-pattern "$FILTER_PATTERN"}
    fi
else
    # Seguir todos los streams del log group
    if [ "$FOLLOW" = true ]; then
        aws logs tail "$LOG_GROUP" \
            --since "${SINCE_MINUTES}m" \
            --format short \
            --region "$AWS_REGION" \
            --follow \
            ${FILTER_PATTERN:+--filter-pattern "$FILTER_PATTERN"}
    else
        aws logs tail "$LOG_GROUP" \
            --since "${SINCE_MINUTES}m" \
            --format short \
            --region "$AWS_REGION" \
            ${FILTER_PATTERN:+--filter-pattern "$FILTER_PATTERN"}
    fi
fi

