#!/bin/bash
#
# Script maestro para deployment completo en AWS
# Ejecuta todos los pasos necesarios para desplegar en AWS
#

set -e

# ========== COLORES ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ========== FUNCIONES ==========
function help() {
    cat << EOF
Uso: $0 [OPTIONS]

Script maestro para deployment completo del proyecto en AWS desde cero.

Opciones:
    -r, --region REGION       Región AWS (default: us-east-1)
    -c, --cluster CLUSTER     Nombre del cluster ECS (default: etl-facturas-cluster)
    --skip-build              Saltar build y push de imágenes ECR
    --skip-terraform          Saltar terraform apply
    --skip-secrets            Saltar setup de secretos
    --skip-deploy             Saltar deployment de servicios ECS
    --skip-dags               Saltar sync de DAGs a S3
    --env-file FILE           Ruta al archivo .env (default: .env)
    -h, --help                Muestra esta ayuda

Ejemplos:
    $0
    $0 --region us-west-2
    $0 --skip-terraform --skip-dags

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

function log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

function check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 no está instalado o no está en PATH"
        return 1
    fi
    return 0
}

function check_prerequisites() {
    log_info "Validando prerrequisitos..."
    
    local missing=0
    
    if ! check_command aws; then
        missing=$((missing + 1))
    fi
    
    if ! check_command docker; then
        missing=$((missing + 1))
    fi
    
    if [ "$SKIP_TERRAFORM" != "true" ]; then
        if ! check_command terraform; then
            log_warning "Terraform no encontrado (se saltará si --skip-terraform está activo)"
        fi
    fi
    
    if [ $missing -gt 0 ]; then
        log_error "Faltan $missing prerrequisitos. Instálalos antes de continuar."
        return 1
    fi
    
    log_success "Todos los prerrequisitos están instalados"
    return 0
}

function confirm_deployment() {
    log_warning "=========================================="
    log_warning "DEPLOYMENT A AWS - CONFIRMACIÓN"
    log_warning "=========================================="
    log_warning "Este script realizará las siguientes acciones:"
    log_warning ""
    [ "$SKIP_BUILD" != "true" ] && log_warning "  ✓ Build y push de imágenes a ECR"
    [ "$SKIP_TERRAFORM" != "true" ] && log_warning "  ✓ Terraform apply (crear recursos AWS)"
    [ "$SKIP_SECRETS" != "true" ] && log_warning "  ✓ Setup de secretos en Secrets Manager"
    [ "$SKIP_DEPLOY" != "true" ] && log_warning "  ✓ Deployment de servicios ECS"
    [ "$SKIP_DAGS" != "true" ] && log_warning "  ✓ Sync de DAGs a S3 para MWAA"
    log_warning ""
    log_warning "Región: $AWS_REGION"
    log_warning "Cluster: $CLUSTER_NAME"
    log_warning "=========================================="
    echo ""
    read -p "¿Continuar con el deployment? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Deployment cancelado por el usuario"
        exit 0
    fi
}

# ========== CONFIGURACIÓN ==========
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="etl-facturas-cluster"
ENV_FILE=".env"
SKIP_BUILD=false
SKIP_TERRAFORM=false
SKIP_SECRETS=false
SKIP_DEPLOY=false
SKIP_DAGS=false

# Directorio raíz del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Archivo de log
LOG_FILE="$PROJECT_ROOT/deployment-$(date +%Y%m%d-%H%M%S).log"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -c|--cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-terraform)
            SKIP_TERRAFORM=true
            shift
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --skip-deploy)
            SKIP_DEPLOY=true
            shift
            ;;
        --skip-dags)
            SKIP_DAGS=true
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
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

# ========== INICIO ==========
log_info "=========================================="
log_info "DEPLOYMENT A AWS - INICIANDO"
log_info "=========================================="
log_info "Región: $AWS_REGION"
log_info "Cluster: $CLUSTER_NAME"
log_info "Log file: $LOG_FILE"
log_info "=========================================="

# Redirigir output a log file también
exec > >(tee -a "$LOG_FILE")
exec 2>&1

# Validar prerrequisitos
if ! check_prerequisites; then
    exit 1
fi

# Confirmación del usuario
confirm_deployment

# ========== PASO 1: BUILD Y PUSH ECR ==========
if [ "$SKIP_BUILD" != "true" ]; then
    log_step "1/5: Build y push de imágenes a ECR"
    
    BUILD_SCRIPT="$SCRIPT_DIR/../deployment/build-and-push-ecr.sh"
    if [ ! -f "$BUILD_SCRIPT" ]; then
        log_error "Script de build no encontrado: $BUILD_SCRIPT"
        exit 1
    fi
    
    if bash "$BUILD_SCRIPT" --region "$AWS_REGION"; then
        log_success "Build y push completado"
    else
        log_error "Error en build y push de imágenes"
        exit 1
    fi
else
    log_info "Saltando build y push de imágenes (--skip-build)"
fi

# ========== PASO 2: TERRAFORM ==========
if [ "$SKIP_TERRAFORM" != "true" ]; then
    log_step "2/5: Aplicar Terraform"
    
    TERRAFORM_DIR="$PROJECT_ROOT/infrastructure/terraform"
    if [ -d "$TERRAFORM_DIR" ] && [ -f "$TERRAFORM_DIR/main.tf" ]; then
        log_info "Ejecutando terraform apply..."
        cd "$TERRAFORM_DIR"
        
        if terraform init && terraform plan -out=tfplan && terraform apply tfplan; then
            log_success "Terraform apply completado"
        else
            log_error "Error en terraform apply"
            exit 1
        fi
        
        cd "$PROJECT_ROOT"
    else
        log_warning "Directorio de Terraform no encontrado o vacío, saltando..."
    fi
else
    log_info "Saltando Terraform (--skip-terraform)"
fi

# ========== PASO 3: SETUP SECRETOS ==========
if [ "$SKIP_SECRETS" != "true" ]; then
    log_step "3/5: Setup de secretos en Secrets Manager"
    
    SETUP_SECRETS_SCRIPT="$SCRIPT_DIR/setup-secrets.py"
    if [ ! -f "$SETUP_SECRETS_SCRIPT" ]; then
        log_error "Script de setup de secretos no encontrado: $SETUP_SECRETS_SCRIPT"
        exit 1
    fi
    
    ENV_PATH="$PROJECT_ROOT/$ENV_FILE"
    if [ ! -f "$ENV_PATH" ]; then
        log_warning "Archivo .env no encontrado: $ENV_PATH"
        log_warning "Saltando setup de secretos..."
    else
        if python3 "$SETUP_SECRETS_SCRIPT" --env "$ENV_PATH" --region "$AWS_REGION"; then
            log_success "Setup de secretos completado"
        else
            log_error "Error en setup de secretos"
            exit 1
        fi
    fi
else
    log_info "Saltando setup de secretos (--skip-secrets)"
fi

# ========== PASO 4: DEPLOY SERVICIOS ECS ==========
if [ "$SKIP_DEPLOY" != "true" ]; then
    log_step "4/5: Deployment de servicios ECS"
    
    DEPLOY_SCRIPT="$SCRIPT_DIR/../deployment/deploy-ecs-service.sh"
    if [ ! -f "$DEPLOY_SCRIPT" ]; then
        log_error "Script de deployment no encontrado: $DEPLOY_SCRIPT"
        exit 1
    fi
    
    # Desplegar cada servicio
    SERVICES=(
        "fastapi-service:aws/ecs/task-definitions/fastapi-service.json"
        "mlflow-service:aws/ecs/task-definitions/mlflow-server.json"
    )
    
    for SERVICE_CONFIG in "${SERVICES[@]}"; do
        SERVICE_NAME="${SERVICE_CONFIG%%:*}"
        TASK_DEF_FILE="${SERVICE_CONFIG##*:}"
        
        log_info "Desplegando servicio: $SERVICE_NAME"
        
        if bash "$DEPLOY_SCRIPT" \
            --service "$SERVICE_NAME" \
            --cluster "$CLUSTER_NAME" \
            --task-def "$PROJECT_ROOT/$TASK_DEF_FILE" \
            --region "$AWS_REGION"; then
            log_success "Servicio $SERVICE_NAME desplegado exitosamente"
        else
            log_error "Error desplegando servicio: $SERVICE_NAME"
            exit 1
        fi
    done
    
    log_success "Deployment de servicios completado"
else
    log_info "Saltando deployment de servicios (--skip-deploy)"
fi

# ========== PASO 5: SYNC DAGS A S3 ==========
if [ "$SKIP_DAGS" != "true" ]; then
    log_step "5/5: Sync de DAGs a S3 para MWAA"
    
    # Obtener bucket de MWAA desde Variables o usar default
    MWAA_BUCKET=$(aws mwaa get-environment \
        --name "${MWAA_ENVIRONMENT_NAME:-etl-facturas-airflow}" \
        --region "$AWS_REGION" \
        --query 'Environment.SourceBucketArn' \
        --output text 2>/dev/null | awk -F':::' '{print $NF}' | awk -F'/' '{print $NF}')
    
    if [ -z "$MWAA_BUCKET" ]; then
        log_warning "No se pudo obtener bucket de MWAA, usando variable MWAA_S3_BUCKET"
        MWAA_BUCKET="${MWAA_S3_BUCKET:-}"
    fi
    
    if [ -n "$MWAA_BUCKET" ]; then
        DAGS_DIR="$PROJECT_ROOT/airflow/dags"
        S3_DAGS_PATH="s3://$MWAA_BUCKET/dags"
        
        log_info "Sincronizando DAGs desde $DAGS_DIR a $S3_DAGS_PATH"
        
        if aws s3 sync "$DAGS_DIR" "$S3_DAGS_PATH" --delete --region "$AWS_REGION"; then
            log_success "DAGs sincronizados a S3"
        else
            log_error "Error sincronizando DAGs a S3"
            exit 1
        fi
    else
        log_warning "Bucket de MWAA no configurado, saltando sync de DAGs"
    fi
else
    log_info "Saltando sync de DAGs (--skip-dags)"
fi

# ========== FINALIZACIÓN ==========
log_success "=========================================="
log_success "DEPLOYMENT A AWS COMPLETADO EXITOSAMENTE"
log_success "=========================================="
log_info "Log guardado en: $LOG_FILE"
log_info ""
log_info "Próximos pasos:"
log_info "  1. Verificar servicios ECS en la consola AWS"
log_info "  2. Verificar DAGs en MWAA"
log_info "  3. Configurar alertas en CloudWatch"
log_info "  4. Probar endpoints de la API"

