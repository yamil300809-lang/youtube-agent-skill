#!/usr/bin/env python3
"""subir.py - sube videos a YouTube como PRIVADOS y los programa con publishAt.

Modos (nada sube sin la palabra de confirmación):

    python3 subir.py --modo validar                      # revisa videos.csv, NO sube nada
    python3 subir.py --modo prueba --archivo "<drive>" --confirmacion súbelo
                                                         # 1 video, privado, sin programar
    python3 subir.py --modo subir --confirmacion súbelo  # todo videos.csv, privado + publishAt

videos.csv (coma o punto y coma como separador):
    archivo,titulo,descripcion,tags,fecha_hora_publicacion

    archivo   enlace de Google Drive, "drive:<ID>", el nombre exacto del archivo en Drive,
              o una ruta local
    tags      separadas por | (también acepta comas si la celda va entre comillas)
    fecha     "2026-11-25 18:00" o "25/11/2026 18:00", hora de America/Mexico_City
    descripcion  escribe \\n para un salto de línea

Credenciales, SOLO por variables de entorno (en GitHub: Settings > Secrets > Actions):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Opcional: YT_DRIVE_FOLDER_ID  (carpeta de Drive donde buscar por nombre)

El script nunca imprime ni guarda las credenciales.
"""
import argparse, csv, io, os, random, re, sys, tempfile, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Mexico_City")
CATEGORIA_GAMING = "20"
CONFIRMACION = "súbelo"
COLUMNAS = ["archivo", "titulo", "descripcion", "tags", "fecha_hora_publicacion"]
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/drive.readonly"]
CHUNK = 8 * 1024 * 1024          # subida reanudable en trozos de 8 MB
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
COSTO_SUBIDA = 1600              # unidades de cuota por videos.insert (cuota diaria por defecto: 10 000)


# ---------------------------------------------------------------- lectura y validación del CSV
def leer_csv(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        raw = fh.read()
    try:
        dialecto = csv.Sniffer().sniff(raw.splitlines()[0], delimiters=",;")
    except (csv.Error, IndexError):
        dialecto = csv.excel
    filas = list(csv.DictReader(io.StringIO(raw), dialect=dialecto))
    if filas:
        faltan = [c for c in COLUMNAS if c not in {(k or "").strip().lower() for k in filas[0]}]
        if faltan:
            sys.exit(f"videos.csv: faltan columnas {faltan}. Deben ser: {','.join(COLUMNAS)}")
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in f.items()} for f in filas
            if any((v or "").strip() for v in f.values())]


def parsear_fecha(texto):
    texto = texto.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            local = datetime.strptime(texto, fmt).replace(tzinfo=TZ)
            return local, local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except ValueError:
            pass
    raise ValueError(f'fecha "{texto}" no reconocida - usa 2026-11-25 18:00')


def preparar(fila, n, programar=True):
    """Devuelve (datos, errores). Reglas de YouTube: título 1-100 caracteres, sin < ni >,
    descripción hasta 5000 bytes, tags hasta ~500 caracteres en total."""
    err = []
    titulo = fila.get("titulo", "")
    desc = fila.get("descripcion", "").replace("\\n", "\n")
    tags = [t.strip() for t in re.split(r"[|,]", fila.get("tags", "")) if t.strip()]
    if not fila.get("archivo"): err.append("falta 'archivo'")
    if not titulo: err.append("falta 'titulo'")
    if len(titulo) > 100: err.append(f"título de {len(titulo)} caracteres (máximo 100)")
    if re.search(r"[<>]", titulo + desc): err.append("YouTube no acepta < ni > en título o descripción")
    if len(desc.encode("utf-8")) > 5000: err.append("descripción de más de 5000 bytes")
    if sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1) > 500:
        err.append("tags suman más de 500 caracteres")
    publish_at = local = None
    if programar:
        try:
            local, publish_at = parsear_fecha(fila.get("fecha_hora_publicacion", ""))
            if local < datetime.now(TZ) + timedelta(minutes=15):
                err.append(f"la fecha {local:%Y-%m-%d %H:%M} ya pasó o es en menos de 15 minutos")
        except ValueError as e:
            err.append(str(e))
    body = {
        "snippet": {"title": titulo, "description": desc, "tags": tags,
                    "categoryId": CATEGORIA_GAMING, "defaultLanguage": "es",
                    "defaultAudioLanguage": "es"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at
    return {"n": n, "archivo": fila.get("archivo", ""), "body": body, "local": local}, err


# ---------------------------------------------------------------- Google: credenciales y servicios
def servicios():
    faltan = [v for v in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(v)]
    if faltan:
        sys.exit(f"Faltan los secretos {faltan}. Agrégalos en GitHub > Settings > Secrets and variables > Actions.")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    cred = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                       token_uri="https://oauth2.googleapis.com/token",
                       client_id=os.environ["YT_CLIENT_ID"],
                       client_secret=os.environ["YT_CLIENT_SECRET"], scopes=SCOPES)
    try:
        cred.refresh(Request())
    except Exception as e:  # el mensaje de Google no contiene el token
        sys.exit(f"No pude renovar el acceso: {e.__class__.__name__}: {e}\n"
                 "Si dice invalid_grant: el token venció o se revocó - repite la autorización (paso 6 de LEEME.md).")
    return (build("youtube", "v3", credentials=cred, cache_discovery=False),
            build("drive", "v3", credentials=cred, cache_discovery=False))


def id_drive(archivo):
    m = re.search(r"/d/([\w-]{20,})", archivo) or re.search(r"[?&]id=([\w-]{20,})", archivo) \
        or re.match(r"drive:([\w-]{20,})$", archivo)
    return m.group(1) if m else None


def resolver_drive(drive, archivo):
    """Devuelve (file_id, nombre, tamaño) o None si es una ruta local."""
    fid = id_drive(archivo)
    if fid:
        f = drive.files().get(fileId=fid, fields="id,name,size,mimeType",
                              supportsAllDrives=True).execute()
        return f["id"], f["name"], int(f.get("size", 0))
    if os.path.exists(archivo):
        return None
    q = "name = '{}' and trashed = false".format(archivo.replace("\\", "\\\\").replace("'", "\\'"))
    if os.environ.get("YT_DRIVE_FOLDER_ID"):
        q += f" and '{os.environ['YT_DRIVE_FOLDER_ID']}' in parents"
    r = drive.files().list(q=q, fields="files(id,name,size)", pageSize=5,
                           supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = r.get("files", [])
    if not files: raise FileNotFoundError(f'"{archivo}" no está en tu Drive')
    if len(files) > 1: raise FileNotFoundError(f'hay {len(files)} archivos llamados "{archivo}" - usa el enlace')
    return files[0]["id"], files[0]["name"], int(files[0].get("size", 0))


def descargar(drive, fid, nombre, carpeta):
    from googleapiclient.http import MediaIoBaseDownload
    ruta = os.path.join(carpeta, re.sub(r"[^\w.-]", "_", nombre))
    with open(ruta, "wb") as fh:
        dl = MediaIoBaseDownload(fh, drive.files().get_media(fileId=fid, supportsAllDrives=True),
                                 chunksize=32 * 1024 * 1024)
        hecho = False
        while not hecho:
            st, hecho = dl.next_chunk(num_retries=5)
            if st: print(f"      descargando de Drive... {int(st.progress() * 100)}%", flush=True)
    return ruta


def titulos_existentes(yt):
    """Títulos ya subidos al canal (para no subir dos veces lo mismo). ~1 unidad por 50 videos."""
    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    vistos, token = set(), None
    for _ in range(4):  # últimos ~200 videos
        r = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50,
                                    pageToken=token).execute()
        vistos |= {i["snippet"]["title"].strip().lower() for i in r.get("items", [])}
        token = r.get("nextPageToken")
        if not token: break
    return ch["snippet"]["title"], vistos


def subir_uno(yt, ruta, body):
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    media = MediaFileUpload(ruta, chunksize=CHUNK, resumable=True, mimetype="video/*")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, intento = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st: print(f"      subiendo a YouTube... {int(st.progress() * 100)}%", flush=True)
            intento = 0
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and intento < 8:
                intento += 1
            elif e.resp.status == 403 and b"quotaExceeded" in e.content:
                sys.exit("Se acabó la cuota diaria de la API (se reinicia a medianoche hora del Pacífico).")
            else:
                raise
        except (ConnectionError, TimeoutError, OSError):
            if intento >= 8: raise
            intento += 1
        if intento:
            espera = min(64, 2 ** intento) + random.random()
            print(f"      error temporal, reintento {intento}/8 en {espera:.0f}s (la subida continúa donde iba)")
            time.sleep(espera)
    return resp["id"]


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modo", choices=["validar", "prueba", "subir"], default="validar")
    ap.add_argument("--csv", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "videos.csv"))
    ap.add_argument("--archivo", help="solo modo prueba: enlace de Drive, nombre o ruta del video")
    ap.add_argument("--confirmacion", default="")
    a = ap.parse_args()

    if a.modo == "prueba":
        if not a.archivo: sys.exit("modo prueba necesita --archivo")
        hoy = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
        filas = [{"archivo": a.archivo, "titulo": f"PRUEBA API - borrar ({hoy})",
                  "descripcion": "Video de prueba del sistema de subida. Privado.", "tags": "prueba"}]
        programar = False
    else:
        filas = leer_csv(a.csv)
        programar = True
    if not filas: sys.exit("videos.csv no tiene filas")

    lista, malos = [], 0
    print(f"\n  {len(filas)} video(s) en {'modo PRUEBA (privado, sin programar)' if not programar else a.csv}\n")
    for i, f in enumerate(filas, 1):
        d, err = preparar(f, i, programar)
        cuando = (f"{DIAS[d['local'].weekday()]} {d['local']:%d/%m/%Y %H:%M} CDMX"
                  if d["local"] else "sin programar")
        print(f"  {i:2d}. {d['body']['snippet']['title'][:60]}\n      {cuando} | privado | Gaming (20) | "
              f"{len(d['body']['snippet']['tags'])} tags | {d['archivo'][:50]}")
        for e in err: print(f"      x {e}")
        malos += bool(err)
        lista.append(d)
    usadas = len(lista) * COSTO_SUBIDA
    print(f"\n  cuota estimada: {usadas} de 10 000 unidades diarias "
          f"(unos {10000 // COSTO_SUBIDA} videos por día como máximo)")
    if usadas > 10000: print("  ! son demasiados para un día: divide videos.csv en varios días")
    if malos: sys.exit(f"\n  {malos} fila(s) con errores - corrígelas antes de subir. No se subió nada.")
    print("  todo válido.")

    if a.modo == "validar":
        print("  modo validar: no se subió nada.\n"); return
    if a.confirmacion.strip().lower() not in (CONFIRMACION, "subelo"):
        sys.exit(f'\n  Para subir de verdad escribe la confirmación exacta: {CONFIRMACION}. No se subió nada.')
    if usadas > 10000: sys.exit("  demasiados videos para la cuota de un día. No se subió nada.")

    yt, drive = servicios()
    canal, ya = titulos_existentes(yt)
    print(f"\n  canal: {canal}\n")
    with tempfile.TemporaryDirectory() as tmp:
        for d in lista:
            t = d["body"]["snippet"]["title"]
            if t.strip().lower() in ya:
                print(f"  {d['n']:2d}. YA EXISTE en el canal, la salto: {t}"); continue
            print(f"  {d['n']:2d}. {t}")
            r = resolver_drive(drive, d["archivo"])
            ruta = descargar(drive, r[0], r[1], tmp) if r else d["archivo"]
            vid = subir_uno(yt, ruta, d["body"])
            if r: os.remove(ruta)
            print(f"      listo: https://youtu.be/{vid}  (privado"
                  f"{', se publica ' + d['local'].strftime('%d/%m %H:%M') + ' CDMX' if d['local'] else ''})")
            print(f"      Studio: https://studio.youtube.com/video/{vid}/edit")
    print()


if __name__ == "__main__":
    main()
