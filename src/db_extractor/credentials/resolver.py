import sys
from .._exceptions import SenhaNaoEncontrada
from .vault import listar_cofre_windows


def obter_usuario_config(banco_upper: str) -> str | None:
    from .._config import carregar_config

    try:
        config = carregar_config()
        for nome, cfg in config.items():
            if nome.strip().upper() == banco_upper:
                user_cfg = cfg.get("user")
                if user_cfg and str(user_cfg).strip():
                    return str(user_cfg).strip()
    except Exception:
        pass
    return None


def resolver_usuario(banco_upper: str, usuario_informado: str | None, operacao: str) -> str:
    if usuario_informado and usuario_informado.strip():
        return usuario_informado.strip()

    if not (sys.stdin and sys.stdin.isatty()):
        raise SenhaNaoEncontrada(
            f"O parâmetro 'usuario' é obrigatório para '{banco_upper}' em modo não interativo."
        )

    usuario_cfg = obter_usuario_config(banco_upper)
    if usuario_cfg:
        resp = input(
            f"[db_extractor] O banco '{banco_upper}' está configurado com o usuário '{usuario_cfg}' no config.json.\n"
            f"Deseja utilizar '{usuario_cfg}' para {operacao}? (S/n): "
        ).strip().lower()

        if resp in ("", "s", "sim", "y", "yes"):
            return usuario_cfg

        novo_user = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()
        if not novo_user:
            raise SenhaNaoEncontrada("O nome de usuário não pode ser vazio.")
        return novo_user

    salvos = [
        r["usuario"]
        for r in listar_cofre_windows(f"db_extractor_{banco_upper}*")
        if r["banco"] == banco_upper and r["usuario"]
    ]
    if salvos:
        print(f"[db_extractor] Usuários encontrados no cofre para '{banco_upper}': {', '.join(sorted(set(salvos)))}")

    usuario_digitado = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()
    if not usuario_digitado:
        raise SenhaNaoEncontrada("O nome de usuário não pode ser vazio.")
    return usuario_digitado


def confirmar_acao(mensagem_prompt: str, mensagem_erro_nao_interativo: str) -> bool:
    if sys.stdin and sys.stdin.isatty():
        resposta = input(mensagem_prompt).strip().lower()
        return resposta in ("s", "sim", "y", "yes")
    raise SenhaNaoEncontrada(mensagem_erro_nao_interativo)