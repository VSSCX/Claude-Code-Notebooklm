"""Cubicaje: port a Python del cubicador VBA (Cubicación.bas, M_Cub_Core.bas, M_Visor3D.bas).

Regla del port: se replica el comportamiento del VBA instrucción por instrucción,
incluidas sus rarezas numéricas (redondeo bancario de CLng, Int = piso, tolerancias).
Cada modo se habilita solo cuando reproduce los casos de control capturados del Excel.
"""
