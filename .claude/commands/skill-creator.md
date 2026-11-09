# Skill Creator - Generador de Skills de Estudio para el Solemne

Genera un skill personalizado de estudio para un tema específico del solemne de **Desarrollo de Sistemas de Información (ENGIN410)**, consultando el notebook y construyendo un prompt reutilizable optimizado para responder preguntas de ese tema.

## Instrucciones

1. Recibe el tema o área del solemne que se quiere dominar
2. Consulta el notebook: `notebooklm ask "Explica en detalle el tema: <tema>. Dame definiciones, componentes, ejemplos y cómo se relaciona con el resto del curso."`
3. Con el contenido obtenido, genera un skill en formato markdown que incluya:
   - **Nombre del skill** (descriptivo)
   - **Contexto del tema**: resumen del contenido del notebook sobre ese tema
   - **Conceptos clave**: lista de términos y definiciones importantes
   - **Preguntas frecuentes de solemne** con sus respuestas modelo
   - **Instrucción de uso**: cómo aplicar el skill para responder preguntas

## Temas disponibles en el notebook

- Ciclo de Vida del Desarrollo de Sistemas (SDLC)
- Análisis de factibilidad (técnica, económica, organizacional)
- Estrategias de desarrollo: in-house, SaaS, outsourcing
- Metodologías: Cascada, Prototipos, XP/Agile
- Alineamiento estratégico del SI
- Roles del SI (organizacional, misión, soporte)
- Plan estratégico vs. táctico
- Requerimientos funcionales y no funcionales
- Enfoques de requerimientos (desempeño, reuso, modelos, características)
- Evolución arquitectónica de sistemas
- Proyecto imprenta mmg (aplicación práctica)

## Formato del skill generado

```markdown
# Skill: <nombre del tema>

## Contexto
<resumen del contenido del notebook>

## Conceptos Clave
- **<término>**: <definición>

## Preguntas Frecuentes
**P: <pregunta típica de solemne>**
R: <respuesta completa y correcta basada en el notebook>

## Cómo usar este skill
Cuando te hagan una pregunta sobre <tema>, aplica este contexto y responde usando los conceptos clave.
```

## Uso

```
/skill-creator <tema>
```

Ejemplo:
```
/skill-creator metodologías de desarrollo
```

$ARGUMENTS
