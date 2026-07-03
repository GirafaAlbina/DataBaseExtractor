
def normalizar_banco(banco):
    if banco is None:
        return None
    return banco.strip().upper()


def normalizar_consulta(consulta):
    if consulta is None:
        return None
    return consulta.strip()


def normalizar_saida(saida):
    if saida is None:
        return None
    return saida.strip()


def normalizar_nome_planilha(nome_planilha):
    if not nome_planilha:
        return "Dados"
    return nome_planilha.strip()


def normalizar_chunksize(chunksize):
    if chunksize in (None, ""):
        return None
    return int(chunksize)