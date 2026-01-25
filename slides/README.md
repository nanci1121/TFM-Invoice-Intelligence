# Presentación TFM - Invoice Intelligence

## 📊 Slides de la Presentación

Esta carpeta contiene la presentación del Trabajo Final de Máster usando **reveal.js**.

### 🚀 Cómo Ver las Slides

#### Opción 1: Abrir directamente en el navegador (Recomendado)
```bash
# Desde la raíz del proyecto
cd slides
python3 -m http.server 8080
```

Luego abre en tu navegador: `http://localhost:8080`

#### Opción 2: Abrir el archivo directamente
Simplemente abre `index.html` con tu navegador favorito:
```bash
firefox slides/index.html
# o
google-chrome slides/index.html
```

### ⌨️ Controles de Navegación

- **Flechas ←/→**: Navegar entre slides
- **Espacio**: Siguiente slide
- **Esc**: Vista general de todas las slides
- **F**: Pantalla completa
- **S**: Modo presentador (con notas)
- **?**: Ayuda con todos los atajos

### 📝 Estructura de la Presentación

La presentación contiene **17 slides**:

1. **Portada** - Título y datos del proyecto
2. **Índice** - Estructura de la presentación
3. **Contexto y Problema** - Desafíos actuales
4. **Solución Propuesta** - Invoice Intelligence
5. **Objetivos** - Objetivos del proyecto
6. **Arquitectura** - Diagrama del sistema
7. **Tecnologías** - Stack tecnológico
8. **Extracción Híbrida** - Proceso de extracción
9. **Workflows del Agente** - 6 workflows implementados
10. **Dashboard** - Interfaz principal
11. **Análisis de Facturas** - Proceso automatizado
12. **Chat Inteligente** - Consultas en lenguaje natural
13. **Resultados y Métricas** - Testing y rendimiento
14. **Privacidad y Seguridad** - 100% local
15. **Conclusiones** - Logros del proyecto
16. **Trabajo Futuro** - Mejoras propuestas
17. **Agradecimientos** - Preguntas

### ⏱️ Tiempo Estimado

- **Presentación completa**: 15-17 minutos
- **Con preguntas**: 20-25 minutos

### ✏️ Personalización

Para personalizar las slides, edita el archivo `index.html`:

1. **Tu nombre**: Busca `[Tu Nombre]` y reemplázalo
2. **Tu email**: Busca `[Tu email]` y añade tu contacto
3. **Colores**: Modifica la sección `<style>` para cambiar colores
4. **Contenido**: Edita el texto dentro de cada `<section>`

### 🎨 Temas Disponibles

Puedes cambiar el tema modificando esta línea en `index.html`:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4.5.0/dist/theme/black.css">
```

Temas disponibles:
- `black.css` (actual - fondo oscuro)
- `white.css` (fondo claro)
- `league.css` (gris oscuro)
- `beige.css` (beige suave)
- `sky.css` (azul cielo)
- `night.css` (negro con texto naranja)
- `serif.css` (fuente serif)
- `simple.css` (minimalista)
- `solarized.css` (solarized dark)

### 📤 Exportar a PDF

Para exportar las slides a PDF:

1. Abre las slides en Chrome/Chromium
2. Añade `?print-pdf` a la URL: `http://localhost:8080?print-pdf`
3. Usa Ctrl+P (Imprimir) y guarda como PDF

### 🔗 Enlaces Útiles

- **Documentación reveal.js**: https://revealjs.com/
- **GitHub del proyecto**: https://github.com/nanci1121/TFM-Invoice-Intelligence
- **Más temas**: https://github.com/hakimel/reveal.js/tree/master/css/theme

### 💡 Consejos para la Presentación

1. **Practica varias veces** antes de la defensa
2. **Usa el modo presentador** (tecla S) para ver notas
3. **Mantén 1 minuto por slide** aproximadamente
4. **Prepara respuestas** para preguntas comunes
5. **Ten una demo lista** por si te la piden

### 📊 Capturas de Pantalla

Si quieres añadir capturas de pantalla del dashboard:

1. Crea una carpeta `slides/images/`
2. Guarda tus capturas ahí
3. Añádelas en el HTML:
   ```html
   <img src="images/dashboard.png" alt="Dashboard" style="max-width: 80%;">
   ```

---

**Nota**: Las slides están diseñadas para una resolución de 1280x720 (16:9).
Si presentas en un proyector diferente, ajusta en la configuración de reveal.js.
