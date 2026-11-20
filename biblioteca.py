"""Aplicación CLI de biblioteca personal usando KeyDB (compatible con Redis) y redis-py."""

from datetime import datetime, timezone
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
import redis
from redis.exceptions import (
    AuthenticationError,
    ConnectionError as RedisConnectionError,
    RedisError,
    TimeoutError as RedisTimeoutError,
)

PREFIJO_CLAVE = "libro:"
CLAVE_CONTADOR = "contador:libros"
ESTADOS_VALIDOS = ("Pendiente", "Leyendo", "Leído")
MAPA_ESTADOS = {
    "pendiente": "Pendiente",
    "leyendo": "Leyendo",
    "leido": "Leído",
    "leído": "Leído",
}


def validar_texto_no_vacio(valor: Any, nombre_campo: str) -> str:
    """Valida que un campo sea texto no vacío."""
    if not isinstance(valor, str):
        raise ValueError(f"El campo '{nombre_campo}' debe ser texto.")
    limpio = valor.strip()
    if not limpio:
        raise ValueError(f"El campo '{nombre_campo}' no puede estar vacío.")
    return limpio


def normalizar_estado(estado: Any) -> str:
    """Valida y normaliza el estado de lectura."""
    texto = validar_texto_no_vacio(estado, "estado_lectura").lower()
    if texto not in MAPA_ESTADOS:
        opciones = ", ".join(ESTADOS_VALIDOS)
        raise ValueError(
            f"Estado de lectura inválido: '{estado}'. Opciones válidas: {opciones}."
        )
    return MAPA_ESTADOS[texto]


def validar_libro(datos: Any) -> dict[str, Any]:
    """Valida la estructura esperada de un libro antes de serializarlo a JSON."""
    if not isinstance(datos, dict):
        raise ValueError("El libro debe ser un diccionario válido.")

    campos_requeridos = ("titulo", "autor", "genero", "estado_lectura")
    faltantes = [campo for campo in campos_requeridos if campo not in datos]
    if faltantes:
        raise ValueError(
            f"Estructura inválida. Faltan los campos: {', '.join(faltantes)}."
        )

    return {
        "titulo": validar_texto_no_vacio(datos["titulo"], "titulo"),
        "autor": validar_texto_no_vacio(datos["autor"], "autor"),
        "genero": validar_texto_no_vacio(datos["genero"], "genero"),
        "estado_lectura": normalizar_estado(datos["estado_lectura"]),
    }


def construir_clave(id_libro: str) -> str:
    """Normaliza el ID ingresado y devuelve la clave completa 'libro:<id>'."""
    limpio = id_libro.strip()
    if not limpio:
        raise ValueError("El ID del libro no puede estar vacío.")
    if limpio.startswith(PREFIJO_CLAVE):
        return limpio
    return f"{PREFIJO_CLAVE}{limpio}"


def conectar_keydb() -> redis.Redis:
    """Carga variables del archivo .env y establece la conexión con KeyDB."""
    load_dotenv()

    host = os.getenv("KEYDB_HOST", "localhost").strip()
    puerto_str = os.getenv("KEYDB_PORT", "6379").strip()
    password = os.getenv("KEYDB_PASSWORD", "").strip() or None
    db_str = os.getenv("KEYDB_DB", "0").strip()
    usar_ssl = os.getenv("KEYDB_SSL", "false").strip().lower() in ("true", "1", "yes", "si")

    try:
        puerto = int(puerto_str)
        db_num = int(db_str)
    except ValueError as exc:
        raise ConnectionError(
            "KEYDB_PORT y KEYDB_DB deben ser números enteros en el archivo .env."
        ) from exc

    try:
        cliente = redis.Redis(
            host=host,
            port=puerto,
            password=password,
            db=db_num,
            ssl=usar_ssl,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        cliente.ping()
        return cliente
    except AuthenticationError as exc:
        raise ConnectionError(
            "Error de autenticación con KeyDB. Revisa KEYDB_PASSWORD en tu archivo .env."
        ) from exc
    except (RedisConnectionError, RedisTimeoutError) as exc:
        raise ConnectionError(
            f"No se pudo conectar con KeyDB en {host}:{puerto}. "
            "Verifica que el servicio esté activo y revisa tu archivo .env."
        ) from exc
    except RedisError as exc:
        raise ConnectionError(f"Error inesperado al conectar con KeyDB: {exc}") from exc


def obtener_libro_por_clave(cliente: redis.Redis, clave: str) -> dict[str, Any] | None:
    """Obtiene y deserializa un libro desde KeyDB usando GET."""
    raw = cliente.get(clave)
    if raw is None:
        return None
    try:
        datos = json.loads(raw)
        if not isinstance(datos, dict):
            return None
        return datos
    except json.JSONDecodeError:
        print(f"Advertencia: El valor almacenado en '{clave}' no es un JSON válido.")
        return None


def obtener_todos_los_libros(cliente: redis.Redis) -> list[tuple[str, dict[str, Any]]]:
    """Recorre todas las claves 'libro:*' usando SCAN y devuelve los libros deserializados."""
    libros: list[tuple[str, dict[str, Any]]] = []
    cursor = 0
    while True:
        cursor, claves = cliente.scan(cursor=cursor, match=f"{PREFIJO_CLAVE}*", count=100)
        for clave in claves:
            libro = obtener_libro_por_clave(cliente, clave)
            if libro is not None:
                libros.append((clave, libro))
        if cursor == 0:
            break

    libros.sort(key=lambda item: str(item[1].get("titulo", "")).lower())
    return libros


def formatear_libro(clave: str, libro: dict[str, Any]) -> str:
    """Formatea un libro para mostrarlo en consola."""
    id_corto = clave.removeprefix(PREFIJO_CLAVE)
    return (
        f"ID: {id_corto} (clave: {clave})\n"
        f"  Título: {libro.get('titulo', 'Sin título')}\n"
        f"  Autor:  {libro.get('autor', 'Desconocido')}\n"
        f"  Género: {libro.get('genero', 'No especificado')}\n"
        f"  Estado: {libro.get('estado_lectura', 'No especificado')}"
    )


def solicitar_campo_obligatorio(etiqueta: str) -> str:
    """Solicita un campo de texto obligatorio hasta recibir un valor válido."""
    while True:
        valor = input(f"{etiqueta}: ")
        try:
            return validar_texto_no_vacio(valor, etiqueta)
        except ValueError as err:
            print(f"Error: {err}")


def solicitar_estado_lectura(permitir_vacio: bool = False) -> str | None:
    """Solicita el estado de lectura mostrando las opciones permitidas."""
    opciones = " / ".join(ESTADOS_VALIDOS)
    while True:
        entrada = input(f"Estado de lectura ({opciones}): ")
        if permitir_vacio and not entrada.strip():
            return None
        try:
            return normalizar_estado(entrada)
        except ValueError as err:
            print(f"Error: {err}")


def agregar_libro(cliente: redis.Redis) -> None:
    """Agrega un nuevo libro serializado en JSON con SET y clave única libro:<id>."""
    print("\n--- Agregar nuevo libro ---")
    titulo = solicitar_campo_obligatorio("Título")
    autor = solicitar_campo_obligatorio("Autor")
    genero = solicitar_campo_obligatorio("Género")
    estado = solicitar_estado_lectura()

    try:
        libro = validar_libro(
            {
                "titulo": titulo,
                "autor": autor,
                "genero": genero,
                "estado_lectura": estado,
            }
        )
        nuevo_id = cliente.incr(CLAVE_CONTADOR)
        clave = f"{PREFIJO_CLAVE}{nuevo_id}"
        ahora = datetime.now(timezone.utc).isoformat()
        libro["id"] = str(nuevo_id)
        libro["fecha_creacion"] = ahora
        libro["fecha_actualizacion"] = ahora

        cliente.set(clave, json.dumps(libro, ensure_ascii=False))
        print(f"\nLibro agregado correctamente con ID: {nuevo_id} (clave: {clave})")
    except ValueError as err:
        print(f"\nError de validación: {err}")
    except RedisError as err:
        print(f"\nError al guardar en KeyDB: {err}")


def listar_libros(cliente: redis.Redis) -> None:
    """Muestra todos los libros almacenados en KeyDB."""
    print("\n--- Listado de libros ---")
    try:
        libros = obtener_todos_los_libros(cliente)
    except RedisError as err:
        print(f"Error al consultar KeyDB: {err}")
        return

    if not libros:
        print("No hay libros registrados en la biblioteca.")
        return

    print(f"Total de libros: {len(libros)}\n")
    for indice, (clave, libro) in enumerate(libros, start=1):
        print(f"[{indice}] {formatear_libro(clave, libro)}\n")


def buscar_libros(cliente: redis.Redis) -> None:
    """Busca libros por título, autor o género recorriendo las claves con SCAN."""
    print("\n--- Buscar libros ---")
    print("1. Buscar por título")
    print("2. Buscar por autor")
    print("3. Buscar por género")
    opcion = input("Elige un criterio de búsqueda (1-3): ").strip()

    campos = {"1": "titulo", "2": "autor", "3": "genero"}
    if opcion not in campos:
        print("Opción de búsqueda inválida.")
        return

    campo = campos[opcion]
    try:
        termino = validar_texto_no_vacio(
            input(f"Ingresa el {campo} a buscar: "), campo
        ).lower()
    except ValueError as err:
        print(f"Error: {err}")
        return

    try:
        todos = obtener_todos_los_libros(cliente)
    except RedisError as err:
        print(f"Error al buscar en KeyDB: {err}")
        return

    resultados = [
        (clave, libro)
        for clave, libro in todos
        if termino in str(libro.get(campo, "")).lower()
    ]

    if not resultados:
        print(f"\nNo se encontraron libros que coincidan con '{termino}' en {campo}.")
        return

    print(f"\nSe encontraron {len(resultados)} resultado(s):\n")
    for indice, (clave, libro) in enumerate(resultados, start=1):
        print(f"[{indice}] {formatear_libro(clave, libro)}\n")


def actualizar_libro(cliente: redis.Redis) -> None:
    """Actualiza uno o más campos de un libro existente usando GET y SET."""
    print("\n--- Actualizar información de un libro ---")
    id_input = input("Ingresa el ID del libro a actualizar (ej. 1 o libro:1): ")

    try:
        clave = construir_clave(id_input)
        libro_actual = obtener_libro_por_clave(cliente, clave)
    except ValueError as err:
        print(f"Error: {err}")
        return
    except RedisError as err:
        print(f"Error al consultar KeyDB: {err}")
        return

    if libro_actual is None:
        print(f"Clave no encontrada: no existe ningún libro con '{clave}'.")
        return

    print("\nDatos actuales del libro:")
    print(formatear_libro(clave, libro_actual))
    print("\nPresiona Enter sin escribir nada para conservar el valor actual.")

    nuevo_titulo = input(f"Nuevo título [{libro_actual.get('titulo', '')}]: ").strip()
    nuevo_autor = input(f"Nuevo autor [{libro_actual.get('autor', '')}]: ").strip()
    nuevo_genero = input(f"Nuevo género [{libro_actual.get('genero', '')}]: ").strip()
    nuevo_estado = solicitar_estado_lectura(permitir_vacio=True)

    if not any([nuevo_titulo, nuevo_autor, nuevo_genero, nuevo_estado]):
        print("\nNo se realizaron cambios en el libro.")
        return

    actualizado = dict(libro_actual)
    if nuevo_titulo:
        actualizado["titulo"] = nuevo_titulo
    if nuevo_autor:
        actualizado["autor"] = nuevo_autor
    if nuevo_genero:
        actualizado["genero"] = nuevo_genero
    if nuevo_estado is not None:
        actualizado["estado_lectura"] = nuevo_estado

    try:
        validado = validar_libro(actualizado)
        actualizado.update(validado)
        actualizado["fecha_actualizacion"] = datetime.now(timezone.utc).isoformat()
        cliente.set(clave, json.dumps(actualizado, ensure_ascii=False))
        print("\nLibro actualizado correctamente.")
    except ValueError as err:
        print(f"\nError de validación: {err}")
    except RedisError as err:
        print(f"\nError al actualizar en KeyDB: {err}")


def eliminar_libro(cliente: redis.Redis) -> None:
    """Elimina un libro de KeyDB usando DEL previa confirmación."""
    print("\n--- Eliminar libro existente ---")
    id_input = input("Ingresa el ID del libro a eliminar (ej. 1 o libro:1): ")

    try:
        clave = construir_clave(id_input)
        libro = obtener_libro_por_clave(cliente, clave)
    except ValueError as err:
        print(f"Error: {err}")
        return
    except RedisError as err:
        print(f"Error al consultar KeyDB: {err}")
        return

    if libro is None:
        print(f"Clave no encontrada: no existe ningún libro con '{clave}'.")
        return

    print("\nLibro seleccionado:")
    print(formatear_libro(clave, libro))
    confirmacion = input("\n¿Confirmas que deseas eliminarlo? (s/n): ").strip().lower()
    if confirmacion != "s":
        print("Eliminación cancelada.")
        return

    try:
        eliminados = cliente.delete(clave)
        if eliminados > 0:
            print("Libro eliminado correctamente.")
        else:
            print("No se pudo eliminar el libro (clave no encontrada).")
    except RedisError as err:
        print(f"Error al eliminar en KeyDB: {err}")


def mostrar_menu() -> None:
    """Imprime las opciones principales de la aplicación."""
    print("\n=== Biblioteca Personal (KeyDB) ===")
    print("1. Agregar nuevo libro")
    print("2. Actualizar información de un libro")
    print("3. Eliminar libro existente")
    print("4. Ver listado de libros")
    print("5. Buscar libros")
    print("6. Salir")


def main() -> None:
    """Punto de entrada principal de la aplicación CLI."""
    try:
        cliente = conectar_keydb()
    except ConnectionError as err:
        print(f"Error de conexión: {err}")
        sys.exit(1)

    host = os.getenv("KEYDB_HOST", "localhost")
    puerto = os.getenv("KEYDB_PORT", "6379")
    print(f"Conectado a KeyDB en {host}:{puerto}")

    acciones = {
        "1": agregar_libro,
        "2": actualizar_libro,
        "3": eliminar_libro,
        "4": listar_libros,
        "5": buscar_libros,
    }

    try:
        while True:
            mostrar_menu()
            opcion = input("Selecciona una opción (1-6): ").strip()
            if opcion == "6":
                print("Saliendo de la biblioteca personal. ¡Hasta luego!")
                break
            accion = acciones.get(opcion)
            if accion:
                accion(cliente)
            else:
                print("Opción inválida. Por favor elige un número del 1 al 6.")
    except KeyboardInterrupt:
        print("\nPrograma interrumpido por el usuario. Cerrando conexión...")
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
