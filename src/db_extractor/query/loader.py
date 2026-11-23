import os
import sys
# db_extractor
from .._exceptions import ConsultaNaoEncontrada
from ..utils import normalizar_consulta, validar_consulta


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


def resolver_sql(consulta: str) -> str:
    """
    Aceita tanto o caminho/nome de um arquivo (.sql / .vql) quanto uma string SQL direta.
    - Se parecer caminho ou arquivo existente: normaliza, valida extensão/existência e lê o conteúdo.
    - Caso contrário: valida que não está vazia e retorna a própria query SQL.
    """
    if not isinstance(consulta, str) or not consulta.strip():
        raise ValueError("A consulta SQL não pode ser vazia.")

    texto = consulta.strip()
    parece_arquivo = (
        "\n" not in texto
        and (os.path.isfile(texto) or texto.lower().endswith((".sql", ".vql")))
    )

    if parece_arquivo:
        caminho = normalizar_consulta(texto)
        validar_consulta(caminho)
        return carregar_consulta(caminho)

    return texto