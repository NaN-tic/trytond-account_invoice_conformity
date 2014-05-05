#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

__all__ = ['ConformGroup', 'Invoice']
__metaclass__ = PoolMeta

CONFORMITY_STATE = [
    (None, ''),
    ('pending', 'Pending'),
    ('closed', 'Closed'),
    ]

CONFORMITY_RESULT = [
    (None, ''),
    ('conformed', 'Conformed'),
    ('disconformed', 'Disconformed'),
    ]


class ConformGroup(ModelSQL, ModelView):
    'Conform Group'
    __name__ = 'account.invoice.conform_group'

    name = fields.Char('Name')


class Invoice:
    __name__ = 'account.invoice'

    conform_by = fields.Many2One('account.invoice.conform_group',
        'Conform by',
        states={
            'required': Bool(Eval('conformity_result')),
            })
    conformity_state = fields.Selection(CONFORMITY_STATE, 'Conformity State',
        states={
            'required': ((Eval('state', '') == 'posted') &
                (Eval('type').in_(['in_invoice', 'in_credit_note']))),
            'invisible': ~Eval('type').in_(['in_invoice', 'in_credit_note']),
            },
        depends=['type', 'state'])
    conformity_result = fields.Selection(CONFORMITY_RESULT,
        'Conformity Result',
        states={
            'required': Eval('conformity_state') == 'closed',
            })
    pending_to_resolve_conformity = fields.Boolean(
        'Pending to resolve conformity',
        states={
            'invisible': ~((Eval('conformity_state', '') == 'closed') &
                (Eval('conformity_result', '') == 'disconformed'))
            },
        depends=['conformity_state', 'conformity_result'])
    disconformity_culprit = fields.Selection([
            (None, ''),
            ('supplier', 'Supplier'),
            ('company', 'Company'),
            ], 'Disconformity Culprit',
        states={
            'required': ((Eval('conformity_result') == 'disconformed') &
                (Eval('conformity_state', '') == 'closed'))
            })
    conformed_description = fields.Text('Conformed Description')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude += ['conform_by', 'conformity_state',
            'conformity_result', 'disconformity_culprit',
            'conformed_description', 'pending_to_resolve_conformity']

    @staticmethod
    def default_conformity_result():
        return None

    @staticmethod
    def default_conformity_state():
        return None

    def on_change_with_conformity_state(self):
        if self.conform_by:
            return 'pending'
        return self.conformity_state

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
        if self.to_conform():
            self.conformity_state = 'pending'
            self.conformity_result = None
        self.save()

    @classmethod
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)
        cls.write(invoices, {
                'conformity_state': 'pending',
                'conformity_result': None,
                })

    @classmethod
    def validate_invoice(cls, invoices):
        super(Invoice, cls).validate_invoice(invoices)
        for invoice in invoices:
            invoice.set_conformity()

    @classmethod
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        for invoice in invoices:
            invoice.set_conformity()

    def get_rec_name(self, name):
        res = super(Invoice, self).get_rec_name(name)
        if self.conformity_state == 'pending':
            res = '***' + res
        return res
