🛠️ Herramientas necesarias
Python 3 instalado.

DB Browser for SQLite (para exportar datos de la base vieja).

Tus archivos de la instalación antigua (jellyfin.db y library.db).

Una instalación nueva y limpia de Jellyfin 10.11.x.

📂 Paso 1: Extraer el historial (Watched Status)
Dado que la estructura de la base de datos ha cambiado, exportaremos el historial a un formato neutral (CSV).

Abre DB Browser for SQLite.

Abre tu archivo antiguo library.db (o jellyfin.db, dependiendo de dónde tenga tu versión anterior la tabla UserItemDatas o UserDatas).

Busca la tabla llamada UserItemDatas.

Ve a Archivo > Exportar > Tabla(s) como archivo CSV.

Selecciona la tabla y guárdalo como: userdatas.csv.
📜 Paso 2: Preparar los Scripts
Crea una carpeta y guarda los dos scripts de Python necesarios (código abajo).

restaurar_usuarios.py: Inyecta los datos en la nueva DB.

actualizar_politicas.py: Reactiva los permisos de los usuarios mediante la API.

(Nota: Asegúrate de tener los archivos .py que usaremos en los siguientes pasos).
🚀 Paso 3: Restaurar la Base de Datos
⚠️ Importante: Detén el servidor Jellyfin antes de ejecutar esto.

Abre una terminal en la carpeta de los scripts y ejecuta:
Windows:
python restaurar_usuarios.py --source "C:\Ruta\BackupViejo\jellyfin.db" --dest "C:\ProgramData\Jellyfin\Server\data\jellyfin.db" --migrate-userdatas --userdatas "C:\Ruta\userdatas.csv" --backup

Linux:
sudo python3 /ruta/restaurar_usuarios.py \
--source "/ruta/jellyfin.db" \
--dest "/var/lib/jellyfin/data/jellyfin.db" \
--migrate-userdatas \
--userdatas "/ruta/_UserDatas.csv" \
--backup

Lo que hace este paso:

Crea un backup de seguridad de tu nueva DB.

Copia los usuarios (tabla Users) de la DB vieja a la nueva.

Lee el CSV que extrajiste y rellena la tabla de historial (UserItemDatas).
🔐 Paso 4: Corregir Permisos (Vía API)
Al inyectar usuarios manualmente, a menudo quedan "bloqueados" o sin permisos en la nueva versión.

Inicia tu servidor Jellyfin.

Entra con tu usuario Administrador nuevo.

Ve a Panel de Control > Claves de API, crea una nueva y cópiala.

Edita el archivo actualizar_politicas.py y pega tu API KEY.

Ejecuta el script:
python actualizar_politicas.py
