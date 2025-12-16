# 📈 Guía de Escalado

## 📋 Tabla de Contenidos

- [Cuándo Escalar](#cuándo-escalar)
- [Escalar Servicios ECS](#escalar-servicios-ecs)
- [Aumentar Recursos de RDS](#aumentar-recursos-de-rds)
- [Optimizar Costos](#optimizar-costos)
- [Tuning de Auto-scaling](#tuning-de-auto-scaling)
- [Performance Optimization](#performance-optimization)

---

## Cuándo Escalar

### Métricas a Observar

| Métrica | Threshold | Acción |
|---------|-----------|--------|
| **CPU Utilization** | > 70% por 5 min | Escalar horizontalmente |
| **Memory Utilization** | > 80% por 5 min | Aumentar memory o escalar |
| **Request Latency** | > 1s p95 | Escalar horizontalmente |
| **Error Rate** | > 1% | Investigar + escalar si necesario |
| **Queue Depth** | > 100 | Escalar workers |

### CloudWatch Dashboard

```bash
# Ver dashboard
aws cloudwatch get-dashboard \
  --dashboard-name etl-facturas-dashboard

# O desde Console:
# CloudWatch → Dashboards → etl-facturas-dashboard
```

---

## Escalar Servicios ECS

### Manual Scaling

```bash
# Aumentar desired count
aws ecs update-service \
  --cluster etl-facturas-cluster \
  --service fastapi-service \
  --desired-count 5

# Verificar escalado
aws ecs describe-services \
  --cluster etl-facturas-cluster \
  --services fastapi-service \
  --query 'services[0].runningCount' \
  --output text
```

### Auto-Scaling (Recomendado)

**Ya configurado en Terraform**, pero puedes ajustar:

```bash
# Ver políticas actuales
aws application-autoscaling describe-scaling-policies \
  --service-namespace ecs \
  --resource-id service/etl-facturas-cluster/fastapi-service

# Actualizar min/max capacity
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/etl-facturas-cluster/fastapi-service \
  --min-capacity 3 \
  --max-capacity 15
```

### Vertical Scaling (CPU/Memory)

```bash
# Actualizar task definition
aws ecs register-task-definition \
  --cli-input-json file://updated-task-def.json

# Actualizar servicio
aws ecs update-service \
  --cluster etl-facturas-cluster \
  --service fastapi-service \
  --task-definition fastapi-service:NEW_REVISION
```

---

## Aumentar Recursos de RDS

### Modificar Instance Class

```bash
# Ver instancia actual
aws rds describe-db-instances \
  --db-instance-identifier textil-db \
  --query 'DBInstances[0].[DBInstanceClass,AllocatedStorage]' \
  --output table

# Modificar (⚠️ Downtime durante modificación)
aws rds modify-db-instance \
  --db-instance-identifier textil-db \
  --db-instance-class db.t3.large \
  --apply-immediately
```

### Auto-Scaling de Storage

```bash
# Habilitar auto-scaling
aws rds modify-db-instance \
  --db-instance-identifier textil-db \
  --max-allocated-storage 1000 \
  --apply-immediately
```

### Read Replicas (Para Read Scaling)

```bash
# Crear read replica
aws rds create-db-instance-read-replica \
  --db-instance-identifier textil-db-replica \
  --source-db-instance-identifier textil-db
```

---

## Optimizar Costos

### SPOT Instances para Training

```bash
# Usar Fargate Spot (hasta 70% descuento)
aws ecs run-task \
  --cluster etl-facturas-cluster \
  --task-definition model-training \
  --capacity-provider-strategy \
    capacityProvider=FARGATE_SPOT,weight=1 \
    capacityProvider=FARGATE,weight=0
```

### Reserved Instances (RDS)

```bash
# Comprar Reserved Instance desde Console
# AWS Console → RDS → Reserved Instances → Purchase
# Ahorro: ~30-40% vs On-Demand
```

### Lifecycle Policies (S3)

```bash
# Ya configuradas en Terraform
# Verificar políticas
aws s3api get-bucket-lifecycle-configuration \
  --bucket mes-en-curso
```

### Right-Sizing

```bash
# Analizar uso real
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=fastapi-service \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum

# Si promedio < 30%, reducir CPU
```

---

## Tuning de Auto-scaling

### Ajustar Thresholds

```bash
# Actualizar política de CPU
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/etl-facturas-cluster/fastapi-service \
  --policy-name fastapi-cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    '{
      "TargetValue": 60.0,
      "PredefinedMetricSpecification": {
        "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
      },
      "ScaleInCooldown": 300,
      "ScaleOutCooldown": 60
    }'
```

### Cooldown Periods

- **Scale Out Cooldown**: 60s (escalar rápido cuando hay demanda)
- **Scale In Cooldown**: 300s (esperar antes de reducir, evitar thrashing)

---

## Performance Optimization

### Connection Pooling

```sql
-- En MySQL, verificar conexiones
SHOW PROCESSLIST;

-- Ajustar max_connections si es necesario
-- (Requiere modificar parameter group)
```

### Caching

```python
# Implementar Redis/ElastiCache para caching
# (No implementado actualmente, pero recomendado)
```

### CDN para Assets Estáticos

```bash
# Usar CloudFront para servir assets
# (No implementado actualmente)
```

---

**Última actualización**: Diciembre 2024

