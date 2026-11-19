from .vault import (
    servico_composto, 
    servico_legado, 
    listar_cofre_windows, 
    obter_senha_cofre, 
    salvar_senha_cofre, 
    remover_senha_cofre
)
from .resolver import (
    obter_usuario_config,
    resolver_usuario,
    confirmar_acao
)

__all__ = [
    "servico_composto",
    "servico_legado",
    "listar_cofre_windows",
    "obter_senha_cofre",
    "salvar_senha_cofre",
    "remover_senha_cofre",
    "obter_usuario_config",
    "resolver_usuario",
    "confirmar_acao"
]