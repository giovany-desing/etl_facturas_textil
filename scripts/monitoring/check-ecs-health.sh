#!/bin/bash
#
# Script para verificar el estado de salud de un servicio ECS
# Retorna exit 0 si healthy, exit 1 si unhealthy
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

Verifica el estado de salud de un servicio ECS.

Opciones:
    -c, --cluster CLUSTER     Nombre del cluster ECS (requerido)
    -s, --service SERVICE     Nombre del servicio ECS (requerido)
    -r, --region REGION        Región AWS (default: us-east-1)
    -v, --verbose              Mostrar información detallada
    -h, --help                 Muestra esta ayuda

Ejemplos:
    $0 --cluster etl-facturas-cluster --service fastapi-service
    $0 -c etl-facturas-cluster -s mlflow-service -v

EOF
}

function log_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

function log_success() {
    echo -e "${GREEN}[HEALTHY]${NC} $1"
}

function log_error() {
    echo -e "${RED}[UNHEALTHY]${NC} $1"
}

function log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 no está instalado o no está en PATH"
        exit 1
    fi
}

# ========== VALIDACIÓN ==========
check_command aws
check_command jq

# ========== PARÁMETROS ==========
CLUSTER_NAME=""
SERVICE_NAME=""
AWS_REGION="${AWS_REGION:-us-east-1}"
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
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

if [ -z "$CLUSTER_NAME" ] || [ -z "$SERVICE_NAME" ]; then
    log_error "Debes especificar --cluster y --service"
    help
    exit 1
fi

# ========== OBTENER ESTADO DEL SERVICIO ==========
log_info "Obteniendo estado del servicio: $SERVICE_NAME en cluster: $CLUSTER_NAME"

SERVICE_INFO=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0]' \
    --output json)

if [ -z "$SERVICE_INFO" ] || [ "$SERVICE_INFO" = "null" ]; then
    log_error "Servicio no encontrado: $SERVICE_NAME"
    exit 1
fi

# Extraer información
RUNNING_COUNT=$(echo "$SERVICE_INFO" | jq -r '.runningCount // 0')
DESIRED_COUNT=$(echo "$SERVICE_INFO" | jq -r '.desiredCount // 0')
STATUS=$(echo "$SERVICE_INFO" | jq -r '.status // "UNKNOWN"')
DEPLOYMENTS=$(echo "$SERVICE_INFO" | jq -r '.deployments | length')

log_info "Running: $RUNNING_COUNT"
log_info "Desired: $DESIRED_COUNT"
log_info "Status: $STATUS"
log_info "Deployments: $DEPLOYMENTS"

# ========== VERIFICACIONES ==========
IS_HEALTHY=true
ISSUES=()

# Verificar que running == desired
if [ "$RUNNING_COUNT" -ne "$DESIRED_COUNT" ]; then
    IS_HEALTHY=false
    ISSUES+=("Running count ($RUNNING_COUNT) != Desired count ($DESIRED_COUNT)")
fi

# Verificar estado del servicio
if [ "$STATUS" != "ACTIVE" ]; then
    IS_HEALTHY=false
    ISSUES+=("Service status is $STATUS (expected ACTIVE)")
fi

# Verificar deployments (debe haber solo 1 deployment estable)
if [ "$DEPLOYMENTS" -gt 1 ]; then
    IS_HEALTHY=false
    ISSUES+=("Multiple deployments detected ($DEPLOYMENTS), service may be updating")
fi

# Verificar tasks individuales
if [ "$RUNNING_COUNT" -gt 0 ]; then
    log_info "Verificando estado de tasks individuales..."
    
    TASK_ARNS=$(aws ecs list-tasks \
        --cluster "$CLUSTER_NAME" \
        --service-name "$SERVICE_NAME" \
        --region "$AWS_REGION" \
        --query 'taskArns[]' \
        --output text)
    
    if [ -n "$TASK_ARNS" ]; then
        UNHEALTHY_TASKS=0
        
        for TASK_ARN in $TASK_ARNS; do
            TASK_INFO=$(aws ecs describe-tasks \
                --cluster "$CLUSTER_NAME" \
                --tasks "$TASK_ARN" \
                --region "$AWS_REGION" \
                --query 'tasks[0]' \
                --output json)
            
            LAST_STATUS=$(echo "$TASK_INFO" | jq -r '.lastStatus // "UNKNOWN"')
            HEALTH_STATUS=$(echo "$TASK_INFO" | jq -r '.healthStatus // "UNKNOWN"')
            
            log_info "Task $TASK_ARN: status=$LAST_STATUS, health=$HEALTH_STATUS"
            
            if [ "$HEALTH_STATUS" != "HEALTHY" ] && [ "$HEALTH_STATUS" != "UNKNOWN" ]; then
                UNHEALTHY_TASKS=$((UNHEALTHY_TASKS + 1))
                ISSUES+=("Task $TASK_ARN is $HEALTH_STATUS")
            fi
        done
        
        if [ "$UNHEALTHY_TASKS" -gt 0 ]; then
            IS_HEALTHY=false
        fi
    fi
fi

# ========== RESULTADO ==========
echo ""
if [ "$IS_HEALTHY" = true ]; then
    log_success "Servicio $SERVICE_NAME está HEALTHY"
    log_success "Running: $RUNNING_COUNT/$DESIRED_COUNT tasks"
    exit 0
else
    log_error "Servicio $SERVICE_NAME está UNHEALTHY"
    echo ""
    log_error "Problemas detectados:"
    for issue in "${ISSUES[@]}"; do
        echo -e "  ${RED}✗${NC} $issue"
    done
    exit 1
fi

