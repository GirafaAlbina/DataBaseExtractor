import sys
from .._exceptions import SenhaNaoEncontrada
from .vault import listar_cofre_windows


def obter_usuarios_config(banco_upper: str) -> tuple[str | None, list[str]]:
    from .._config import carregar_config

    try:
        config = carregar_config()
        for nome, cfg in config.items():
            if nome.strip().upper() == banco_upper:
                user_padrao = str(cfg["user"]).strip() if cfg.get("user") else None
                lista_users = [user_padrao] if user_padrao else []
                for u in cfg.get("users", []):
                    u_str = str(u).strip()
                    if u_str and u_str not in lista_users:
                        lista_users.append(u_str)
                return user_padrao, lista_users
    except Exception:
        pass
    return None, []


def resolver_usuario(banco_upper: str, usuario_informado: str | None, operacao: str) -> str:
    if usuario_informado and usuario_informado.strip():
        return usuario_informado.strip()

    if not (sys.stdin and sys.stdin.isatty()):
        raise SenhaNaoEncontrada(
            f"O parâmetro 'usuario' é obrigatório para '{banco_upper}' em modo não interativo."
        )

    user_padrao, lista_users = obter_usuarios_config(banco_upper)

    if user_padrao:
        resp = input(
            f"[db_extractor] O banco '{banco_upper}' está configurado com o usuário padrão '{user_padrao}'.\n"
            f"Deseja utilizar '{user_padrao}' para {operacao}? (S/n): "
        ).strip().lower()

        if resp in ("", "s", "sim", "y", "yes"):
            return user_padrao

    # Junta sugestões do 'users' no JSON com o que já existe no cofre do Windows
    salvos_cofre = [
        r["usuario"]
        for r in listar_cofre_windows(f"db_extractor_{banco_upper}*")
        if r["banco"] == banco_upper and r["usuario"]
    ]
    sugestoes = sorted(set(lista_users + salvos_cofre))
    if sugestoes:
        print(f"[db_extractor] Usuários disponíveis/cadastrados para '{banco_upper}': {', '.join(sugestoes)}")

    usuario_digitado = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()
    if not usuario_digitado:
        raise SenhaNaoEncontrada("O nome de usuário não pode ser vazio.")
    return usuario_digitado


def confirmar_acao(mensagem_prompt: str, mensagem_erro_nao_interativo: str) -> bool:
    if sys.stdin and sys.stdin.isatty():
        resposta = input(mensagem_prompt).strip().lower()
        return resposta in ("s", "sim", "y", "yes")
    raise SenhaNaoEncontrada(mensagem_erro_nao_interativo)