#!/bin/bash
#
# Script para construir y subir imágenes Docker a AWS ECR
# Construye imágenes para: fastapi, training, mlflow
# Tags: latest y git commit hash
#

set -e

# ========== COLORES ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========== FUNCIONES ==========
function help() {
    cat << EOF
Uso: $0 [OPTIONS]

Construye y sube imágenes Docker a AWS ECR para los servicios del proyecto.

Opciones:
    -r, --region REGION       Región AWS (default: us-east-1)
    -a, --account-id ID       AWS Account ID (se obtiene automáticamente si no se especifica)
    -h, --help                Muestra esta ayuda

Ejemplos:
    $0
    $0 --region us-west-2
    $0 --account-id 123456789012

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

# ========== VALIDACIÓN DE PREREQUISITOS ==========
log_info "Validando prerrequisitos..."
check_command aws
check_command docker
check_command git

# ========== CONFIGURACIÓN ==========
AWS_REGION="${AWS_REGION:-us-east-1}"
SERVICES=("fastapi" "training" "mlflow")

# Obtener AWS Account ID si no se proporciona
if [ -z "$AWS_ACCOUNT_ID" ]; then
    log_info "Obteniendo AWS Account ID..."
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        log_error "No se pudo obtener AWS Account ID. Verifica tus credenciales de AWS."
        exit 1
    fi
    log_success "AWS Account ID: $AWS_ACCOUNT_ID"
fi

# Obtener git commit hash
GIT_COMMIT=$(git rev-parse --short HEAD)
if [ -z "$GIT_COMMIT" ]; then
    log_warning "No se pudo obtener git commit hash, usando 'latest'"
    GIT_COMMIT="latest"
fi

log_info "Git commit: $GIT_COMMIT"
log_info "AWS Region: $AWS_REGION"
log_info "AWS Account ID: $AWS_ACCOUNT_ID"

# ========== ECR LOGIN ==========
log_info "Haciendo login a ECR..."
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
log_success "Login a ECR exitoso"

# ========== CREAR REPOSITORIOS ECR (si no existen) ==========
for SERVICE in "${SERVICES[@]}"; do
    REPO_NAME="$SERVICE"
    log_info "Verificando repositorio ECR: $REPO_NAME"
    
    if ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" &> /dev/null; then
        log_warning "Repositorio $REPO_NAME no existe, creándolo..."
        aws ecr create-repository \
            --repository-name "$REPO_NAME" \
            --region "$AWS_REGION" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        log_success "Repositorio $REPO_NAME creado"
    else
        log_info "Repositorio $REPO_NAME ya existe"
    fi
done

# ========== BUILD Y PUSH ==========
for SERVICE in "${SERVICES[@]}"; do
    log_info "=========================================="
    log_info "Procesando servicio: $SERVICE"
    log_info "=========================================="
    
    DOCKERFILE="docker/Dockerfile.$SERVICE"
    IMAGE_NAME="$ECR_REGISTRY/$SERVICE"
    
    # Verificar que existe el Dockerfile
    if [ ! -f "$DOCKERFILE" ]; then
        log_error "Dockerfile no encontrado: $DOCKERFILE"
        exit 1
    fi
    
    # Build imagen
    log_info "Construyendo imagen: $SERVICE"
    docker build -f "$DOCKERFILE" -t "$IMAGE_NAME:latest" -t "$IMAGE_NAME:$GIT_COMMIT" .
    
    if [ $? -eq 0 ]; then
        log_success "Imagen construida exitosamente: $SERVICE"
    else
        log_error "Error construyendo imagen: $SERVICE"
        exit 1
    fi
    
    # Push tag latest
    log_info "Subiendo imagen con tag: latest"
    docker push "$IMAGE_NAME:latest"
    
    # Push tag commit
    log_info "Subiendo imagen con tag: $GIT_COMMIT"
    docker push "$IMAGE_NAME:$GIT_COMMIT"
    
    log_success "Servicio $SERVICE procesado exitosamente"
    log_info "Imágenes disponibles:"
    log_info "  - $IMAGE_NAME:latest"
    log_info "  - $IMAGE_NAME:$GIT_COMMIT"
done

log_success "=========================================="
log_success "Todas las imágenes fueron construidas y subidas exitosamente"
log_success "=========================================="

