import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class RemoteZPLPrinterController(http.Controller):
    """
    Endpoint que recibe ZPL + token y lo manda a la impresora configurada.
    No piensa, no procesa: solo imprime.
    """

    @http.route(
        "/remote_zpl/print",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def remote_zpl_print(self, **kwargs):
        # Ojo: acá NO se hace request.env.sudo()
        env = request.env

        # 1) Token
        token = kwargs.get("token") or request.httprequest.args.get("token")
        if not token:
            _logger.warning("Llamada a /remote_zpl/print SIN token")
            return http.Response("Missing token", status=400, content_type="text/plain")

        # 2) Buscar impresora por token (con sudo sobre el modelo)
        printer_model = env["remote.zpl.printer"].sudo()
        printer = printer_model.search(
            [("token", "=", token), ("active", "=", True)], limit=1
        )
        if not printer:
            _logger.warning("Token inválido en /remote_zpl/print: %s", token)
            return http.Response("Invalid token", status=404, content_type="text/plain")

        # 3) Obtener ZPL
        zpl_text = ""

        if request.httprequest.method == "POST":
            # Intentamos leer body crudo
            raw = request.httprequest.get_data()
            if raw:
                try:
                    zpl_text = raw.decode("utf-8")
                except Exception:
                    zpl_text = raw.decode("latin-1")

            # Si además viene por parámetro 'zpl', pisamos con eso
            if kwargs.get("zpl"):
                zpl_text = kwargs.get("zpl") or zpl_text
        else:
            # GET: viene por querystring
            zpl_text = kwargs.get("zpl") or ""

        if not zpl_text:
            _logger.warning("Llamada a /remote_zpl/print sin ZPL (token=%s)", token)
            return http.Response("Missing ZPL data", status=400, content_type="text/plain")

        # 4) Enviar a impresora
        try:
            printer.send_zpl(zpl_text)
        except Exception as e:
            _logger.exception("Error imprimiendo ZPL para token %s: %s", token, e)
            return http.Response("Error sending to printer", status=500, content_type="text/plain")

        # 5) OK
        return http.Response("OK", status=200, content_type="text/plain")
