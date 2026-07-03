# db_extractor
from .._exceptions import ConexaoNaoIdentificado
# connection
from .oracle import criar_conexao as criar_conexao_oracle
from .denodo import criar_conexao as criar_conexao_denodo


def criar_conexao(cfg):
    if "service" in cfg:
        return criar_conexao_oracle(cfg)
    if "database" in cfg:
        return criar_conexao_denodo(cfg)
    raise ConexaoNaoIdentificado("Tipo de conexão não identificado.")