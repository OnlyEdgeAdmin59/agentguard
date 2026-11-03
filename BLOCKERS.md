# Bloqueos

## 2026-11-02: holdout v2 ciego (tarea 1), no se pudo crear
- **Qué pasó:** el subagente que arma el holdout v2 a ciegas fue frenado por un filtro de seguridad dos veces. La primera fue al escribir los 50 casos maliciosos. La segunda, al escribir solo la mitad benigna. No se creó nada: `tests/corpus_holdout_v2/` no existe y `reports/holdout_v2_antes.md` tampoco.
- **Decisión:** no reintentarlo ni buscarle la vuelta (otro agente, otra redacción, escribirlo yo con los casos a la vista). Si un filtro de seguridad lo frena, no se sortea. Además, si los escribo yo después de ver las reglas, deja de ser ciego.
- **Efecto:** el rediseño por familias (tarea 2) se ajustó solo con `tests/corpus/` y el control de ruido en skills reales. La tarea 4 no tiene un holdout ciego nuevo. Como referencia se mide el holdout v1, que ya estaba usado: no es ciego y no prueba que no haya sobreajuste.
- **Para destrabarlo (lo decide Charlie):**
  1. Usar un benchmark público de prompt injection / tool poisoning, respetando su licencia. Bajarlo requiere tu aprobación (archivo, fuente y tamaño).
  2. O que una persona escriba los casos a mano en `tests/corpus_holdout_v2/{benign,malicious}/`, sin ver las reglas, con el formato de `tests/corpus/README.md`.
- **Resuelto (2026-11-02):** Charlie eligió el benchmark público `deepset/prompt-injections` (Apache 2.0). Ver `tests/corpus_holdout_v2/README.md` y `reports/holdout_v2_antes.md`.

## 2026-11-02: rediseño por familias (tarea 2), detenido
- **Qué pasó:** al escribir el módulo nuevo de señales por familia, un filtro de seguridad frenó mi respuesta. Quedó un archivo a medio escribir, sin seguimiento en git, y lo quité. El scanner quedó igual que en el commit anterior y los tests pasan.
- **Decisión:** mismo criterio que arriba: no se reintenta ni se reformula para sortear el filtro.
- **Efecto:** no se hicieron las tareas 2 a 4 (familias, control de ruido de cada cambio, holdout v2 después). La herramienta de control de ruido (`scripts/ruido_skills.py` + `reports/ruido_base.json`) sí quedó lista para cuando se retome.
- **Para destrabarlo (lo decide Charlie):** que el rediseño lo escriba una persona, o seguirlo en otra sesión con supervisión directa tuya. La base de ruido ya está guardada.
