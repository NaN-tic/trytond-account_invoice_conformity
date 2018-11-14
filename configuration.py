#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.modules.account_invoice_conformity.invoice import CONFORMITY_STATE
from trytond.modules.company.model import CompanyValueMixin


__all__ = ['Configuration', 'ConfigurationConformity']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    default_conformity_state = fields.MultiValue(fields.Selection(
        CONFORMITY_STATE, 'Default Conformity State'))
    ensure_conformity = fields.MultiValue(fields.Boolean('Ensure Conformity',
        help=('If marked posted supplier invoices must be conforming before '
            'posting them.')))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'default_conformity_state', 'ensure_conformity'}:
            return pool.get('account.configuration.default_account')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationConformity(ModelSQL, CompanyValueMixin):
    "Account Configuration Default Account"
    __name__ = 'account.configuration.default_account'
    default_conformity_state = fields.Selection(CONFORMITY_STATE,
        'Default Conformity Sate')
    ensure_conformity = fields.Boolean('Ensure Conformity')
