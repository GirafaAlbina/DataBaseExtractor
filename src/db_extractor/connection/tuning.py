

def configurar_buffer_cursor(cursor, motor: str, arraysize: int = 50_000) -> None:
    """Ajusta prefetch e fetch array para maximizar vazão de rede."""
    motor_upper = motor.upper()

    if motor_upper == "ORACLE":
        cursor.arraysize = arraysize
        cursor.prefetchrows = arraysize
    elif motor_upper == "DENODO":
        # Para psycopg2 (especialmente server-side cursors)
        if hasattr(cursor, "itersize"):
            cursor.itersize = arraysize