import logging
import socket

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RemoteZPLPrinter(models.Model):
    _name = "remote.zpl.printer"
    _description = "Impresora ZPL remota"

    name = fields.Char(string="Nombre", required=True)
    printer_host = fields.Char(
        string="IP / Host de la impresora",
        required=True,
        help="IP pública o nombre de host de la impresora (por ej. 1.2.3.4)",
    )
    printer_port = fields.Integer(
        string="Puerto",
        default=9100,
        help="Puerto TCP de la impresora (típicamente 9100).",
    )
    token = fields.Char(
        string="Token de seguridad",
        required=True,
        help="Token que se usará en el webhook ?token=...",
    )
    timeout = fields.Integer(
        string="Timeout (segundos)",
        default=10,
        help="Tiempo máximo de espera al conectarse a la impresora.",
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Notas")

    _sql_constraints = [
        (
            "token_unique",
            "unique(token)",
            "El token debe ser único por impresora remota.",
        )
    ]

    @api.model
    def get_by_token(self, token):
        printer = self.sudo().search(
            [("token", "=", token), ("active", "=", True)], limit=1
        )
        return printer

    def send_zpl(self, zpl_text):
        """Envía el ZPL a la impresora remota vía socket."""
        self.ensure_one()
        host = self.printer_host
        port = self.printer_port or 9100
        timeout = self.timeout or 10

        if not zpl_text:
            raise UserError(_("No hay datos ZPL para enviar a la impresora."))

        _logger.info(
            "Enviando ZPL a impresora remota '%s' (%s:%s), longitud=%s bytes",
            self.name,
            host,
            port,
            len(zpl_text.encode("utf-8")),
        )

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(zpl_text.encode("utf-8"))
            sock.close()
        except Exception as e:
            _logger.exception(
                "Error enviando ZPL a la impresora '%s' (%s:%s): %s",
                self.name,
                host,
                port,
                e,
            )
            raise UserError(
                _(
                    "Error enviando a la impresora remota '%(name)s': %(error)s"
                )
                % {"name": self.name, "error": e}
            )
