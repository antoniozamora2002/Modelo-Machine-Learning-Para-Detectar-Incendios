# 🔥 Predicción de Incendios Forestales en San Martín, Perú

[![Python](https://img.shields.io/badge/Python-3.x-blue)](https://www.python.org/)

## 🎯 Descripción del Proyecto

Este repositorio alberga un proyecto de Machine Learning centrado en la **detección y predicción de incendios forestales en la región de San Martín, Perú**, utilizando datos satelitales (MODIS) de puntos de calor y puntos de control de no-incendio desde el año 2000 hasta 2024.

El objetivo principal es comparar la capacidad predictiva de diferentes algoritmos de clasificación para determinar la probabilidad de un incendio basándose únicamente en la ubicación (`lat/lon`) y las características temporales (`día del año`, `mes`, `año`).

> **Advertencia:** Si tu modelo predice que tu café está a punto de incendiarse, probablemente sea solo vapor. Pero en serio, las predicciones de incendios son mucho más fiables.

## 📁 Estructura del Repositorio

El corazón de este proyecto reside en la comparación de cuatro modelos de clasificación diferentes.

| Nombre del Notebook | Algoritmo | Propósito |
| :--- | :--- | :--- |
| `XGBoost-Model.ipynb` | **XGBoost (Gradient Boosting)** | Baseline de alto rendimiento. Ideal para desbalance de clases. |
| `Random-Forest-Model.ipynb` | **Random Forest** | Modelo de ensamble robusto, buen equilibrio entre rendimiento e interpretabilidad. |
| `Arbol-de-Decision-Model.ipynb` | **Árbol de Decisión** | El modelo más interpretable, usado para visualizar las reglas de clasificación. |
| `Regresion-Logistica-Model.ipynb` | **Regresión Logística** | Modelo lineal simple. Requiere pre-escalado de datos (StandardScaler). |

### Directorios Principales

* `Incendios/`: Contiene los datos satelitales de puntos de calor (clase 1) por año (`modis_AAAA_Peru.csv`).
* `NoIncendios/`: Contiene los datos de puntos de no-incendio (clase 0) por año.
* `ModelosGuardados/`: Modelos entrenados en formato `.json` o `.joblib`.

## ⚙️ Características (Features) Utilizadas

Las características del modelo se derivan de la fecha y ubicación de los eventos:

* `latitude`
* `longitude`
* `year`
* `month`
* `day`
* `day_of_year` (La característica más importante, ya que captura la estacionalidad de los incendios).

## 🚀 Instalación y Uso

### Requisitos

Asegúrate de tener instalado Python 3.x y las siguientes librerías (puedes instalarlas con pip):

```bash
pip install pandas numpy scikit-learn xgboost matplotlib seaborn jupyter joblib