import sys
import keyring
from ._config import carregar_config
from ._exceptions import BancoNaoEncontrado, SenhaNaoEncontrada
from .utils import ler_senha_com_mascara


def _obter_usuario_do_config(banco: str) -> str:
    config = carregar_config()
    banco_upper = banco.strip().upper()
    for nome, cfg in config.items():
        if nome.upper() == banco_upper:
            return cfg.get("user")
    raise BancoNaoEncontrado(f"Banco '{banco}' não localizado no config.json.")


def cadastrar_credencial(banco: str, usuario: str = None, senha: str = None) -> None:
    banco_upper = banco.strip().upper()

    if not usuario:
        usuario = _obter_usuario_do_config(banco_upper)
        if not usuario:
            usuario = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()

    servico = f"db_extractor_{banco_upper}"
    senha_existente = keyring.get_password(servico, usuario)

    if senha_existente is not None:
        print(f"\n[db_extractor] O usuário '{usuario}' já possui credencial cadastrada para '{banco_upper}'.")
        if senha is None:
            resposta = input("Deseja sobrescrever a senha existente? (s/N): ").strip().lower()
            if resposta not in ("s", "sim", "y", "yes"):
                print("[db_extractor] Operação cancelada. A credencial existente foi mantida.")
                return

    if not senha:
        senha = ler_senha_com_mascara(f"Digite a senha para '{usuario}' ({banco_upper}): ")

    if not senha.strip():
        raise SenhaNaoEncontrada("A senha não pode ser vazia.")

    keyring.set_password(servico, usuario, senha)
    print(f"[db_extractor] Credencial cadastrada com sucesso para '{usuario}' em '{banco_upper}'.")


def alterar_senha(banco: str, usuario: str = None, nova_senha: str = None) -> None:
    banco_upper = banco.strip().upper()

    if not usuario:
        usuario = _obter_usuario_do_config(banco_upper)
        if not usuario:
            usuario = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()

    servico = f"db_extractor_{banco_upper}"
    senha_atual = keyring.get_password(servico, usuario)

    if not senha_atual:
        print(f"[db_extractor] Nenhuma senha anterior encontrada para '{usuario}' em '{banco_upper}'.")
        print("[db_extractor] Criando novo registro de senha...")
    else:
        print(f"[db_extractor] Alterando senha de '{usuario}' em '{banco_upper}'.")

    if not nova_senha:
        nova_senha = ler_senha_com_mascara(f"Digite a NOVA senha para '{usuario}' ({banco_upper}): ")
        confirmacao = ler_senha_com_mascara("Confirme a nova senha: ")
        if nova_senha != confirmacao:
            raise SenhaNaoEncontrada("As senhas digitadas não coincidem. Nenhuma alteração foi feita.")

    if not nova_senha.strip():
        raise SenhaNaoEncontrada("A nova senha não pode ser vazia.")

    keyring.set_password(servico, usuario, nova_senha)
    print(f"[db_extractor] Senha de '{usuario}' em '{banco_upper}' alterada com sucesso!")


def remover_credencial(banco: str, usuario: str = None) -> None:
    banco_upper = banco.strip().upper()

    if not usuario:
        usuario = _obter_usuario_do_config(banco_upper)

    servico = f"db_extractor_{banco_upper}"
    try:
        keyring.delete_password(servico, usuario)
        print(f"[db_extractor] Credencial de '{usuario}' em '{banco_upper}' removida do cofre.")
    except Exception:
        print("[db_extractor] Nenhuma credencial encontrada para remover.")