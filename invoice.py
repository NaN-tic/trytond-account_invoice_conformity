#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Not, Equal
from trytond import backend
from trytond.transaction import Transaction
from sql.conditionals import Case

__all__ = ['Configuration', 'ConformGroupUser', 'ConformGroup', 'Invoice']

CONFORMITY_STATE = [
    (None, ''),
    ('pending', 'Pending'),
    ('conforming', 'Conforming'),
    ('nonconforming_pending', 'Nonconforming Pending'),
    ('nonconforming', 'Nonconforming'),
    ]


class Configuration:
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
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
        return None

    def to_conforming(self):
        Config = Pool().get('account.configuration')
        config = Config(1)

        if ((not config.ensure_conformity)
                or (self.type != 'in')
                or (self.conformity_state != None)):
            return False
        return True

    def to_pending(self):
        Config = Pool().get('account.configuration')
        config = Config(1)

        if ((not config.ensure_conformity)
                or (self.type != 'in')
                or (self.conformity_state == None)):
            return False
        return True

    def check_conformity(self):
        Config = Pool().get('account.configuration')

        config = Config(1)
        if (not config.ensure_conformity or (self.type != 'in')):
            return

        if self.conformity_state != 'conforming':
            self.raise_user_error('post_conforming', self.rec_name)

    def get_rec_name(self, name):
        res = super(Invoice, self).get_rec_name(name)
        if (self.conformity_state in ('pending',
                'nonconforming_pending')):
            res = '***' + res
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
    @ModelView.button
    def conform(cls, invoices):
        cls.write(invoices, {
            'conformity_state' : 'conforming',
            })

    @classmethod
    def view_attributes(cls):
        return super(Invoice, cls).view_attributes() + [
            ('//page[@id="conform"]', 'states', {
                    'invisible': (Eval('type') != 'in'),
                    })]

    @classmethod
    def copy(cls, invoices, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['conform_by'] = None
        default['conformity_state'] = None
        default['nonconformity_culprit'] = None
        default['conforming_description'] = None
        return super(Invoice, cls).copy(invoices, default=default)
