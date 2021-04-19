# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Not, Equal
from trytond.config import config, parse_uri
from trytond import backend
from trytond.exceptions import UserError
from sql.functions import Function
from sql.conditionals import Case
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.wizard import Wizard, StateView, StateTransition, Button
from datetime import datetime
import itertools

__all__ = ['ConformGroupUser', 'ConformGroup', 'Invoice',
    'ConformGroupInvoice', 'Conformity', 'InvoiceConform',
    'InvoiceConformStart']

CONFORMITY_STATE = [
    ('pending', 'Pending'),
    ('conforming', 'Conforming'),
    ('gnc', 'Managing Nonconforming'),
    ('nonconforming', 'Nonconforming'),
    ]


class StringAgg(Function):
    __slots__ = ()
    uri = parse_uri(config.get('database', 'uri'))
    if uri.scheme == 'postgresql':
        _function = 'STRING_AGG'
    else:
        _function = 'group_concat'


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


class ConformGroupInvoice(ModelSQL):
    'Conform Group - Invoice'
    __name__ = 'account.invoice.conform_group-account.invoice'
    invoice = fields.Many2One('account.invoice', 'Invoice',
        required=True, select=True)
    group = fields.Many2One('account.invoice.conform_group', 'Group',
        required=True, select=True)


class Conformity(ModelSQL, ModelView):
    'Conformity'
    __name__ = 'account.invoice.conformity'
    invoice = fields.Many2One('account.invoice', 'Invoice', select=True,
        ondelete='CASCADE')
    group = fields.Many2One('account.invoice.conform_group', 'Group',
        states={
            'required': Bool(Eval('group_required')),
            }, depends=['group_required'], select=True, ondelete='CASCADE')
    group_required = fields.Function(fields.Boolean('Group Required'),
        'on_change_with_group_required')
    state = fields.Selection(CONFORMITY_STATE, 'Conformity State',
        select=True)
    nonconformity_culprit = fields.Selection([
            (None, ''),
            ('supplier', 'Supplier'),
            ('company', 'Company'),
            ], 'Nonconformity Culprit',
        states={
            'required': ((Eval('state') == 'nonconforming'))
            })
    description = fields.Text('Conforming Description')

    @classmethod
    def default_state(cls):
        return 'pending'

    @fields.depends('invoice')
    def on_change_with_group_required(self, name=None):
        if self.invoice and self.invoice.state == 'posted':
            return True
        return False

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Activity = pool.get('activity.activity')

        new_activities = []
        for values in vlist:
            new_activities += cls._get_activities(values)

        if new_activities:
            with Transaction().set_context(_check_access=False):
                Activity.create(a._save_values for a in new_activities)

        return super(Conformity, cls).create(vlist)

    @classmethod
    def write(cls, *args, **kwargs):
        pool = Pool()
        Activity = pool.get('activity.activity')

        actions = iter(args)
        new_activities = []
        for conformities, values in zip(actions, actions):
            for conformity in conformities:
                new_activities += cls._get_activities(values, conformity)

        if new_activities:
            Activity.create(a._save_values for a in new_activities)

        return super(Conformity, cls).write(*args)

    @classmethod
    def copy(cls, conformities, default=None):
        new_default = default.copy() if default else {}
        new_default.setdefault('state', cls.default_state())
        return super(Conformity, cls).copy(conformities, default=new_default)

    @classmethod
    def _get_activities(cls, values, record=None):
        pool = Pool()
        Activity = pool.get('activity.activity')
        ActivityType = pool.get('activity.type')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        Data = pool.get('ir.model.data')

        # Do not create an activity if description is not set...
        if 'description' not in values:
            return []
        description = values['description']
        # ...or does not change its value...
        if record:
            if description == record.description:
                return []
        # ...or is empty
        elif not description:
            return []

        invoice_id = values.get('invoice')
        if invoice_id:
            invoice = Invoice(invoice_id)
        else:
            if not record:
                return []
            invoice = record.invoice

        activity = Activity()
        activity.date = Date().today()
        data_meeting_type, = Data.search([
            ('module', '=', 'account_invoice_conformity'),
            ('fs_id', '=', 'meeting_type'),
            ], limit=1)
        activity.activity_type = ActivityType(data_meeting_type.db_id)
        activity.state = 'held'
        activity.description = description
        activity.subject = invoice.rec_name
        activity.resource = invoice
        activity.party = invoice.party
        employee = activity.default_employee()
        if not employee:
            user = User(Transaction().user)
            if user and user.employees:
                employee = user.employees[0]
            else:
                configuration = Configuration(1)
                employee = configuration.default_employee
        activity.employee = employee
        return [activity]


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    conformities = fields.One2Many('account.invoice.conformity',
        'invoice', 'Conformities',
        states={
            'invisible': Not(Equal(Eval('type'), 'in')),
            'required': Bool(Eval('type') == 'in') &
                ~Eval('state').in_(['cancel', 'draft']) &
                Bool(Eval('conformity_required')),
            },
        depends=['type', 'conformity_required', 'state'])
    conformities_state = fields.Function(fields.Selection(
                [(None, '')] + CONFORMITY_STATE,
            'Conformities State', states={
                'invisible': Not(Equal(Eval('type'), 'in')) &
                ~Bool(Eval('conformity_required')),
            },
            depends=['type', 'conformity_required'], sort=False),
            'get_conformities_state', searcher='search_conformities_state')
    activities = fields.One2Many('activity.activity', 'resource',
        'Activities')
    conformities_summary = fields.Function(fields.Text('Summary'),
        'get_conformities_summary')
    conformity_required = fields.Function(
        fields.Boolean('Conformity Required'), 'get_conformity_required')
    to_conform = fields.Function(fields.Boolean('To Conform'),
        'get_to_conform', searcher='search_to_conform')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        for fname in ('type', 'conformities'):
            if fname not in cls.party.on_change:
                cls.party.on_change.add(fname)
        cls._check_modify_exclude += ['conformities', 'conformities_state',
            'activities', 'conformities_summary']

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Conformity = pool.get('account.invoice.conformity')
        conformity = Conformity.__table__()
        sql_table = cls.__table__()
        table = TableHandler(cls, module_name)
        today = datetime.today()

        # Migration from 4.0: rename conformity_result into conformity_state
        if table.column_exist('conformity_result'):
            cursor.execute(*sql_table.update(
                    columns=[sql_table.conformity_state],
                    values=[
                        Case(((sql_table.conformity_state == 'closed') &
                              (sql_table.conformity_result == 'conforming'),
                                'conforming'),
                            ((sql_table.conformity_state == 'closed') &
                             (sql_table.conformity_result == 'nonconforming'),
                                'nonconforming'),
                            ((sql_table.conformity_state == 'pending') &
                             (sql_table.conformity_result == 'nonconforming'),
                                'gnc'),
                            else_='pending')]))
            table.drop_column('conformity_result')

        # Migration from 4.0: rename conformed_description into
        # conforming_description
        if (table.column_exist('conformed_description') and
                not table.column_exist('conforming_description')):
            table.column_rename('conformed_description',
                'conforming_description')

        # Migration from 4.0: rename disconformity_culprit into
        # nonconformity_culprit
        if (table.column_exist('disconformity_culprit') and
                not table.column_exist('nonconformity_culprit')):
            table.column_rename('disconformity_culprit',
                'nonconformity_culprit')

        # Migration from 4.8: copy conform_by into conform_group_invoice
        # and create conformities
        old_columns = {'nonconformity_culprit', 'conforming_description',
            'conformity_state', 'conform_by'}
        if old_columns.issubset(table._columns):
            cursor.execute(*conformity.insert(
                columns=[
                    conformity.invoice,
                    conformity.group,
                    conformity.state,
                    conformity.nonconformity_culprit,
                    conformity.description
                    ],
                values=sql_table.select(
                    sql_table.id,
                    sql_table.conform_by,
                    sql_table.conformity_state,
                    sql_table.nonconformity_culprit,
                    sql_table.conforming_description,
                    where=sql_table.conform_by != None)))
            cursor.execute(*conformity.update(
                columns=[conformity.create_uid, conformity.create_date],
                values=[0, today]))
            table.drop_column('conform_by')
            table.drop_column('nonconformity_culprit')
            table.drop_column('conforming_description')
            table.drop_column('conformity_state')

        super(Invoice, cls).__register__(module_name)

    @fields.depends('type', 'conformities')
    def on_change_party(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Conformity = pool.get('account.invoice.conformity')
        super(Invoice, self).on_change_party()

        configuration = Configuration(1)
        if self.type == 'in' and configuration.conformity_required:
            if not self.conformities:
                conformity = Conformity()
                conformity.state = 'pending'
                self.conformities = (conformity,)

    @classmethod
    def search_conformities_state(cls, name, clause):
        pool = Pool()
        Conformity = pool.get('account.invoice.conformity')

        Operator = fields.SQL_OPERATORS[clause[1]]
        table = Conformity.__table__()
        query = table.select(table.invoice,
            where=Operator(table.state, clause[2]))
        return [('id', 'in', query)]

    @classmethod
    def get_conformities_state(cls, invoices, name):
        Conformity = Pool().get('account.invoice.conformity')

        invoice_ids = [x.id for x in invoices]
        cursor = Transaction().connection.cursor()

        table = Conformity.__table__()
        query = table.select(
            table.invoice,
            StringAgg(table.state, ','),
            where=table.invoice.in_(invoice_ids),
            group_by=table.invoice)

        cursor.execute(*query)
        res = dict.fromkeys(invoice_ids)
        for invoice_id, states_str in cursor.fetchall():
            if states_str:
                state = None
                states = states_str.split(',')
                if len(states) == 1:
                    state = states[0]
                if 'pending' in states:
                    state = 'pending'
                elif 'gnc' in states:
                    state = 'gnc'
                elif 'nonconforming' in states:
                    state = 'nonconforming'
                elif 'conforming' in states:
                    state = 'conforming'
                res[invoice_id] = state
        return res

    @classmethod
    def get_conformity_required(cls, invoices, name):
        pool = Pool()
        Config = pool.get('account.configuration')
        config = Config(1)
        res = {}
        for invoice in invoices:
            res[invoice.id] = config.conformity_required
        return res

    def get_to_conform(self, name):
        Config = Pool().get('account.configuration')

        config = Config(1)
        return config.ensure_conformity or False

    @classmethod
    def search_to_conform(cls, name, clause):
        Config = Pool().get('account.configuration')

        config = Config(1)
        # if ensure_conformity is false, filter posted and paid invoices. Omit clause values
        if not config.ensure_conformity:
            return [('state', 'in', ['posted', 'paid'])]

    def to_pending(self):
        Config = Pool().get('account.configuration')
        config = Config(1)
        if (not config.ensure_conformity or self.type != 'in' or
                self.conformities_state is None):
            return False
        return True

    def check_conformity(self):
        Config = Pool().get('account.configuration')
        config = Config(1)
        for conformity in self.conformities:
            if not conformity.group:
                raise UserError(gettext('account_invoice_conformity.'
                        'msg_missing_conformity_group', invoice=self.rec_name))

        if not config.ensure_conformity or self.type != 'in':
            return

        if self.conformities_state != 'conforming':
            raise UserError(gettext(
                'account_invoice_conformity.msg_post_conforming',
                    invoice=self.rec_name))

    def get_rec_name(self, name):
        res = super(Invoice, self).get_rec_name(name)
        if self.type == 'in' and self.conformities_state:
            if self.conformities_state == 'pending':
                return ' P*** ' + res
            elif self.conformities_state == 'gnc':
                return ' GNC*** ' + res
            elif self.conformities_state == 'nonconforming':
                return ' NC*** ' + res
        return res

    @classmethod
    def draft(cls, invoices):
        pool = Pool()
        Conformity = pool.get('account.invoice.conformity')
        super(Invoice, cls).draft(invoices)
        to_pending = [i.conformities for i in invoices if i.to_pending()]
        to_write = list(itertools.chain(*to_pending))
        if to_write:
            Conformity.write(to_write, {
                    'state': 'pending',
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
        new_default = default.copy() if default else {}
        new_default.setdefault('activities')
        return super(Invoice, cls).copy(invoices, default=new_default)

    def get_conformities_summary(self, name):
        pool = Pool()
        Activity = pool.get('activity.activity')
        Data = pool.get('ir.model.data')

        data_meeting_type, = Data.search([
            ('module', '=', 'account_invoice_conformity'),
            ('fs_id', '=', 'meeting_type'),
            ], limit=1)
        activities = Activity.search([
                ('activity_type.id', '=', data_meeting_type.db_id),
                ('resource', '=', ('account.invoice', self.id))
                ], order=[('date', 'DESC')])
        body = []
        for activity in activities:
            employee = activity.employee.rec_name.upper()
            title = '{} - {}'.format(activity.date, employee)
            texts = '<br/>'.join(activity.description.split('\n') if
                activity.description else [])
            body.append(
                '<div align="left">'
                '<font size="4"><b>{}</b></font>'
                '</div>'
                '<div align="left">{}</div>'.format(title, texts))
        return '<div align="left"><br></div>'.join(body)


class InvoiceNonconformStart(ModelView):
    "Nonconform Invoices"
    __name__ = 'account.invoice.nonconformity.wizard.start'
    conformity = fields.Many2One('account.invoice.conformity', 'Conformity',
        domain=[('invoice', '=', Eval('context', {}).get('active_id', 0)),
               ('group.users', '=', Eval('user', 0))
                ], depends=['user'], required=True)
    conformity_state = fields.Selection([
           ('gnc', 'Nonconforming Pending'),
           ('nonconforming', 'Nonconforming'),
           ], 'Conformity State', required=True)
    nonconformity_culprit = fields.Selection([
            ('supplier', 'Supplier'),
            ('company', 'Company'),
            ], 'Nonconformity Culprit', required=True)
    conforming_description = fields.Text('Conforming Description')
    user = fields.Many2One('res.user', 'Active User', readonly=True)

    @staticmethod
    def default_conformity_state():
        return 'gnc'

    @staticmethod
    def default_user():
        return Transaction().user


class InvoiceNonconform(Wizard):
    "Nonconform Invoices"
    __name__ = 'account.invoice.nonconformity.wizard'
    start = StateView('account.invoice.nonconformity.wizard.start',
        'account_invoice_conformity.account_invoice_nonconformity_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Nonconforming', 'nonconforming', 'tryton-ok', default=True)
            ])
    nonconforming = StateTransition()

    def transition_nonconforming(self):
        pool = Pool()
        InvoiceConformity = pool.get('account.invoice.conformity')
        conformity = self.start.conformity
        with Transaction().set_context(_check_access=False):
            InvoiceConformity.write([conformity], {
                    'invoice': Transaction().context['active_id'],
                    'state': self.start.conformity_state,
                    'nonconformity_culprit': self.start.nonconformity_culprit,
                    'description': self.start.conforming_description
                    })
        return 'end'


class InvoiceConformStart(ModelView):
    "Conform Invoices"
    __name__ = 'account.invoice.conformity.wizard.start'
    conformity = fields.Many2One('account.invoice.conformity', 'Conformity',
        domain=[('invoice', '=', Eval('context', {}).get('active_id', 0)),
               ('group.users', '=', Eval('user', 0))
                ], depends=['user'], required=True)
    conforming_description = fields.Text('Conforming Description')
    user = fields.Many2One('res.user', 'Active User', readonly=True)

    @staticmethod
    def default_user():
        return Transaction().user


class InvoiceConform(Wizard):
    "Conform Invoices"
    __name__ = 'account.invoice.conformity.wizard'
    start = StateView('account.invoice.conformity.wizard.start',
        'account_invoice_conformity.account_invoice_conformity_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Conforming', 'conforming', 'tryton-ok', default=True)
            ])

    conforming = StateTransition()

    def transition_conforming(self):
        pool = Pool()
        InvoiceConformity = pool.get('account.invoice.conformity')
        conformity = self.start.conformity
        with Transaction().set_context(_check_access=False):
            InvoiceConformity.write([conformity], {
                'invoice': Transaction().context['active_id'],
                'state': 'conforming',
                'description': self.start.conforming_description
            })
        return 'end'
