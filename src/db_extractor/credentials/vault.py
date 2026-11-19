import sys
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import keyring


def servico_composto(banco: str, usuario: str) -> str:
    return f"db_extractor_{banco.strip().upper()}_{usuario.strip().upper()}"


def servico_legado(banco: str) -> str:
    return f"db_extractor_{banco.strip().upper()}"


def _filetime_para_str(ft: wintypes.FILETIME) -> str:
    ticks = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
    if ticks == 0:
        return "-"
    unix_ts = (ticks - 116_444_736_000_000_000) / 10_000_000
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")


def listar_cofre_windows(filtro: str = "db_extractor*") -> list[dict]:
    if sys.platform != "win32":
        return []

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    PCREDENTIAL = ctypes.POINTER(CREDENTIAL)
    advapi32 = ctypes.WinDLL("advapi32.dll")

    cred_enumerate = advapi32.CredEnumerateW
    cred_enumerate.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.POINTER(PCREDENTIAL)),
    ]
    cred_enumerate.restype = wintypes.BOOL

    cred_free = advapi32.CredFree
    cred_free.argtypes = [ctypes.c_void_p]

    count = wintypes.DWORD(0)
    creds_ptr = ctypes.POINTER(PCREDENTIAL)()
    registros = []

    if cred_enumerate(filtro, 0, ctypes.byref(count), ctypes.byref(creds_ptr)):
        try:
            for i in range(count.value):
                c = creds_ptr[i].contents
                target = c.TargetName or ""
                user = (c.UserName or "").strip()

                sem_prefixo = target[len("db_extractor_"):] if target.startswith("db_extractor_") else target
                if user and sem_prefixo.upper().endswith(f"_{user.upper()}"):
                    banco = sem_prefixo[: -(len(user) + 1)]
                else:
                    banco = sem_prefixo

                registros.append({
                    "banco": banco.upper(),
                    "usuario": user,
                    "servico": target,
                    "atualizado_em": _filetime_para_str(c.LastWritten),
                })
        finally:
            cred_free(creds_ptr)

    return registros


def obter_senha_cofre(banco: str, usuario: str) -> tuple[str | None, str]:
    srv_comp = servico_composto(banco, usuario)
    senha = keyring.get_password(srv_comp, usuario)
    if senha is not None:
        return senha, srv_comp

    srv_leg = servico_legado(banco)
    senha = keyring.get_password(srv_leg, usuario)
    if senha is not None:
        return senha, srv_leg

    return None, srv_comp


def salvar_senha_cofre(banco: str, usuario: str, senha: str, servico_anterior: str | None = None) -> str:
    srv_novo = servico_composto(banco, usuario)
    keyring.set_password(srv_novo, usuario, senha)

    if servico_anterior and servico_anterior != srv_novo:
        try:
            keyring.delete_password(servico_anterior, usuario)
        except Exception:
            pass

    return srv_novo


def remover_senha_cofre(servico: str, usuario: str) -> None:
    keyring.delete_password(servico, usuario)