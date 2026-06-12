import ast


def main():
    with open("app.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    extracted = []
    
    # Imports necesarios para el modulo extraido
    extracted.append("import random\n")

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name in ["_generar_filosofia_juego", "_generar_practica_deliberada", "_generar_tips_salud", "generar_reporte_coach"]:
                extracted.append(ast.unparse(node))

    with open("src/coaching_ia.py", "w", encoding="utf-8") as f:
        f.write("\n".join(extracted))
        
if __name__ == "__main__":
    main()
