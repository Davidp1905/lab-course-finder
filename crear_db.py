import sqlite3
import os

# Crear carpeta 'data' si no existe
os.makedirs("data", exist_ok=True)

# Crear/conectar base de datos en data/cursos.sqlite
con = sqlite3.connect("data/cursos.sqlite")

# Ejecutar el script SQL desde sql/01_schema.sql
with open("sql/01_schema.sql", "r", encoding="utf-8") as f:
    con.executescript(f.read())

# Ejecutar el script SQL desde sql/02_queries_word_lookup.sql
# with open("sql/02_queries_word_lookup.sql", "r", encoding="utf-8") as f:
#     con.executescript(f.read())

# Guardar cambios y cerrar conexión
con.commit()
con.close()

print("DB creada en data/cursos.sqlite")
