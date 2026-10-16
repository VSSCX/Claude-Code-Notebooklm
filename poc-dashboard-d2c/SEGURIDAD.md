# Seguridad y auditoría de datos

Este documento aplica el marco de «Auditoría de Datos y Pipelines de IA» (FEN U. de Chile, CLA11) al tablero. Cada riesgo del marco tiene un control, una prueba y la evidencia que la respalda. Lo que **no** está cubierto se declara al final.

## 1. Cómo publicar en Vercel sin exponer las bases

```
 Red privada (tu empresa)                         Internet
 ┌───────────────────────────────┐                ┌──────────────────────────────┐
 │ VTEX Azure   ODS SAP          │                │ Vercel                       │
 │      ▲ (solo lectura)         │                │  · login con rol + sesión    │
 │      │                        │   paquete      │  · lee el paquete cifrado    │
 │ publicar_snapshot.py ─────────┼─ cifrado ────► │  · NO tiene claves de bases  │
 │  calidad → minimizar → cifrar │  (Vercel Blob) │  · bitácora de auditoría     │
 └───────────────────────────────┘                └──────────────────────────────┘
```

1. **Claves** (en tu PC): `python seguridad_admin.py claves` → `SESSION_SECRET` y `SNAPSHOT_KEYS`.
2. **Usuarios**: `python seguridad_admin.py usuario ana@empresa.cl analista` (pide la clave sin mostrarla) → pegar la línea en `DASH_USUARIOS`.
3. **Vercel → Settings → Environment Variables** (marcar *Sensitive*): `DASH_USUARIOS`, `SESSION_SECRET`, `SNAPSHOT_KEYS`, `BLOB_READ_WRITE_TOKEN` (se crea en Storage → Blob). **No** se cargan `VTEX_*` ni `SAP_*`: Vercel nunca ve las bases.
4. **Vercel → Settings → Deployment Protection**: activar *Vercel Authentication* (segunda capa; protege también los archivos estáticos).
5. **En el PC de la red** (`.env` con `SNAPSHOT_KEYS`, `BLOB_READ_WRITE_TOKEN` y las claves de las bases, que son de **solo lectura**): `python publicar_snapshot.py --cada 300`. Para ensayar sin subir: `--simular`; sin bases: `--demo`.
6. Desplegar (`vercel --prod`). Con `SNAPSHOT_KEYS` + `BLOB_READ_WRITE_TOKEN` el tablero deja el modo demo y lee el último paquete; si no hay usuarios configurados el acceso queda **cerrado**.

Roles: **lector** (ve el tablero y pregunta al asistente) · **analista** (+ exporta CSV, calidad, linaje, valora respuestas) · **admin** (+ bitácora, diagnóstico, aprendizaje del asistente).

## 2. Matriz riesgo-control

| Riesgo (marco) | Control implementado | Prueba | Tipo | Evidencia |
|---|---|---|---|---|
| Mala calidad de datos | 18 reglas de calidad en el pipeline: unicidad, completitud, validez, exactitud, consistencia, conciliación pedidos↔líneas↔SAP, actualización, deriva de volumen y ticket (`app/calidad.py`). Una **falla rechaza la publicación**; una alerta se informa | `probar_seguridad.py` inyecta duplicados, montos negativos, status inválido, fechas futuras, líneas huérfanas y datos viejos | Preventivo + detectivo | `/api/calidad`, informe en el manifiesto, bitácora `publicacion_rechazada` |
| Integridad / manipulación | Paquete cifrado y autenticado (Fernet: AES + HMAC-SHA256); huella SHA-256 por tabla y del conjunto; el puntero guarda el hash del paquete; reemplazo atómico | Un byte alterado, otra clave o un paquete modificado en el almacén se **rechazan** | Preventivo | Pruebas de snapshot; `huella` en el manifiesto |
| Trazabilidad / linaje | Manifiesto por versión: id, fecha, periodo, origen lógico de cada tabla, filas, columnas incluidas/excluidas, huella, responsable, versión del código, calidad, excepción. Endpoint `/api/linaje` | Recorrido de punta a punta (sección 4) | Sustantivo | `/api/linaje`, manifiesto dentro de cada paquete |
| Procedencia | Cada tabla declara su fuente (VTEX Orders/OrderItems, ODS `od_pedidos_ingresados`, `dp_facturacion`, stock, maestra). Solo lectura (auditado en `auditar_seguridad.py` C03) | C03 | Preventivo | `snapshot.ORIGEN`, `queries.py` |
| Versionado de datos | Cada publicación tiene id `AAAAMMDDTHHMMSSZ-huella`; se conservan las últimas 10 y el puntero indica la vigente | Prueba de «versión nueva + anterior conservada» | Preventivo | Archivos `d2c-<id>.enc` |
| Acceso indebido | Autenticación con PBKDF2-SHA256 (240 000 iteraciones), sesión HMAC HttpOnly/Secure/SameSite=Strict que vence en 8 h, **RBAC** por ruta, bloqueo tras 5 intentos (usuario e IP), CSRF por origen, límite de uso por usuario, falla segura sin usuarios | `probar_seguridad.py` (28 pruebas de acceso); `auditar_seguridad.py` A01-A07 recorre **todas** las rutas `/api` | Preventivo + detectivo | Bitácora `login_*`, `acceso_denegado` |
| Revisión de accesos | `DASH_USUARIOS` es la única lista; quitar a alguien invalida sus sesiones al instante | «sesión de un usuario dado de baja: 401» | Detectivo | Revisión trimestral (sección 5) |
| Secretos y credenciales | Nada en el código ni en git (`.env` ignorado); claves solo en variables de entorno *Sensitive*; el hosting público **no tiene** claves de bases; cuentas de base de **solo lectura**; clave de cifrado con **rotación** (`SNAPSHOT_KEYS` admite varias; la primera cifra) | `auditar_seguridad.py` S01-S06 (archivos e **historial de git**) | Preventivo | Informe de evidencia |
| Cambio no aprobado | Todo cambio pasa por pull request y por CI (`.github/workflows/seguridad.yml`): pruebas del asistente, de seguridad, de Vercel y auditoría; el instalador verifica su SHA-256 | Pipeline en cada PR | Preventivo | Historial de PR y artefacto `evidencia-auditoria` |
| Drift de datos | Q13/Q14 comparan volumen y ticket de 7 d contra 28 d; el asistente además marca anomalías («¿qué debo revisar?») | Pruebas de calidad y de alertas | Detectivo | `/api/calidad` |
| Data poisoning | Fuente única validada (solo lectura), reglas de rango/outliers (Q05, Q06), paquete firmado: nadie puede inyectar datos en el almacén sin la clave | Prueba de paquete alterado | Preventivo + detectivo | Pruebas de snapshot |
| Fuga de datos (leakage) / segregación | **No hay entrenamiento de modelos con estos datos.** La IA opcional solo traduce la pregunta a un plan; con `IA_REDACTAR` recibe únicamente cifras ya agregadas de esa respuesta y se descarta todo texto con cifras que no estaban en los datos. Datos de ejemplo (sintéticos) en desarrollo y en demos | Pruebas de `ia.redactar` y `datos_para_redactar` | Preventivo | `uso_de_ia` en el manifiesto |
| Privacidad | Minimización: el paquete solo lleva columnas permitidas (se excluyen adjuntos y texto libre de las líneas); el tablero no maneja nombre, RUT ni dirección; la bitácora no guarda claves ni pedidos | Prueba «columnas excluidas» | Preventivo | `excluidas` en el manifiesto |
| Logging / monitoreo | Bitácora con **cadena de hashes** (editar o borrar un registro se detecta): logins, fallos, bloqueos, accesos denegados, exportaciones (quién, cuántas filas, qué filtros), preguntas al asistente, consultas administrativas, publicaciones y rechazos. En Vercel además sale por los logs de la función | Pruebas «editar/borrar se detecta»; `seguridad_admin.py verificar-auditoria` | Detectivo | `/api/auditoria`, `data/auditoria.jsonl` |
| Jobs fallidos sin alerta | `publicar_snapshot.py` registra cada fallo, reintenta con espera creciente y avisa por `ALERTA_WEBHOOK`; el tablero muestra «sin bases» si el paquete envejece | Pruebas de publicación rechazada | Detectivo | Bitácora `publicacion_error`, aviso |
| Lógica de transformación incorrecta (ETL/ELT) | Las transformaciones son las mismas consultas del .pbix y `modelo.py`; el tablero lee las tablas **crudas** del paquete y recalcula con el mismo código (ELT): se probó que el resultado es **idéntico** al de leer directo | Prueba «mismos resultados que leyendo directo» | Sustantivo | `probar_seguridad.py` |
| Pérdida o duplicado de registros | Conciliaciones Q02, Q11, Q12, Q15, Q16 | Pruebas de calidad | Detectivo | `/api/calidad` |
| Cadena de suministro | Dependencias con cota de versión, `pip-audit` en CI, librerías del navegador locales con **huella SHA-256**, sin CDN externos | `auditar_seguridad.py` D01-D04 | Preventivo | Informe de evidencia |
| Inyección y exportación | Consultas parametrizadas, `Sequence` validado, CSV neutraliza fórmulas (`=`, `+`, `-`, `@`), CSP estricta, sin `eval`/`exec`/`pickle`, `/docs` desactivado publicado | `auditar_seguridad.py` C01-C04, A03-A09 | Preventivo | Informe de evidencia |
| Sesgo | No aplica a decisiones sobre personas: el tablero y el asistente agregan pedidos, no puntúan clientes | — | — | — |

## 3. Evidencia que puede pedir un auditor

| Capa | Dónde está |
|---|---|
| Datos | Diccionario: `/api/linaje` (tablas, columnas, origen); calidad: `/api/calidad`; muestra: exportación CSV (queda en bitácora) |
| Pipelines | Código en git; configuración en `.env.example`; ejecuciones en la bitácora (`publicacion_ok`, `_error`, `_rechazada`) |
| Seguridad | Matriz de roles (sección 1); `DASH_USUARIOS`; accesos en `/api/auditoria` |
| Cambios | Pull requests, ejecuciones de CI, artefacto `EVIDENCIA_AUDITORIA.md` |
| Modelos | No hay modelos propios. La IA es un proveedor externo opcional (`IA_MODO`), sin entrenamiento con estos datos |
| Monitoreo | `/api/calidad`, aviso de `ALERTA_WEBHOOK`, alertas del asistente |

Generar el informe fechado: `python auditar_seguridad.py --informe EVIDENCIA_AUDITORIA.md`.

## 4. Pregunta crítica: ¿qué datos produjeron esta cifra?

Dado un número del tablero: (1) `/api/linaje` indica el paquete vigente, su periodo, su huella y cada tabla con su fuente; (2) el paquete `d2c-<id>.enc` se puede abrir con la clave y verificar tabla por tabla contra la huella; (3) la bitácora muestra quién lo publicó y cuándo; (4) la definición de cada indicador está en `modelo.py`, `ventas.py` (venta = monto del pedido repartido por línea) y `ASISTENTE.md`. El recorrido completo es reproducible.

## 5. Operación

- **Rotar `SNAPSHOT_KEYS`**: `python seguridad_admin.py rotar-clave`, anteponer la clave nueva (coma) en el PC y en Vercel, publicar; retirar la vieja cuando no queden paquetes cifrados con ella.
- **Rotar `SESSION_SECRET`**: cambiarlo cierra todas las sesiones.
- **Revisión de accesos**: cada trimestre comparar `DASH_USUARIOS` con la nómina y con los accesos de `/api/auditoria`; retirar lo que no se use.
- **Incidente**: cambiar `SESSION_SECRET` y `SNAPSHOT_KEYS`, revocar el token de Blob, revisar la bitácora (`seguridad_admin.py verificar-auditoria`), publicar de nuevo.
- **Excepciones**: `publicar_snapshot.py --excepcion "motivo"` permite publicar con controles en falla; el motivo queda en el manifiesto y en la bitácora.

## 6. Límites declarados (riesgo residual)

- La carga a **Vercel Blob** usa su API REST y no pudo probarse aquí con un token real; `SNAPSHOT_DIR` sí está probado de punta a punta. Probar con `--simular` y luego una publicación real antes de depender de ella.
- En Vercel el disco no persiste: la bitácora vive en los logs de la función. Para conservarla y que no se pueda alterar, configurar un **Log Drain** (Vercel → Settings → Log Drains).
- El bloqueo por intentos y el límite de uso están en memoria de cada instancia: frenan ataques simples, no uno distribuido. Para algo más fuerte, usar *Vercel Firewall / Rate Limiting*.
- Si se usa una IA externa, el texto de las preguntas del usuario sale de la red (y las cifras agregadas si `IA_REDACTAR=1`). Con Ollama local no sale nada.
- Los usuarios se gestionan en una variable de entorno: es simple y auditable, pero no tiene SSO ni doble factor. Si la empresa lo exige, usar *Vercel Authentication* con el proveedor de identidad corporativo como capa previa.
- El cifrado usa Fernet (AES-128). Es adecuado para este uso; si la política exige AES-256-GCM o un KMS, cambiar `snapshot._fernet` por ese servicio.
- La exposición que permanece en una instalación **solo local** sin `DASH_USUARIOS`: cualquiera en la misma red puede abrir el tablero. Configurar usuarios elimina ese riesgo.

## 7. Plan sugerido

| Plazo | Acción |
|---|---|
| 30 días | Crear usuarios y roles, publicar con `publicar_snapshot.py --cada 300`, activar Deployment Protection y el aviso `ALERTA_WEBHOOK`, usar cuentas de base de solo lectura |
| 60 días | Log Drain de Vercel, primera revisión de accesos, ensayo de rotación de claves |
| 90 días | Evaluar SSO/doble factor, firewall de Vercel, auditoría externa con el informe de evidencia |
