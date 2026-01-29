---
description: despliegue de cambios a github (add, commit, push)
---

Este workflow automatiza el envío de cambios al repositorio remoto.

1. **Verificar rama actual**: Asegúrate de no estar en `main` si vas a subir una funcionalidad nueva.
2. **Añadir cambios**:
// turbo
```bash
git add .
```
3. **Confirmar cambios**: El asistente pedirá un mensaje descriptivo si no se proporciona.
// turbo
```bash
git commit -m "feat: [descripción de los cambios]"
```
4. **Subir cambios**:
// turbo
```bash
git push origin [nombre-de-la-rama]
```
5. **Enlace de Pull Request**: Al finalizar, el asistente proporcionará el enlace directo para abrir el PR en GitHub:
`https://github.com/nanci1121/TFM-Invoice-Intelligence/pull/new/[nombre-de-la-rama]`
