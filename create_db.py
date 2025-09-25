import sqlite3
import os

# Creates the 'data' directory if it doesn't exist.
os.makedirs("data", exist_ok=True)

# Create/connect to the database at data/cursos.sqlite
con = sqlite3.connect("data/cursos.sqlite")

# Execute the SQL script from sql/01_schema.sql
with open("sql/01_schema.sql", "r", encoding="utf-8") as f:
    con.executescript(f.read())

# Save changes and close connection
con.commit()
con.close()

print("DB created at data/cursos.sqlite")
