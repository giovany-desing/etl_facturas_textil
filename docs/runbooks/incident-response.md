# 🚨 Runbook de Incident Response

## 📋 Tabla de Contenidos

- [ECS Service Unhealthy](#ecs-service-unhealthy)
- [Training Job Failed](#training-job-failed)
- [Airflow DAG Failed](#airflow-dag-failed)
- [High Costs Alert](#high-costs-alert)
- [Database Connection Issues](#database-connection-issues)
- [Comandos Útiles](#comandos-útiles)
- [Logs Locations](#logs-locations)
- [Contactos de Escalation](#contactos-de-escalation)

---

## ECS Service Unhealthy

### Síntomas
- Health checks fallando en ALB
- Tasks en estado STOPPED
- Error 503 en endpoints

### Diagnóstico

```bash
# 1. Verificar estado del servicio
aws ecs describe-services \
  --cluster etl-facturas-cluster \
  --services fastapi-service \
  --query 'services[0].[status,runningCount,desiredCount]' \
  --output table

# 2. Ver eventos recientes
aws ecs describe-services \
  --cluster etl-facturas-cluster \
  --services fastapi-service \
  --query 'services[0].events[:5]' \
  --output table

# 3. Ver logs de CloudWatch
aws logs tail /ecs/fastapi --follow --since 10m

# 4. Verificar tasks fallidas
aws ecs list-tasks \
  --cluster etl-facturas-cluster \
  --service-name fastapi-service \
  --desired-status STOPPED \
  --query 'taskArns[:5]' \
  --output table
```

### Soluciones Comunes

**Problema: Imagen no encontrada**
```bash
# Verificar imagen existe en ECR
aws ecr describe-images \
  --repository-name etl-facturas-fastapi \
  --query 'imageDetails[0]' \
  --output json

# Si falta, rebuild y push
./scripts/deployment/build-and-push-ecr.sh
```

**Problema: Secrets Manager access denied**
```bash
# Verificar task execution role
aws iam get-role-policy \
  --role-name etl-facturas-ecs-task-execution-role \
  --policy-name ecs-task-execution-policy
```

**Problema: Health check fallando**
```bash
# Verificar endpoint /health
curl https://<alb-dns>/health

# Ver logs del contenedor
aws logs tail /ecs/fastapi --follow
```

### Escalation Path
1. Verificar logs → 2. Rollback si necesario → 3. Contactar equipo DevOps

---

## Training Job Failed

### Cómo Ver Logs en CloudWatch

```bash
# Ver logs de training
aws logs tail /ecs/model-training --follow --since 1h

# Buscar errores específicos
aws logs filter-log-events \
  --log-group-name /ecs/model-training \
  --filter-pattern "ERROR" \
  --since $(date -u -d '1 hour ago' +%s)000
```

### Errores Comunes y Soluciones

**Error: "Out of memory"**
- Solución: Aumentar memory en task definition (32768 → 40960)

**Error: "Model file not found"**
- Solución: Verificar DVC pull se ejecutó correctamente

**Error: "MySQL connection failed"**
- Solución: Verificar security groups y secrets

### Cómo Reintentar

```bash
# Desde MWAA: Re-trigger DAG
# O desde API:
curl -X POST https://<alb-dns>/train_model

# O manualmente desde ECS:
aws ecs run-task \
  --cluster etl-facturas-cluster \
  --task-definition model-training \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

---

## Airflow DAG Failed

### Acceso a Webserver MWAA

```bash
# Obtener URL del webserver
aws mwaa get-environment \
  --name etl-facturas-airflow \
  --query 'Environment.WebserverUrl' \
  --output text

# Credenciales: Ver Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id textil/airflow/webserver-credentials
```

### Ver Logs de Tasks

```bash
# Desde AWS Console: MWAA → Environment → Logs
# O desde CLI:
aws logs tail /aws/mwaa/etl-facturas-airflow --follow

# Filtrar por task específico
aws logs filter-log-events \
  --log-group-name /aws/mwaa/etl-facturas-airflow \
  --filter-pattern "task_id"
```

### Debugging de DAGs

```bash
# Validar sintaxis
python3 -m py_compile airflow/dags/etl_dag_aws.py

# Test DAG localmente
docker exec -it airflow-webserver airflow dags test etl_dag_aws 2024-01-01

# Ver variables de Airflow
aws mwaa get-environment \
  --name etl-facturas-airflow \
  --query 'Environment.AirflowConfigurationOptions' \
  --output json
```

---

## High Costs Alert

### Identificar Recursos Costosos

```bash
# Ver costos por servicio (últimos 7 días)
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-08 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE

# Ver costos de ECS
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-08 \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://filter-ecs.json
```

### Optimizaciones

**Reducir ECS Tasks**
```bash
# Reducir desired count
aws ecs update-service \
  --cluster etl-facturas-cluster \
  --service fastapi-service \
  --desired-count 1
```

**Usar Spot Instances para Training**
```bash
# Modificar task definition para usar Fargate Spot
aws ecs run-task \
  --capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1
```

**Limpiar ECR Images Antiguas**
```bash
# Lifecycle policies ya configuradas en Terraform
# Verificar políticas
aws ecr get-lifecycle-policy \
  --repository-name etl-facturas-fastapi
```

### Stop Recursos No Necesarios

```bash
# Detener servicios de desarrollo
aws ecs update-service \
  --cluster etl-facturas-cluster-dev \
  --service fastapi-service-dev \
  --desired-count 0
```

---

## Database Connection Issues

### Validar RDS Disponible

```bash
# Verificar estado de RDS
aws rds describe-db-instances \
  --db-instance-identifier textil-db \
  --query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address]' \
  --output table

# Debe mostrar: available
```

### Security Groups

```bash
# Verificar security groups de RDS
aws rds describe-db-instances \
  --db-instance-identifier textil-db \
  --query 'DBInstances[0].VpcSecurityGroups' \
  --output table

# Verificar reglas de entrada
aws ec2 describe-security-groups \
  --group-ids <rds-sg-id> \
  --query 'SecurityGroups[0].IpPermissions' \
  --output json

# Agregar regla si falta
aws ec2 authorize-security-group-ingress \
  --group-id <rds-sg-id> \
  --protocol tcp \
  --port 3306 \
  --source-group <ecs-sg-id>
```

### Secrets Manager Credentials

```bash
# Verificar secreto existe
aws secretsmanager describe-secret \
  --secret-id textil/mysql/credentials

# Obtener credenciales (solo para debugging)
aws secretsmanager get-secret-value \
  --secret-id textil/mysql/credentials \
  --query 'SecretString' \
  --output text | jq .

# Test conexión desde ECS task
aws ecs run-task \
  --cluster etl-facturas-cluster \
  --task-definition fastapi-service \
  --overrides '{
    "containerOverrides": [{
      "name": "fastapi",
      "command": ["python", "-c", "import mysql.connector; print(\"OK\")"]
    }]
  }'
```

---

## Comandos Útiles

### ECS

```bash
# Listar servicios
aws ecs list-services --cluster etl-facturas-cluster

# Ver detalles de task
aws ecs describe-tasks \
  --cluster etl-facturas-cluster \
  --tasks <task-arn>

# Ver eventos de servicio
aws ecs describe-services \
  --cluster etl-facturas-cluster \
  --services fastapi-service \
  --query 'services[0].events[:10]' \
  --output table
```

### CloudWatch

```bash
# Ver métricas
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=fastapi-service \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average

# Ver alarmas
aws cloudwatch describe-alarms \
  --alarm-name-prefix etl-facturas
```

### S3

```bash
# Ver contenido de bucket
aws s3 ls s3://mes-en-curso --recursive

# Ver tamaño de bucket
aws s3 ls s3://mes-en-curso --recursive --summarize --human-readable
```

---

## Logs Locations

| Servicio | Log Group | Cómo Acceder |
|----------|-----------|--------------|
| **FastAPI** | `/ecs/fastapi` | `aws logs tail /ecs/fastapi --follow` |
| **Training** | `/ecs/model-training` | `aws logs tail /ecs/model-training --follow` |
| **MLflow** | `/ecs/mlflow` | `aws logs tail /ecs/mlflow --follow` |
| **MWAA** | `/aws/mwaa/etl-facturas-airflow` | AWS Console → MWAA → Logs |
| **ALB** | S3 bucket `etl-facturas-alb-logs` | `aws s3 ls s3://etl-facturas-alb-logs` |

---

## Contactos de Escalation

### Nivel 1: Equipo de Desarrollo
- **Email**: mlops-team@textil.com
- **Slack**: #etl-facturas-aws
- **Response Time**: 1 hora

### Nivel 2: DevOps Team
- **Email**: devops@textil.com
- **Slack**: #devops-oncall
- **Response Time**: 30 minutos

### Nivel 3: AWS Support
- **Account Manager**: [contacto AWS]
- **Support Plan**: Business/Enterprise
- **Response Time**: Según plan

---

**Última actualización**: Diciembre 2024

