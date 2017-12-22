#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.account_invoice_conformity.invoice import CONFORMITY_STATE

__all__ = ['Company']

class Company:
    __metaclass__ = PoolMeta
    __name__ = 'company.company'
    default_conformity_state = fields.Selection(
        CONFORMITY_STATE, 'Default Conformity State')
