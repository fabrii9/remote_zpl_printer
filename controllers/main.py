import logging
from urllib.parse import unquote

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class RemoteZPLPrinterController(http.Controller):
    """
    Endpoint que recibe ZPL + token y lo manda a la impresora configurada.
    Soporta '&amp;' en la URL y parseo manual de parámetros.
    """

    @http.route(
        "/remote_zpl/print",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def remote_zpl_print(self, **kwargs):
        env = request.env

        # ==============================================
        # 0) LEER QUERY STRING CRUDA
        # ==============================================
        raw_qs = request.httprequest.query_string.decode("utf-8", "ignore")
        _logger.info("REMOTE_ZPL_PRINT QS RAW: %s", raw_qs)

        # Normalizar por si viene escapada (&amp;)
        clean_qs = raw_qs.replace("&amp;", "&")

        # Parsear parameters manualmente
        params = {}
        if clean_qs:
            for pair in clean_qs.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        # ==============================================
        # 1) TOKEN
        # ==============================================
        token = params.get("token")
        if token:
            token = unquote(token)

        # fallback por si viene en kwargs
        if not token:
            token = kwargs.get("token") or request.httprequest.args.get("token")

        if not token:
            _logger.warning("Llamada a /remote_zpl/print SIN token (QS=%s)", raw_qs)
            return http.Response("Missing token", status=400, content_type="text/plain")

        # Buscar impresora remota
        printer = env["remote.zpl.printer"].sudo().search(
            [("token", "=", token), ("active", "=", True)], limit=1
        )
        if not printer:
            _logger.warning("Token inválido en /remote_zpl/print: %s", token)
            return http.Response("Invalid token", status=404, content_type="text/plain")

        # ==============================================
        # 2) OBTENER ZPL
        # ==============================================
        zpl_text = None

        # Si viene por POST, primero el body
        if request.httprequest.method == "POST":
            raw_body = request.httprequest.get_data()
            if raw_body:
                try:
                    zpl_text = raw_body.decode("utf-8")
                except Exception:
                    zpl_text = raw_body.decode("latin-1")

        # Si viene por GET o como parámetro en QS
        if not zpl_text:
            zpl_param = params.get("zpl")
            if zpl_param:
                zpl_text = unquote(zpl_param)

        # fallback
        if not zpl_text and kwargs.get("zpl"):
            zpl_text = kwargs.get("zpl")

        # Validar
        if not zpl_text:
            _logger.warning(
                "Llamada a /remote_zpl/print sin ZPL (token=%s, QS=%s)",
                token,
                raw_qs,
            )
            return http.Response("Missing ZPL data", status=400, content_type="text/plain")

        _logger.info(
            "REMOTE_ZPL_PRINT: token=%s, len(ZPL)=%s",
            token,
            len(zpl_text.encode("utf-8")),
        )

        # ==============================================
        # 3) ENVIAR A IMPRESORA
        # ==============================================
        try:
            printer.send_zpl(zpl_text)
        except Exception as e:
            _logger.exception(
                "Error imprimiendo ZPL para token %s: %s", token, e
            )
            return http.Response(
                "Error sending to printer",
                status=500,
                content_type="text/plain",
            )

        # ==============================================
        # 4) RESPUESTA (popup que se cierra)
        # ==============================================
        html = """
        <html>
          <head>
            <title>Impresión enviada</title>
            <script type="text/javascript">
              setTimeout(function() { window.close(); }, 1000);
            </script>
          </head>
          <body>
            <p>Etiqueta enviada a la impresora. Esta ventana se cerrará automáticamente.</p>
          </body>
        </html>
        """
        return http.Response(html, status=200, content_type="text/html; charset=utf-8")
