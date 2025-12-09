import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class RemoteZPLPrinterController(http.Controller):
    """Endpoint que recibe ZPL + token y lo manda a la impresora configurada."""

    @http.route(
        "/remote_zpl/print",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def remote_zpl_print(self, **kwargs):
        env = request.env.sudo()

        token = kwargs.get("token") or request.httprequest.args.get("token")
        if not token:
            _logger.warning("Llamada a /remote_zpl/print SIN token")
            return http.Response("Missing token", status=400, content_type="text/plain")

        printer = env["remote.zpl.printer"].get_by_token(token)
        if not printer:
            _logger.warning("Token inválido en /remote_zpl/print: %s", token)
            return http.Response("Invalid token", status=404, content_type="text/plain")

        zpl_text = ""

        if request.httprequest.method == "POST":
            raw = request.httprequest.get_data()
            if raw:
                try:
                    zpl_text = raw.decode("utf-8")
                except Exception:
                    zpl_text = raw.decode("latin-1")

            if kwargs.get("zpl"):
                zpl_text = kwargs.get("zpl") or zpl_text
        else:
            zpl_text = kwargs.get("zpl") or ""

        if not zpl_text:
            _logger.warning("Llamada a /remote_zpl/print sin ZPL (token=%s)", token)
            return http.Response("Missing ZPL data", status=400, content_type="text/plain")

        try:
            printer.send_zpl(zpl_text)
        except Exception as e:
            _logger.exception("Error imprimiendo ZPL para token %s: %s", token, e)
            return http.Response("Error sending to printer", status=500, content_type="text/plain")

        return http.Response("OK", status=200, content_type="text/plain")
