# Subir y programar videos a YouTube (desde el celular)

Sube tus Shorts **como privados** y los deja **programados** (`publishAt`, hora de Ciudad de México),
con categoría **Gaming (20)**, tomando los videos directo de tu **Google Drive**.

Todo corre en **GitHub Actions**: lo lanzas con un botón desde el navegador del celular. Tus claves
viven como **secretos de GitHub** (cifrados), nunca en el repo ni en un commit.

> **Regla de oro:** nada sube sin escribir `súbelo` en el campo *confirmacion*.

## Cómo se usa (cuando ya está configurado)

1. Sube tus videos a Drive.
2. Edita `videos.csv` en GitHub (lápiz ✏️). Una fila por video:

   | columna | ejemplo |
   |---|---|
   | archivo | enlace de Drive (Compartir → Copiar enlace) o el nombre exacto, `short1.mp4` |
   | titulo | `¿Lucia traiciona a Jason? #GTA6 #Shorts` (máx. 100 caracteres, sin `<` `>`) |
   | descripcion | escribe `\n` para un salto de línea |
   | tags | separadas por `\|` → `GTA 6\|Vice City\|Lucia` |
   | fecha_hora_publicacion | `2026-11-25 18:00` (hora CDMX) |

   Si un texto lleva comas, ponlo entre comillas: `"Hola, esto es GTA 6"`.
3. GitHub → **Actions** → **Subir videos a YouTube** → **Run workflow**:
   - `validar`: solo revisa el CSV. No sube nada. Úsalo siempre primero.
   - `prueba`: sube 1 video privado y sin programar (pon su enlace de Drive).
   - `subir`: sube todo `videos.csv`, privado y programado.
   - En `confirmacion` escribe `súbelo` (solo para prueba/subir).

Si un título ya existe en tu canal, el script lo salta, así que puedes repetir sin duplicar.

## Límites que debes conocer

- **Cuota:** la API da 10 000 unidades al día y cada subida cuesta unas 1 600, o sea **unos 6
  videos al día**. Revisa la cifra real en Google Cloud → APIs → YouTube Data API v3 → Cuotas.
- **Proyectos sin auditar:** YouTube deja en **privado bloqueado** los videos subidos por API desde
  proyectos nuevos que no han pasado su auditoría. Para que `publishAt` los haga públicos hay que
  pedir la auditoría (gratis) en el formulario de YouTube API Services: https://support.google.com/youtube/contact/yt_api_form
- **Verificar el canal** (youtube.com/verify, con SMS) hace falta para videos de más de 15 min y
  miniaturas personalizadas. Para Shorts no es obligatorio, pero conviene.
- **Shorts:** vertical y de hasta 3 minutos. No hay un campo "Short" en la API: YouTube lo
  detecta solo.

## Configuración (una sola vez)

1. **Proyecto:** console.cloud.google.com → selector de proyecto → *Proyecto nuevo* → nombre
   `subidor-youtube` → *Crear*.
2. **APIs:** busca y *Habilitar* **YouTube Data API v3** y **Google Drive API**.
3. **Pantalla de consentimiento** (*Google Auth Platform*): tipo *Externo*, nombre de la app,
   tu correo. En *Público*, agrégate como usuario de prueba. Después pulsa **Publicar app** (pasar a
   *En producción*). Si se queda en *Prueba*, el token **vence cada 7 días**.
4. **Credencial:** *Clientes* → *Crear cliente* → tipo **Aplicación web** → en *URIs de redirección
   autorizados* agrega exactamente `https://developers.google.com/oauthplayground` → *Crear*.
   Copia el *ID de cliente* y el *Secreto del cliente*.
5. **Secretos en GitHub:** tu repo → *Settings* → *Secrets and variables* → *Actions* → *New
   repository secret*: `YT_CLIENT_ID` y `YT_CLIENT_SECRET`.
6. **Autorizar tu canal** en developers.google.com/oauthplayground:
   - ⚙️ (arriba a la derecha) → marca *Use your own OAuth credentials* → pega ID y secreto.
   - En la caja de la izquierda escribe estos tres permisos, separados por espacio:
     `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/drive.readonly`
   - *Authorize APIs* → elige tu cuenta → **elige el canal** de GTA 6 → si sale "Google no
     verificó esta app", pulsa *Configuración avanzada* → *Ir a…* (es tu propia app) → *Permitir*.
   - *Exchange authorization code for tokens* → copia el **Refresh token** → secreto
     `YT_REFRESH_TOKEN` en GitHub. No lo pegues en ningún chat.
7. (Opcional) `YT_DRIVE_FOLDER_ID`: el ID de tu carpeta de Drive, que va después de `/folders/` en
   el enlace, para buscar videos por nombre solo ahí.

Para quitar el acceso cuando quieras: myaccount.google.com/permissions → tu app → *Quitar acceso*.
