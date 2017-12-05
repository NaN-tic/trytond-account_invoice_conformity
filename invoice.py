#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Not, Equal
from trytond import backend
from trytond.transaction import Transaction
from sql import Table
from sql.conditionals import Case

__all__ = ['Configuration', 'ConformGroupUser', 'ConformGroup', 'Invoice']
__metaclass__ = PoolMeta

CONFORMITY_STATE = [
    (None, ''),
    ('pending', 'Pending'),
    ('conforming', 'Conforming'),
    ('nonconforming', 'Nonconforming'),
    ('nonconforming_pending', 'Nonconforming Pending'),
    ]


class Configuration:
    __name__ = 'account.configuration'
    ensure_conformity = fields.Boolean('Ensure Conformity', help='If marked '
        'posted supplier invoices must be conforming before posting them.')


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


class Invoice:
    __name__ = 'account.invoice'

    conform_by = fields.Many2One('account.invoice.conform_group',
        'Conform by',
        states={
            'required': Bool(Eval('conformity_state')),
            })
    conformity_state = fields.Selection(CONFORMITY_STATE, 'Conformity State',
        states={
            'invisible': Not(Equal(Eval('type'), 'in')),
            },
        depends=['type'])
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
                    'is not conforming.'),
                })
        cls._check_modify_exclude += ['conform_by', 'conformity_state',
            'nonconformity_culprit',
            'conforming_description']
        cls._buttons.update({
            'conform' : {
                'invisible' : Eval('conformity_state') != 'pending',
                }
            })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        table = TableHandler(cls, module_name)
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
        super(Invoice, cls).__register__(module_name)

    @staticmethod
    def default_conformity_state():
        return None

    def to_conform(self):
        if self.type != 'in':
            return False
        InvoiceLine = Pool().get('account.invoice.line')
        lines = InvoiceLine.search([('origin', '=', None),
            ('invoice', '=', self.id)])
        if not lines:
            return False
        return True

    def set_conformity(self):
        if self.conformity_state != None:
            return
        if self.to_conform():
            self.conformity_state = 'open'
        self.save()

    @classmethod
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)
        cls.write(invoices, {
                'conformity_state': 'open',
                })

    @classmethod
    def validate_invoice(cls, invoices):
        super(Invoice, cls).validate_invoice(invoices)
        for invoice in invoices:
            invoice.set_conformity()

    @classmethod
    def post(cls, invoices):
        for invoice in invoices:
            invoice.check_conformity()
        super(Invoice, cls).post(invoices)

    def check_conformity(self):
        pool = Pool()
        config = pool.get('account.configuration').get_singleton()
        if not config or not config.ensure_conformity:
            return
        if self.to_conform() and not self.conformity_state:
            self.raise_user_error('post_conforming', self.rec_name)

    def get_rec_name(self, name):
        res = super(Invoice, self).get_rec_name(name)
        if self.conformity_state == 'pending':
            res = '***' + res
        return res

    @classmethod
    @ModelView.button
    def conform(cls, invoices):
        cls.write(invoices, {
            'conformity_state' : 'conforming',
            })
