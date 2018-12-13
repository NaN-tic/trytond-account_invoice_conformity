#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Not, Equal
from trytond import backend
from trytond.transaction import Transaction
from sql.conditionals import Case
from trytond.wizard import Wizard, StateView, StateTransition, Button

__all__ = ['ConformGroupUser', 'ConformGroup', 'Invoice', 'InvoiceConform',
    'InvoiceNonconform', 'InvoiceNonconformStart']

CONFORMITY_STATE = [
    (None, ''),
    ('pending', 'Pending'),
    ('conforming', 'Conforming'),
    ('nonconforming_pending', 'Nonconforming Pending'),
    ('nonconforming', 'Nonconforming'),
    ]

class ConformGroupUser(ModelSQL):
    'Conform Group - Users'
    __name__ = 'account.invoice.conform_group-res.user'
    group = fields.Many2One('account.invoice.conform_group', 'Group',
        required=True, select=True)
    user = fields.Many2One('res.user', 'User', required=True, select=True)


class ConformGroup(ModelSQL, ModelView):
    'Conform Group'
    __name__ = 'account.invoice.conform_group'
    name = fields.Char('Name', required=True)
    users = fields.Many2Many('account.invoice.conform_group-res.user',
        'group', 'user', 'Users')


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    conform_by = fields.Many2One('account.invoice.conform_group',
        'Conform by',
        states={
            'required': Bool(Eval('conformity_state')) &
                Bool(Eval('type') ==  'in') &
                ~Eval('state').in_(['cancel', 'draft']),
            },
        depends=['conformity_state', 'type', 'state'])
    conformity_state = fields.Selection(CONFORMITY_STATE, 'Conformity State',
        states={
            'invisible': Not(Equal(Eval('type'), 'in')),
            },
        depends=['type'], sort=False)
    nonconformity_culprit = fields.Selection([
            (None, ''),
            ('supplier', 'Supplier'),
            ('company', 'Company'),
            ], 'Nonconformity Culprit',
        states={
            'required': ((Eval('conformity_state') == 'nonconforming') &
                (Eval('conformity_state', '') == 'closed'))
            })
    conforming_description = fields.Text('Conforming Description')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'post_conforming': ('Invoice "%s" can not be posted because it '
                    'is pending to conformed.'),
                })
        cls._check_modify_exclude += ['conform_by', 'conformity_state',
            'nonconformity_culprit', 'conforming_description']

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        table = TableHandler(cls, module_name)

        # Migration from 4.0: rename conformity_result into conformity_state
        if table.column_exist('conformity_result'):
            cursor.execute(*sql_table.update(
                    columns=[sql_table.conformity_state],
                    values = [
                        Case(((sql_table.conformity_state == 'closed')
                              & (sql_table.conformity_result == 'conforming'),
                                'conforming'),
                            ((sql_table.conformity_state == 'closed')
                             & (sql_table.conformity_result == 'nonconforming'),
                                'nonconforming'),
                            ((sql_table.conformity_state == 'pending')
                             & (sql_table.conformity_result == 'nonconforming'),
                                'nonconforming_pending'),
                            else_='pending')
                    ]
                )
            )
            table.drop_column('conformity_result')
        # Migration from 4.0: rename conformed_description into conforming_description
        if (table.column_exist('conformed_description')
                and not table.column_exist('conforming_description')):
            table.column_rename('conformed_description', 'conforming_description')
        # Migration from 4.0: rename disconformity_culprit into nonconformity_culprit
        if (table.column_exist('disconformity_culprit')
                and not table.column_exist('nonconformity_culprit')):
            table.column_rename('disconformity_culprit', 'nonconformity_culprit')

        super(Invoice, cls).__register__(module_name)

    @staticmethod
    def default_conformity_state():
        Config = Pool().get('account.configuration')
        config = Config(1)
        return config.default_conformity_state

    def to_conforming(self):
        Config = Pool().get('account.configuration')
        config = Config(1)

        if (not config.ensure_conformity or self.type != 'in'
                or self.conformity_state is not None):
            return False
        return True

    def to_pending(self):
        Config = Pool().get('account.configuration')
        config = Config(1)

        if (not config.ensure_conformity or self.type != 'in'
                or self.conformity_state is None):
            return False
        return True

    def check_conformity(self):
        Config = Pool().get('account.configuration')

        config = Config(1)
        if not config.ensure_conformity or self.type != 'in':
            return

        if self.conformity_state != 'conforming':
            self.raise_user_error('post_conforming', self.rec_name)

    def get_rec_name(self, name):
        res = super(Invoice, self).get_rec_name(name)
        if self.type == 'in':
            if self.conformity_state == 'pending':
                return ' P*** ' + res
            elif self.conformity_state == 'nonconforming_pending':
                return ' NCP*** ' + res
            elif self.conformity_state == 'nonconforming':
                return ' NC*** ' + res
        return res

    @classmethod
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)

        to_pending = []
        for invoice in invoices:
            if invoice.to_pending():
                to_pending.append(invoice)

        if to_pending:
            cls.write(to_pending, {
                    'conformity_state': 'pending',
                    })

    @classmethod
    def post(cls, invoices):
        for invoice in invoices:
            invoice.check_conformity()
        super(Invoice, cls).post(invoices)

    @classmethod
    def view_attributes(cls):
        return super(Invoice, cls).view_attributes() + [
            ('//page[@id="conform"]', 'states', {
                    'invisible': (Eval('type') != 'in'),
                    })]

    @classmethod
    def copy(cls, invoices, default=None):
        invoices_w_cs = []
        invoices_wo_cs = []

        for invoice in invoices:
            if invoice.conformity_state:
                invoices_w_cs.append(invoice)
            else:
                invoices_wo_cs.append(invoice)
        new_records = []
        if default:
            new_default = default.copy()
        else:
            new_default = {}
        if invoices_wo_cs:
            new_records += super(Invoice, cls).copy(invoices_wo_cs,
                default=new_default)
        if invoices_w_cs:
            new_default['conformity_state'] = cls.default_conformity_state()
            new_records += super(Invoice, cls).copy(invoices_w_cs,
                default=new_default)

        return new_records


class InvoiceNonconformStart(ModelView):
    "Nonconform Invoices"
    __name__ = 'account.invoice.nonconformity.start'
    conformity_state = fields.Selection([
           ('nonconforming_pending', 'Nonconforming Pending'),
           ('nonconforming', 'Nonconforming'),
           ], 'Conformity State')
    nonconformity_culprit = fields.Selection([
            (None, ''),
            ('supplier', 'Supplier'),
            ('company', 'Company'),
            ], 'Nonconformity Culprit', required=True)
    conforming_description = fields.Text('Conforming Description')

    @staticmethod
    def default_conformity_state():
       return 'nonconforming_pending'

    @staticmethod
    def default_conforming_description():
        pool = Pool()
        Invoice = pool.get('account.invoice')
        active_id = Transaction().context.get('active_id')
        if active_id:
            invoice = Invoice(active_id)
            return invoice.conforming_description


class InvoiceNonconform(Wizard):
    "Nonconform Invoices"
    __name__ = 'account.invoice.nonconformity'
    start = StateView('account.invoice.nonconformity.start',
        'account_invoice_conformity.account_invoice_nonconformity_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Nonconforming', 'nonconforming', 'tryton-ok', default=True)
            ])
    nonconforming = StateTransition()

    def transition_nonconforming(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        invoices = Invoice.browse(Transaction().context['active_ids'])
        with Transaction().set_context(_check_access=False):
            Invoice.write(invoices, {
                'conformity_state': self.start.conformity_state,
                'nonconformity_culprit': self.start.nonconformity_culprit,
                'conforming_description': self.start.conforming_description,
               })
        return 'end'


class InvoiceConform(Wizard):
    "Conform Invoices"
    __name__ = 'account.invoice.conformity'
    start = StateTransition()

    def transition_start(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        invoices = Invoice.browse(Transaction().context['active_ids'])
        with Transaction().set_context(_check_access=False):
            Invoice.write(invoices, {
                'conformity_state': 'conforming',
            })
        return 'end'
