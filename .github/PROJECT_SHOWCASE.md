# 🚀 ETL MLOps Cloud-Native en AWS - Showcase

## 📊 Resumen Ejecutivo

Sistema ETL empresarial con Machine Learning integrado, diseñado y construido 100% en AWS utilizando arquitectura cloud-native serverless.

**Stack Principal:** Terraform · AWS ECS Fargate · MWAA · TensorFlow · FastAPI · Docker · GitHub Actions

---

## 🎯 Problema y Solución

### Desafío
Procesar y clasificar miles de facturas textiles automáticamente, distinguiendo entre facturas correctivas y preventivas para optimizar operaciones.

### Solución
Sistema ETL cloud-native que combina:

- **Clasificación ML** con CNN custom (TensorFlow)
- **Extracción OCR** automatizada (Tesseract)
- **Orquestación** con Airflow managed (MWAA)
- **Escalamiento automático** basado en demanda
- **Monitoreo** completo con CloudWatch

---

## 🏗️ Arquitectura Técnica

### Infrastructure as Code
   📁 Terraform (2,317 líneas)

   ├─ 75+ recursos AWS automatizados
   ├─ Multi-AZ deployment
   ├─ Auto-scaling policies
   └─ 100% reproducible

### Compute Layer (Serverless)
   🐳 ECS Fargate

   ├─ FastAPI Service (2-10 tasks auto-scaled)
   ├─ MLflow Tracking (persistent)
   └─ Training Tasks (on-demand, 8 vCPU / 32GB)

   ⚖️ Application Load Balancer

   ├─ Health checks: /health
   ├─ SSL/TLS termination
   └─ Multi-AZ distribution

### Orchestration
   ✈️ Amazon MWAA (Managed Airflow)

   ├─ ETL Pipeline (hourly)
   ├─ Training Pipeline (on-demand)
   └─ Drift Detection (weekly)

### Data Layer
   💾 Storage

   ├─ Amazon S3 (facturas, modelos, artifacts)
   ├─ Amazon RDS MySQL (datos estructurados)
   └─ AWS Secrets Manager (credenciales)

   📊 ML/AI

   ├─ TensorFlow CNN (custom model)
   ├─ MLflow (experiment tracking)
   └─ DVC (model versioning)

### Observability
   📈 CloudWatch

   ├─ Logs centralizados (5 log groups)
   ├─ Métricas custom
   ├─ 8 alarmas configuradas
   └─ Dashboard integrado

---

## 💡 Highlights Técnicos

### Diseño Cloud-Native
✨ **100% Serverless** - Zero gestión de servidores (ECS Fargate, MWAA)
✨ **Infrastructure as Code** - Terraform para reproducibilidad completa
✨ **Multi-AZ** - Alta disponibilidad con deployment en múltiples zonas
✨ **Auto-scaling** - Escalamiento automático basado en CPU/memoria
✨ **Cost-optimized** - Lifecycle policies, spot instances, pay-per-use

### MLOps Pipeline
✨ **Automated training** - Reentrenamiento on-demand o scheduled
✨ **Drift detection** - Monitoreo semanal de data drift con tests estadísticos
✨ **Model versioning** - DVC con backend S3 para reproducibilidad
✨ **Experiment tracking** - MLflow para métricas y comparación de modelos
✨ **CI/CD integration** - Tests automáticos + quality gates (F1 > 0.85)

### DevOps Excellence
✨ **CI/CD completo** - GitHub Actions con 5 workflows automatizados
✨ **Multi-stage builds** - Docker images optimizadas (<500MB)
✨ **Health checks** - Endpoints custom para ALB y ECS
✨ **Monitoring** - CloudWatch logs, metrics, alarms
✨ **Security** - IAM roles, Secrets Manager, encryption at rest/transit

---

## 📈 Métricas del Proyecto

| Categoría | Métrica | Valor |
|-----------|---------|-------|
| **Código Total** | Líneas | ~12,000 |
| **Infrastructure as Code** | Terraform | 2,317 líneas |
| **Recursos AWS** | Automatizados | 75+ |
| **Documentación** | Líneas | 2,671 |
| **CI/CD** | Workflows | 5 |
| **Tests** | Cobertura | >85% |
| **Dockerfiles** | Optimizados | 3 |
| **Scripts** | Automation | 8 |

---

## 🛠️ Stack Tecnológico Completo

**Cloud & Infrastructure:**
- AWS (ECS Fargate, MWAA, RDS, S3, CloudWatch, Secrets Manager, ALB, ECR)
- Terraform (Infrastructure as Code)
- Docker (containerización)

**Backend & APIs:**
- Python 3.11
- FastAPI (async REST API)
- SQLAlchemy (ORM)
- Pydantic (validation)

**ML & Data:**
- TensorFlow / Keras (CNN model)
- Pandas, NumPy, SciPy
- Scikit-learn
- Tesseract OCR
- OpenCV
- MLflow (tracking)
- DVC (versioning)

**Orchestration:**
- Apache Airflow (MWAA)
- Airflow AWS Providers

**CI/CD:**
- GitHub Actions
- Pytest (testing)
- Docker multi-stage builds

---

## 🎓 Competencias Demostradas

### Cloud Architecture
✅ Diseño de arquitecturas serverless escalables
✅ Multi-AZ deployment para alta disponibilidad
✅ Cost optimization strategies
✅ Security best practices (IAM, encryption, secrets)

### Infrastructure as Code
✅ Terraform avanzado (2,300+ líneas, 75+ recursos)
✅ Modularización y reutilización
✅ State management (S3 backend + locking)
✅ Multi-environment deployments

### MLOps
✅ End-to-end ML pipeline (training, serving, monitoring)
✅ Automated retraining con drift detection
✅ Model versioning y experiment tracking
✅ CI/CD con quality gates

### DevOps
✅ CI/CD automation (GitHub Actions)
✅ Containerización (Docker multi-stage)
✅ Monitoring y observability (CloudWatch)
✅ Automated testing (pytest, coverage)

### Software Engineering
✅ Clean code y best practices
✅ Documentación técnica completa
✅ Type hints y validation
✅ Async/await patterns

---

## 📸 Assets Visuales

_Diagrams y screenshots serán agregados después del deployment_

- [ ] Diagrama de arquitectura AWS
- [ ] Screenshot de Terraform plan
- [ ] Screenshot de ECS Cluster
- [ ] CloudWatch Dashboard
- [ ] GitHub Actions workflows
- [ ] MLflow UI

---

## 📚 Documentación

- 📖 [README Principal](../README-PRODUCTION.md) - Overview y quick start
- 🏗️ [Arquitectura Detallada](../docs/architecture/architecture.md) - Decisiones técnicas
- 🚀 [Deployment Guide](../docs/deployment/deployment-guide.md) - Paso a paso
- 📊 [Infrastructure (Terraform)](../infrastructure/README.md) - IaC documentation

---

**Contacto:** [Tu nombre/email]
**LinkedIn:** [Tu perfil]
**GitHub:** [Tu usuario]

---

_Este proyecto demuestra capacidades profesionales en cloud architecture, MLOps, Infrastructure as Code, y DevOps automation, aplicando best practices de la industria en un caso de uso empresarial real._

