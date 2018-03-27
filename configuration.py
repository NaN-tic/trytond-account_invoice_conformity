#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.modules.account_invoice_conformity.invoice import CONFORMITY_STATE

__all__ = ['Configuration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    default_conformity_state = fields.MultiValue(fields.Selection(
        CONFORMITY_STATE, 'Default Conformity State'))
    ensure_conformity = fields.Boolean('Ensure Conformity',
        help=('If marked posted supplier invoices must be conforming before '
            'posting them.'))
