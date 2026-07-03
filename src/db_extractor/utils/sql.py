import re


def extrair_aliases(sql):
    aliases = re.findall(r'AS\s+"([^"]+)"', sql, flags=re.IGNORECASE)
    return aliases


def expandir_parametros_lista(sql, parametros):
    if not parametros:
        return sql, parametros

    parametros_bind = {}
    for chave, valor in parametros.items():
        if isinstance(valor, (list, tuple, set)):

            if len(valor) == 0:
                raise ValueError("Lista vazia para {}".format(chave))
            placeholder = "{{{}}}".format(chave)
            if placeholder not in sql:
                raise ValueError("Placeholder {} não encontrado.".format(placeholder))
            itens = []

            for item in valor:
                if hasattr(item, "item"):
                    item = item.item()
                if isinstance(item, str):
                    itens.append("'{}'".format(item.replace("'", "''")))
                else:
                    itens.append(str(item))

            sql = sql.replace(placeholder, ",".join(itens))

        else:
            if hasattr(valor, "item"):
                valor = valor.item()
            parametros_bind[chave] = valor

    return sql, parametros_bind