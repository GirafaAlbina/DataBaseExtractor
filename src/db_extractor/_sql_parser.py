import re
from typing import Any


_IDENTIFICADOR_VALIDO = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$.]*$")


def preparar_sql_e_binds(sql: str, parametros: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """
    Separa parâmetros em:
      1. Interpolação textual ({CHAVE}): para listas IN (...) e identificadores (tabelas/colunas).
      2. Bind variables (:CHAVE): repassadas de forma segura ao driver do banco.
    """
    if not parametros:
        return sql, {}

    sql_processado = sql
    binds: dict[str, Any] = {}

    for chave, valor in parametros.items():
        token = f"{{{chave}}}"

        if token in sql_processado:
            if isinstance(valor, (list, tuple, set)):
                if not valor:
                    raise ValueError(f"A lista para o parâmetro '{chave}' não pode ser vazia.")
                itens = ", ".join(
                    f"'{str(v).replace(chr(39), chr(39)*2)}'" if isinstance(v, str) else str(v)
                    for v in valor
                )
                sql_processado = sql_processado.replace(token, itens)
            else:
                identificador = str(valor).strip()
                if not _IDENTIFICADOR_VALIDO.match(identificador):
                    raise ValueError(
                        f"Identificador SQL inválido para '{{{chave}}}': '{identificador}'. "
                        "Use apenas letras, números, '_', '$' ou '.'."
                    )
                sql_processado = sql_processado.replace(token, identificador)
        else:
            if re.search(rf":{re.escape(chave)}\b", sql_processado):
                binds[chave] = valor

    return sql_processado, binds