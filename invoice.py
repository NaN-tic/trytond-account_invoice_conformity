#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

__all__ = ['Invoice']
__metaclass__ = PoolMeta

CONFORMITY_STATE = [
    ('pending', 'Pending'),
    ('closed', 'Closed'),]

CONFORMITY_RESULT = [
    ('to_conform', 'To Conform'),
    ('conformed', 'Conformed'),
    ('disconformed', 'Disconformed'),
]


class Invoice:
    __name__ = 'account.invoice'

    to_conform_by = fields.Many2One('res.user', 'Conform By',
        states={
            'required': Bool(Eval('conformity_result')),
        })
    conformity_state = fields.Selection([(None, None)] + CONFORMITY_STATE,
        'Conformity State', states={
            'required': Bool(Eval('conformity_result')),
        })
    conformity_result = fields.Selection([(None, None)] + CONFORMITY_RESULT,
        'Conformity Result', states={
            'required': Bool(Eval('conformity_result')),
            }
        )

    disconformity_culprit = fields.Selection([
            (None, None),
            ('supplier', 'Supplier'),
            ('company', 'Company'),
            ], 'Disconformity Culprit',
        states={
            'required': (Bool(Eval('conformity_result')) &
                (Eval('conformity_state', '') == 'pending'))
            })

    conformed_description = fields.Text('Conformed Description')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude += ['to_conform_by', 'conformity_state',
            'conformity_result', 'disconformity_culprit',
            'conformed_description']

    @staticmethod
    def default_conformity_result():
        return None

    @staticmethod
    def default_conformity_state():
        return None

    def to_conform(self):
        if self.type not in ('in_invoice', 'in_credit_note'):
            return False
        InvoiceLine = Pool().get('account.invoice.line')
        lines = InvoiceLine.search([('origin', '=', None),
            ('invoice', '=', self.id)])
        if not lines:
            return False
        return True

    def set_conformity(self):
        if self.conformity_state != None and self.conformity_result != None:
            return
        self.conformity_state = None
        self.conformity_result = None
        if self.to_conform():
            self.conformity_state = 'pending'
            self.conformity_result = 'to_conform'
        self.save()

    @classmethod
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)
        cls.write(invoices, {
                'conformity_state': None,
                'conformity_result': None,
                })

    @classmethod
    def validate_invoice(cls, invoices):
        super(Invoice, cls).validate_invoice(invoices)
        for invoice in invoices:
            invoice.set_conformity()

    @classmethod
    def post(cls, invoices):
        super(Invoice, cls).validate_invoice(invoices)
        for invoice in invoices:
            invoice.set_conformity()

    def get_rec_name(self, name):
        res = super(Invoice, self).get_rec_name(name)
        if self.conformity_state in ('disconformed', 'to_conform') and \
           self.conformity_result == 'pending':
            res = '*' + res
        return res
