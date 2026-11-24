# Validación de la clasificación IA con WSI de BACH

Fecha: 2026-11-24 · WSI: A03, A07, A05, A09, A10, A06 · Modelo: inceptionv3-bach-he (cpu) · Tiempo total: 866 s

Referencia: regiones anotadas por patólogos en las WSI de BACH (parte B). Cada región se clasificó con el mismo procedimiento que una anotación en la aplicación (ventana deslizante a la escala física del entrenamiento).

## Regiones anotadas por patólogos

### Nivel región (clase predominante)

| Real \ Predicha | Normal | Benigno | Carcinoma in situ | Carcinoma invasivo |
|---|---|---|---|---|
| Benigno | 1 | 12 | 5 | 4 |
| Carcinoma in situ | 0 | 1 | 7 | 0 |
| Carcinoma invasivo | 1 | 1 | 1 | 10 |

- Exactitud: **67.4 %** (n = 43)
- Exactitud equilibrada (media de sensibilidades): 73.0 %
- Carcinoma frente a no carcinoma: sensibilidad 85.7 %, especificidad 59.1 %

| Clase | Precisión | Sensibilidad | F1 | Soporte |
|---|---|---|---|---|
| Benigno | 85.7 % | 54.5 % | 0.67 | 22 |
| Carcinoma in situ | 53.8 % | 87.5 % | 0.67 | 8 |
| Carcinoma invasivo | 71.4 % | 76.9 % | 0.74 | 13 |

### Nivel campo (cada posición analizada)

| Real \ Predicha | Normal | Benigno | Carcinoma in situ | Carcinoma invasivo |
|---|---|---|---|---|
| Benigno | 152 | 523 | 178 | 208 |
| Carcinoma in situ | 13 | 85 | 381 | 19 |
| Carcinoma invasivo | 34 | 98 | 110 | 1059 |

- Exactitud: **68.6 %** (n = 2860)
- Exactitud equilibrada (media de sensibilidades): 69.1 %
- Carcinoma frente a no carcinoma: sensibilidad 87.2 %, especificidad 63.6 %

| Clase | Precisión | Sensibilidad | F1 | Soporte |
|---|---|---|---|---|
| Benigno | 74.1 % | 49.3 % | 0.59 | 1061 |
| Carcinoma in situ | 57.0 % | 76.5 % | 0.65 | 498 |
| Carcinoma invasivo | 82.3 % | 81.4 % | 0.82 | 1301 |

## Regiones anotadas + recuadros de tejido sin anotar (Normal)

### Nivel región (clase predominante)

| Real \ Predicha | Normal | Benigno | Carcinoma in situ | Carcinoma invasivo |
|---|---|---|---|---|
| Normal | 24 | 7 | 1 | 28 |
| Benigno | 1 | 12 | 5 | 4 |
| Carcinoma in situ | 0 | 1 | 7 | 0 |
| Carcinoma invasivo | 1 | 1 | 1 | 10 |

- Exactitud: **51.5 %** (n = 103)
- Exactitud equilibrada (media de sensibilidades): 64.7 %
- Carcinoma frente a no carcinoma: sensibilidad 85.7 %, especificidad 53.7 %

| Clase | Precisión | Sensibilidad | F1 | Soporte |
|---|---|---|---|---|
| Normal | 92.3 % | 40.0 % | 0.56 | 60 |
| Benigno | 57.1 % | 54.5 % | 0.56 | 22 |
| Carcinoma in situ | 50.0 % | 87.5 % | 0.64 | 8 |
| Carcinoma invasivo | 23.8 % | 76.9 % | 0.36 | 13 |

### Nivel campo (cada posición analizada)

| Real \ Predicha | Normal | Benigno | Carcinoma in situ | Carcinoma invasivo |
|---|---|---|---|---|
| Normal | 1854 | 1088 | 241 | 2556 |
| Benigno | 152 | 523 | 178 | 208 |
| Carcinoma in situ | 13 | 85 | 381 | 19 |
| Carcinoma invasivo | 34 | 98 | 110 | 1059 |

- Exactitud: **44.4 %** (n = 8599)
- Exactitud equilibrada (media de sensibilidades): 59.9 %
- Carcinoma frente a no carcinoma: sensibilidad 87.2 %, especificidad 53.2 %

| Clase | Precisión | Sensibilidad | F1 | Soporte |
|---|---|---|---|---|
| Normal | 90.3 % | 32.3 % | 0.48 | 5739 |
| Benigno | 29.2 % | 49.3 % | 0.37 | 1061 |
| Carcinoma in situ | 41.9 % | 76.5 % | 0.54 | 498 |
| Carcinoma invasivo | 27.6 % | 81.4 % | 0.41 | 1301 |

## Limitaciones

- El modelo se entrenó con imágenes de microscopía de BACH (parte A); BACH no documenta si las WSI de la parte B comparten pacientes con ellas.
- La etiqueta de una región se asigna a todas sus posiciones, aunque una región anotada puede incluir estroma u otros tejidos.
- El tejido sin anotar se toma como «Normal», que es una referencia más débil.
- Muestra pequeña (pocas WSI): los porcentajes tienen una incertidumbre alta.
