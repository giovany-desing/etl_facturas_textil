# 🚀 Workflows de GitHub Actions - Proyecto ETL Facturas

Esta carpeta contiene los workflows de GitHub Actions para automatizar el testing y la validación del proyecto.

## 📋 Workflows Definidos

### 1. **`tests.yml` - Tests Completos**
- **Descripción**: Ejecuta todos los tests unitarios, de integración y de estabilidad de la API.
- **Objetivo**: Asegurar la calidad del código y la funcionalidad de la aplicación.
- **Triggers**:
  - `push` a las ramas `main`, `develop`, `master`
  - `pull_request` a las ramas `main`, `develop`, `master`
  - `workflow_dispatch` (ejecución manual)
- **Características**:
  - Ejecuta todos los tests en `tests/`
  - Genera reportes de cobertura
  - Sube resultados a Codecov (opcional)
  - Timeout: 30 minutos
  - **NO puede fallar**: Si los tests fallan, el workflow falla

### 2. **`ci-validation.yml` - Validación CI Crítica**
- **Descripción**: Ejecuta tests críticos de validación (`test_ci_validation.py`) que validan métricas del modelo, comparación con baseline y calidad de datos.
- **Objetivo**: Actuar como un "gate" de calidad en el pipeline de CI/CD. Si estos tests fallan, el proceso de integración continua (y potencialmente el despliegue) debe detenerse.
- **Triggers**:
  - `push` a las ramas `main`, `develop`, `master`
  - `pull_request` a las ramas `main`, `develop`, `master`
  - `workflow_dispatch` (ejecución manual)
- **Características**:
  - Ejecuta solo `tests/test_ci_validation.py`
  - Validación de métricas (F1 > 0.85)
  - Comparación con baseline
  - Validación de datos
  - Timeout: 20 minutos
  - **NO puede fallar**: Si la validación falla, el CD se detiene

## ⚙️ Configuración y Dependencias

- **Python Version**: Ambos workflows utilizan Python 3.11.
- **Dependencies**: Instalan las dependencias listadas en `requirements.txt`, además de las dependencias específicas de testing (`pytest`, `pytest-cov`, `moto`, `httpx`).
- **MySQL Service**: Ambos workflows configuran un servicio MySQL para los tests de integración con la base de datos.
- **Environment Variables**: Se configuran variables de entorno de prueba (incluyendo credenciales AWS mockeadas y configuración MySQL) para los tests.

## 📊 Reportes y Artefactos

- **Cobertura de Código**: El workflow `tests.yml` genera un reporte de cobertura en formato XML (`coverage.xml`) y HTML (`htmlcov/`). El reporte XML se puede subir a Codecov (requiere `CODECOV_TOKEN`). El reporte HTML se sube como un artefacto de GitHub Actions.
- **Resultados de Tests**: Los logs de los tests se pueden ver directamente en la salida del workflow.

## ⚠️ Notas Importantes

- **Fallo Crítico**: Si el workflow `ci-validation.yml` falla, indica un problema grave con el modelo o los datos, y el pipeline de CI/CD debe detenerse.
- **Credenciales AWS**: Para los tests de S3, se utilizan credenciales AWS mockeadas (`testing`). Para interacciones reales con AWS en otros contextos (ej. DVC push), se deben configurar los secrets de GitHub Actions (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`).
- **Secrets**: Si se utiliza Codecov, el `CODECOV_TOKEN` debe configurarse como un secret en el repositorio de GitHub (opcional).
- **MySQL**: Los workflows esperan hasta 90 intentos (3 minutos) para que MySQL esté listo antes de ejecutar los tests.

## 🔧 Troubleshooting

### Problema: Tests fallan en GitHub Actions pero pasan localmente
- Verificar que todas las variables de entorno estén configuradas
- Verificar que MySQL esté disponible y accesible
- Revisar los logs del workflow para ver errores específicos

### Problema: CI Validation falla
- Revisar que `tests/test_ci_validation.py` exista y tenga los tests correctos
- Verificar que las métricas del modelo cumplan con los umbrales (F1 > 0.85)
- Verificar que el baseline esté configurado correctamente

---

**Última actualización:** 2024  
**Versión del proyecto:** 2.0.0


