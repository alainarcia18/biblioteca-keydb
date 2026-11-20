# Biblioteca Personal CLI con KeyDB y redis-py

Aplicación de línea de comandos (CLI) en Python para gestionar una biblioteca personal usando **KeyDB** (sistema de almacenamiento en memoria compatible con Redis) y la biblioteca oficial `redis-py`.

Cada libro se serializa en formato **JSON** (`json.dumps()`) y se almacena bajo una clave única con el formato `libro:<id>` usando comandos nativos de clave-valor (`INCR`, `SET`, `GET`, `DEL`, `SCAN`).

## Funcionalidades

1. **Agregar nuevo libro**: Registra un libro con título, autor, género y estado de lectura (`Pendiente`, `Leyendo` o `Leído`) usando `INCR` y `SET`.
2. **Actualizar información de un libro**: Recupera el JSON con `GET`, permite modificar cualquier campo y sobrescribe el valor con `SET`.
3. **Eliminar libro existente**: Elimina una clave con `DEL` previa confirmación.
4. **Ver listado de libros**: Recorre las claves `libro:*` con `SCAN` y muestra todos los registros ordenados por título.
5. **Buscar libros**: Filtra por título, autor o género (búsqueda parcial insensible a mayúsculas y minúsculas).
6. **Salir**: Cierra la conexión con KeyDB y termina el programa de forma segura.

## Configuración de KeyDB

### Opción A: Sin instalar nada en Windows (Nube gratuita compatible con Redis/KeyDB)

Puedes usar un servidor compatible con el protocolo Redis en la nube, como [Upstash Redis](https://upstash.com/redis) (plan gratuito sin tarjeta):
1. Crea una cuenta gratuita en [Upstash](https://upstash.com/redis) y crea una base de datos.
2. Copia **Endpoint** (`KEYDB_HOST`), **Port** (`KEYDB_PORT`) y **Password** (`KEYDB_PASSWORD`).
3. Coloca esos datos en tu archivo `.env` con `KEYDB_SSL=true`.

### Opción B: KeyDB local con Docker

Consulta la [documentación oficial de KeyDB](https://docs.keydb.dev/) o el [repositorio oficial de KeyDB](https://github.com/Snapchat/KeyDB) y levanta un contenedor en el puerto `6379`:

```bash
docker run -d --name keydb -p 6379:6379 eqalpha/keydb
```

### Opción C: KeyDB en Linux / WSL (Ubuntu)

Sigue la [guía de instalación de KeyDB](https://docs.keydb.dev/) en Ubuntu/WSL y verifica que el servicio escuche en `localhost:6379`.

## Instalación y configuración en Visual Studio Code

1. Abre la carpeta del proyecto en VS Code y abre la terminal integrada.
2. Crea y activa el entorno virtual:
   ```powershell
   py -m venv .venv
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   .\.venv\Scripts\Activate.ps1
   ```
3. Instala las dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
4. Crea tu archivo `.env` a partir de `.env.example` y completa tus datos de conexión:
   ```env
   KEYDB_HOST=localhost
   KEYDB_PORT=6379
   KEYDB_PASSWORD=
   KEYDB_DB=0
   KEYDB_SSL=false
   ```

## Ejecución de la aplicación

```powershell
python biblioteca.py
```

## Estructura de claves y valor JSON

- **Clave contador**: `contador:libros` (genera IDs incrementales `1`, `2`, `3`, ...).
- **Clave por libro**: `libro:<id>` (ejemplo: `libro:1`).
- **Valor almacenado (JSON)**:

```json
{
  "id": "1",
  "titulo": "Cien años de soledad",
  "autor": "Gabriel García Márquez",
  "genero": "Realismo mágico",
  "estado_lectura": "Leído",
  "fecha_creacion": "2026-11-20T06:45:00+00:00",
  "fecha_actualizacion": "2026-11-20T06:45:00+00:00"
}
```

## Manejo de errores y validaciones

- **Conexión fallida / autenticación**: Captura `ConnectionError`, `TimeoutError`, `AuthenticationError` y `RedisError` ejecutando `ping()` al iniciar.
- **Variables `.env` inválidas**: Valida que `KEYDB_PORT` y `KEYDB_DB` sean enteros válidos.
- **Clave no encontrada**: Informa claramente si el `libro:<id>` solicitado para actualizar o eliminar no existe.
- **Datos y JSON inválidos**: Valida campos obligatorios, estados de lectura permitidos (`Pendiente`, `Leyendo`, `Leído`) y errores de deserialización (`json.JSONDecodeError`).
- **Búsquedas sin resultados**: Muestra un mensaje claro sin interrumpir el menú.
