#!/bin/bash
#
# Script para actualizar una task definition de ECS
# Reemplaza ACCOUNT_ID y registra la nueva versión
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
Uso: $0 [OPTIONS] TASK_DEF_FILE

Actualiza una task definition de ECS reemplazando placeholders y registrándola.

Argumentos:
    TASK_DEF_FILE            Ruta al archivo JSON de task definition

Opciones:
    -r, --region REGION      Región AWS (default: us-east-1)
    -o, --output             Mostrar solo el ARN de la task definition
    -h, --help               Muestra esta ayuda

Ejemplos:
    $0 aws/ecs/task-definitions/fastapi-service.json
    $0 -r us-west-2 aws/ecs/task-definitions/mlflow-server.json
    $0 -o aws/ecs/task-definitions/model-training.json

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
AWS_REGION="${AWS_REGION:-us-east-1}"
OUTPUT_ONLY=false
TASK_DEF_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_ONLY=true
            shift
            ;;
        -h|--help)
            help
            exit 0
            ;;
        -*)
            log_error "Opción desconocida: $1"
            help
            exit 1
            ;;
        *)
            TASK_DEF_FILE="$1"
            shift
            ;;
    esac
done

if [ -z "$TASK_DEF_FILE" ]; then
    log_error "Debes especificar un archivo de task definition"
    help
    exit 1
fi

if [ ! -f "$TASK_DEF_FILE" ]; then
    log_error "Archivo no encontrado: $TASK_DEF_FILE"
    exit 1
fi

# ========== OBTENER AWS ACCOUNT ID ==========
if [ "$OUTPUT_ONLY" = false ]; then
    log_info "Obteniendo AWS Account ID..."
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
if [ -z "$AWS_ACCOUNT_ID" ]; then
    log_error "No se pudo obtener AWS Account ID"
    exit 1
fi

# ========== REEMPLAZAR ACCOUNT_ID ==========
if [ "$OUTPUT_ONLY" = false ]; then
    log_info "Reemplazando ACCOUNT_ID en task definition..."
fi

TEMP_TASK_DEF=$(mktemp)
sed "s/ACCOUNT_ID/$AWS_ACCOUNT_ID/g" "$TASK_DEF_FILE" > "$TEMP_TASK_DEF"

# ========== REGISTRAR TASK DEFINITION ==========
if [ "$OUTPUT_ONLY" = false ]; then
    log_info "Registrando task definition..."
fi

TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json "file://$TEMP_TASK_DEF" \
    --region "$AWS_REGION" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

# Limpiar archivo temporal
rm -f "$TEMP_TASK_DEF"

if [ -z "$TASK_DEF_ARN" ]; then
    log_error "Error registrando task definition"
    exit 1
fi

# ========== OUTPUT ==========
if [ "$OUTPUT_ONLY" = true ]; then
    echo "$TASK_DEF_ARN"
else
    log_success "Task definition registrada exitosamente"
    log_info "ARN: $TASK_DEF_ARN"
    
    # Extraer información adicional
    TASK_FAMILY=$(echo "$TASK_DEF_ARN" | awk -F'/' '{print $2}' | awk -F':' '{print $1}')
    TASK_REVISION=$(echo "$TASK_DEF_ARN" | awk -F':' '{print $NF}')
    
    log_info "Familia: $TASK_FAMILY"
    log_info "Revisión: $TASK_REVISION"
fi

exit 0

