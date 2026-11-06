# src/db_extractor/utils/terminal.py
import sys

def ler_senha_com_mascara(prompt: str = "Senha: ") -> str:
    """Lê a senha no terminal exibindo asteriscos (*) enquanto o usuário digita."""
    sys.stdout.write(prompt)
    sys.stdout.flush()

    if sys.platform == "win32":
        import msvcrt
        senha = []
        while True:
            char = msvcrt.getch()
            if char in (b"\r", b"\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                break
            elif char == b"\x08":  # Backspace
                if senha:
                    senha.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif char == b"\x03":  # Ctrl+C
                raise KeyboardInterrupt
            else:
                try:
                    senha.append(char.decode("utf-8"))
                    sys.stdout.write("*")
                    sys.stdout.flush()
                except UnicodeDecodeError:
                    pass
        return "".join(senha)
