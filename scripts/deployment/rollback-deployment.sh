#!/bin/bash
#
# Script para hacer rollback de un servicio ECS a una revisión anterior
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

Hace rollback de un servicio ECS a una revisión anterior de la task definition.

Opciones:
    -s, --service SERVICE     Nombre del servicio ECS (requerido)
    -c, --cluster CLUSTER     Nombre del cluster ECS (default: etl-facturas-cluster)
    -r, --revision REV        Número de revisión a la que hacer rollback
    -l, --list                Listar las últimas 5 revisiones disponibles
    --region REGION           Región AWS (default: us-east-1)
    -h, --help                Muestra esta ayuda

Ejemplos:
    $0 --service fastapi-service --list
    $0 -s fastapi-service -r 5
    $0 -s mlflow-service -c etl-facturas-cluster -r 3

EOF
}

function log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

function log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
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
SERVICE_NAME=""
CLUSTER_NAME="etl-facturas-cluster"
TARGET_REVISION=""
AWS_REGION="${AWS_REGION:-us-east-1}"
LIST_REVISIONS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -c|--cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -r|--revision)
            TARGET_REVISION="$2"
            shift 2
            ;;
        -l|--list)
            LIST_REVISIONS=true
            shift
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
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

if [ -z "$SERVICE_NAME" ]; then
    log_error "Debes especificar un nombre de servicio con -s o --service"
    help
    exit 1
fi

# ========== OBTENER TASK DEFINITION ACTUAL ==========
log_info "Obteniendo información del servicio: $SERVICE_NAME"
CURRENT_TASK_DEF=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0].taskDefinition' \
    --output text)

if [ -z "$CURRENT_TASK_DEF" ] || [ "$CURRENT_TASK_DEF" = "None" ]; then
    log_error "No se pudo obtener información del servicio o el servicio no existe"
    exit 1
fi

TASK_FAMILY=$(echo "$CURRENT_TASK_DEF" | awk -F'/' '{print $2}' | awk -F':' '{print $1}')
CURRENT_REVISION=$(echo "$CURRENT_TASK_DEF" | awk -F':' '{print $NF}')

log_info "Task Family: $TASK_FAMILY"
log_info "Revisión actual: $CURRENT_REVISION"

# ========== LISTAR REVISIONES ==========
if [ "$LIST_REVISIONS" = true ] || [ -z "$TARGET_REVISION" ]; then
    log_info "Obteniendo últimas revisiones de task definition..."
    
    REVISIONS=$(aws ecs list-task-definitions \
        --family-prefix "$TASK_FAMILY" \
        --region "$AWS_REGION" \
        --sort DESC \
        --max-items 5 \
        --query 'taskDefinitionArns[*]' \
        --output text)
    
    if [ -z "$REVISIONS" ]; then
        log_error "No se encontraron revisiones para $TASK_FAMILY"
        exit 1
    fi
    
    echo ""
    log_info "Últimas 5 revisiones disponibles:"
    echo ""
    
    REVISION_LIST=($REVISIONS)
    for i in "${!REVISION_LIST[@]}"; do
        REV=$(echo "${REVISION_LIST[$i]}" | awk -F':' '{print $NF}')
        if [ "$REV" = "$CURRENT_REVISION" ]; then
            echo -e "  ${GREEN}[ACTUAL]${NC} Revisión $REV: ${REVISION_LIST[$i]}"
        else
            echo -e "  [     ] Revisión $REV: ${REVISION_LIST[$i]}"
        fi
    done
    echo ""
    
    if [ -z "$TARGET_REVISION" ]; then
        log_warning "Especifica una revisión con -r o --revision para hacer rollback"
        exit 0
    fi
fi

# ========== VALIDAR REVISIÓN OBJETIVO ==========
if [ "$TARGET_REVISION" = "$CURRENT_REVISION" ]; then
    log_warning "La revisión objetivo ($TARGET_REVISION) es la misma que la actual"
    log_warning "No se realizará rollback"
    exit 0
fi

# Verificar que la revisión existe
TARGET_TASK_DEF="$TASK_FAMILY:$TARGET_REVISION"
TASK_DEF_EXISTS=$(aws ecs describe-task-definition \
    --task-definition "$TARGET_TASK_DEF" \
    --region "$AWS_REGION" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text 2>/dev/null)

if [ -z "$TASK_DEF_EXISTS" ]; then
    log_error "La revisión $TARGET_REVISION no existe para $TASK_FAMILY"
    exit 1
fi

# ========== CONFIRMACIÓN ==========
log_warning "=========================================="
log_warning "ROLLBACK DE SERVICIO ECS"
log_warning "=========================================="
log_warning "Servicio: $SERVICE_NAME"
log_warning "Cluster: $CLUSTER_NAME"
log_warning "Revisión actual: $CURRENT_REVISION"
log_warning "Revisión objetivo: $TARGET_REVISION"
log_warning "=========================================="
echo ""
read -p "¿Continuar con el rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Rollback cancelado por el usuario"
    exit 0
fi

# ========== HACER ROLLBACK ==========
log_info "Actualizando servicio a revisión $TARGET_REVISION..."

UPDATE_RESULT=$(aws ecs update-service \
    --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --task-definition "$TARGET_TASK_DEF" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --query 'service.serviceName' \
    --output text)

if [ -z "$UPDATE_RESULT" ]; then
    log_error "Error actualizando servicio"
    exit 1
fi

log_success "Servicio actualizado: $UPDATE_RESULT"

# ========== ESPERAR ESTABILIDAD ==========
log_info "Esperando a que el servicio esté estable..."
aws ecs wait services-stable \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$AWS_REGION"

if [ $? -eq 0 ]; then
    log_success "Rollback completado exitosamente"
    log_info "Servicio ahora usa revisión: $TARGET_REVISION"
else
    log_error "El servicio no alcanzó estado estable después del rollback"
    exit 1
fi

