import json
import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect("data/lol_data.db")
cursor = conn.cursor()

# Obtener todos los campeones distintos que aparecen en las partidas
cursor.execute("SELECT DISTINCT champion FROM participantes ORDER BY champion")
champs = [row[0] for row in cursor.fetchall()]

conn.close()

# Crear el diccionario con clave = índice, valor = nombre
champs_dict = {i: name for i, name in enumerate(champs)}

# Guardar en assets/campeones.json con UTF-8 sin BOM
with open("assets/campeones.json", "w", encoding="utf-8") as f:
    json.dump(champs_dict, f, indent=2, ensure_ascii=False)

print(f"✅ Archivo 'campeones.json' regenerado con {len(champs)} campeones.")