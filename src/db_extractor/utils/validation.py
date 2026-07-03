import os
# db_extractor
from .._constants import CONSULTA_EXTENSIONS, OUTPUT_EXTENSIONS
from .._exceptions import (FormatoConsultaInvalido, FormatoSaidaInvalido, 
                          ChunksizeInvalido, NomePlanilhaInvalido,
                          BancoNaoEncontrado)


def validar_banco(banco, config):
    if banco not in config:
        raise BancoNaoEncontrado(f"Banco '{banco}' não encontrado.")
    

def validar_consulta(caminho):
    extensao = os.path.splitext(caminho)[1].lower()
    if extensao not in CONSULTA_EXTENSIONS:
        raise FormatoConsultaInvalido(f"Extensão inválida: {extensao}")
    

def validar_saida(saida):
    extensao = os.path.splitext(saida)[1].lower()
    if extensao not in OUTPUT_EXTENSIONS:
        raise FormatoSaidaInvalido(f"Formato de saída inválido: {extensao}")
    

def validar_chunksize(chunksize):
    if chunksize is None:
        return
    if not isinstance(chunksize, int):
        raise TypeError("chunksize deve ser inteiro.")
    if chunksize <= 0:
        raise ChunksizeInvalido("chunksize deve ser maior que zero.")
    

def validar_nome_planilha(nome_planilha):
    if len(nome_planilha) > 31:
        raise NomePlanilhaInvalido("Nome deve possuir até 31 caracteres.")