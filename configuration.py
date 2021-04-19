#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.modules.account_invoice_conformity.invoice import CONFORMITY_STATE
from trytond.modules.company.model import CompanyValueMixin
from trytond.pyson import Eval


__all__ = ['Configuration', 'ConfigurationConformity',
    'ConfigurationDefaultEmployee']


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    conformity_required = fields.MultiValue(fields.Boolean(
            'Conformity Required', help=('If we mark it as true, it will '
                'be necessary to create, at least, a conformity register')))
    ensure_conformity = fields.MultiValue(fields.Boolean('Ensure Conformity',
            help=('If marked posted supplier invoices must be conforming '
                'before posting them.')))
    default_employee = fields.MultiValue(fields.Many2One(
            'company.employee', 'Default Employee', domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
        ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'conformity_required', 'ensure_conformity'}:
            return pool.get('account.configuration.default_account')
        elif field == 'default_employee':
            return pool.get('account.configuration.default_employee')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationConformity(ModelSQL, CompanyValueMixin):
    "Account Configuration Default Account"
    __name__ = 'account.configuration.default_account'
    conformity_required = fields.Boolean('Conformity Required')
    ensure_conformity = fields.Boolean('Ensure Conformity')


class ConfigurationDefaultEmployee(ModelSQL, CompanyValueMixin):
    'Account Configuration Default Employee'
    __name__ = 'account.configuration.default_employee'
    default_employee = fields.Many2One('company.employee', 'Default Employee')
