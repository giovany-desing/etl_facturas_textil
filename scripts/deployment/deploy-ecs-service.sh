#!/bin/bash
#
# Script para desplegar un servicio ECS
# Registra nueva task definition y actualiza el servicio
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

Despliega un servicio ECS actualizando la task definition y forzando un nuevo deployment.

Opciones:
    -s, --service SERVICE     Nombre del servicio ECS (default: fastapi-service)
    -c, --cluster CLUSTER     Nombre del cluster ECS (default: etl-facturas-cluster)
    -t, --task-def FILE       Ruta al archivo JSON de task definition
    -r, --region REGION       Región AWS (default: us-east-1)
    -w, --wait                Esperar a que el servicio esté estable (default: true)
    -h, --help                Muestra esta ayuda

Ejemplos:
    $0 --service fastapi-service --task-def aws/ecs/task-definitions/fastapi-service.json
    $0 -s mlflow-service -c etl-facturas-cluster -t aws/ecs/task-definitions/mlflow-server.json

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
SERVICE_NAME="fastapi-service"
CLUSTER_NAME="etl-facturas-cluster"
TASK_DEF_FILE=""
AWS_REGION="${AWS_REGION:-us-east-1}"
WAIT_FOR_STABILITY=true

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
        -t|--task-def)
            TASK_DEF_FILE="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -w|--wait)
            WAIT_FOR_STABILITY=true
            shift
            ;;
        --no-wait)
            WAIT_FOR_STABILITY=false
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

# ========== VALIDACIÓN DE PARÁMETROS ==========
if [ -z "$TASK_DEF_FILE" ]; then
    log_error "Debes especificar un archivo de task definition con -t o --task-def"
    help
    exit 1
fi

if [ ! -f "$TASK_DEF_FILE" ]; then
    log_error "Archivo de task definition no encontrado: $TASK_DEF_FILE"
    exit 1
fi

log_info "=========================================="
log_info "Desplegando servicio ECS"
log_info "=========================================="
log_info "Servicio: $SERVICE_NAME"
log_info "Cluster: $CLUSTER_NAME"
log_info "Task Definition: $TASK_DEF_FILE"
log_info "Región: $AWS_REGION"
log_info ""

# ========== OBTENER AWS ACCOUNT ID ==========
log_info "Obteniendo AWS Account ID..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
if [ -z "$AWS_ACCOUNT_ID" ]; then
    log_error "No se pudo obtener AWS Account ID"
    exit 1
fi
log_success "AWS Account ID: $AWS_ACCOUNT_ID"

# ========== REEMPLAZAR ACCOUNT_ID EN TASK DEFINITION ==========
log_info "Reemplazando ACCOUNT_ID en task definition..."
TEMP_TASK_DEF=$(mktemp)
sed "s/ACCOUNT_ID/$AWS_ACCOUNT_ID/g" "$TASK_DEF_FILE" > "$TEMP_TASK_DEF"
log_success "Task definition preparada"

# ========== REGISTRAR TASK DEFINITION ==========
log_info "Registrando nueva task definition..."
TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json "file://$TEMP_TASK_DEF" \
    --region "$AWS_REGION" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

if [ -z "$TASK_DEF_ARN" ]; then
    log_error "Error registrando task definition"
    rm -f "$TEMP_TASK_DEF"
    exit 1
fi

log_success "Task definition registrada: $TASK_DEF_ARN"

# Extraer familia y revisión
TASK_FAMILY=$(echo "$TASK_DEF_ARN" | awk -F'/' '{print $2}' | awk -F':' '{print $1}')
TASK_REVISION=$(echo "$TASK_DEF_ARN" | awk -F':' '{print $NF}')

log_info "Familia: $TASK_FAMILY"
log_info "Revisión: $TASK_REVISION"

# Limpiar archivo temporal
rm -f "$TEMP_TASK_DEF"

# ========== ACTUALIZAR SERVICIO ==========
log_info "Actualizando servicio ECS..."
UPDATE_RESULT=$(aws ecs update-service \
    --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --task-definition "$TASK_FAMILY:$TASK_REVISION" \
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
if [ "$WAIT_FOR_STABILITY" = true ]; then
    log_info "Esperando a que el servicio esté estable (esto puede tardar varios minutos)..."
    
    aws ecs wait services-stable \
        --cluster "$CLUSTER_NAME" \
        --services "$SERVICE_NAME" \
        --region "$AWS_REGION"
    
    if [ $? -eq 0 ]; then
        log_success "Servicio está estable"
        
        # Obtener estado final
        RUNNING_COUNT=$(aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$AWS_REGION" \
            --query 'services[0].runningCount' \
            --output text)
        
        DESIRED_COUNT=$(aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$AWS_REGION" \
            --query 'services[0].desiredCount' \
            --output text)
        
        log_info "Running tasks: $RUNNING_COUNT / $DESIRED_COUNT"
    else
        log_error "El servicio no alcanzó estado estable"
        exit 1
    fi
else
    log_warning "No se esperará estabilidad (usa --wait para habilitar)"
fi

log_success "=========================================="
log_success "Deployment completado exitosamente"
log_success "=========================================="

