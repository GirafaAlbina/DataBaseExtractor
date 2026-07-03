import os
import sys
# db_extractor
from .._exceptions import ConsultaNaoEncontrada


def localizar_consulta(caminho):
    if os.path.isabs(caminho):
        if os.path.exists(caminho):
            return caminho

        raise ConsultaNaoEncontrada(f"Consulta não encontrada: {caminho}")

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    consulta_script = os.path.join(script_dir,caminho)
    if os.path.exists(consulta_script):
        return consulta_script

    consulta_cwd = os.path.join(os.getcwd(),caminho)
    if os.path.exists(consulta_cwd):
        return consulta_cwd

    raise ConsultaNaoEncontrada(f"Consulta não encontrada: {caminho}")


def carregar_consulta(caminho):
    consulta_path = localizar_consulta(caminho)
    try:
        with open(consulta_path,"r",encoding="utf-8") as f:
            return f.read()

    except UnicodeDecodeError:
        with open(consulta_path, "r", encoding="latin-1") as f:
            return f.read()