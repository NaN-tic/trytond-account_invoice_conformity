=========================
Invoice Supplier Scenario
=========================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Install account_invoice_conformity::

    >>> config = activate_modules('account_invoice_conformity')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> payable = accounts['payable']

Create Employees::

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')
    >>> employee1 = Employee(party=Party(name='Employee'))
    >>> employee1.company = company
    >>> employee1.save()
    >>> employee2 = Employee(party=Party(name='Employee'))
    >>> employee2.company = company
    >>> employee2.save()
    >>> employee3 = Employee(party=Party(name='Employee'))
    >>> employee3.company = company
    >>> employee3.save()

Create account user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> account_user = User()
    >>> account_user.name = 'Account'
    >>> account_user.login = 'account'
    >>> account_user.main_company = company
    >>> account_user.employees.append(employee1)
    >>> account_user.employee = employee1
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> account_user.groups.append(account_group)
    >>> account_user.save()

Create account admin user::

    >>> account_user_admin = User()
    >>> account_user_admin.name = 'Account Admin'
    >>> account_user_admin.login = 'account_admin'
    >>> account_user_admin.main_company = company
    >>> account_user_admin.employees.append(employee2)
    >>> account_user_admin.employee = employee2
    >>> account_admin_group, = Group.find([('name', '=', 'Account Administration')])
    >>> account_user_admin.groups.append(account_admin_group)
    >>> account_user_admin.save()

Create conformity user::

    >>> conform_user = User()
    >>> conform_user.name = 'Conformity'
    >>> conform_user.login = 'conformity'
    >>> conform_user.main_company = company
    >>> conform_user.employees.append(employee3)
    >>> conform_user.employee = employee3
    >>> conform_group, = Group.find([('name', '=', 'Conform')])
    >>> conform_user.groups.append(conform_group)
    >>> conform_user.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Configure account::

    >>> AccountConfig = Model.get('account.configuration')
    >>> account_config = AccountConfig()
    >>> account_config.ensure_conformity = True
    >>> account_conformity_required = True
    >>> account_config.save()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create party::

    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.supplier_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Term')
    >>> payment_term_line = PaymentTermLine(type='remainder')
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create conform groups::

    >>> ConformGroup = Model.get('account.invoice.conform_group')
    >>> conform_group = ConformGroup()
    >>> conform_group.name = 'Account Conform Group'
    >>> conform_group.users.append(conform_user)
    >>> conform_group.save()
    >>> conform_group2 = ConformGroup()
    >>> conform_group2.name = 'Account Conform Group 2'
    >>> conform_group2.save()

Create activity reference::

    >>> IrModel = Model.get('ir.model')
    >>> ActivityReference = Model.get('activity.reference')
    >>> invoice_reference = ActivityReference()
    >>> invoice_reference.model, = IrModel.find(['model', '=', 'account.invoice'])
    >>> invoice_reference.save()

Create invoice::

    >>> config.user = account_user.id
    >>> config._context = User.get_preferences(True, config.context)
    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> Conformity = Model.get('account.invoice.conformity')
    >>> Activity = Model.get('activity.activity')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> invoice.account = payable
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> conformity = invoice.conformities.new()
    >>> conformity.invoice = invoice
    >>> conformity.group = conform_group
    >>> conformity.state = 'pending'
    >>> conformity.description = 'new conformity'
    >>> invoice.save()
    >>> invoice.conformities_state
    'pending'
    >>> len(invoice.activities) == 1
    True
    >>> activity, = invoice.activities
    >>> activity.description == conformity.description
    True
    >>> activity.resource == invoice
    True
    >>> activity.activity_type.name == 'System'
    True
    >>> Invoice.post([invoice.id], config.context) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Conform invoice::

    >>> config.user = conform_user.id
    >>> config._context = User.get_preferences(True, config.context)
    >>> conform = Wizard('account.invoice.conformity.wizard', [invoice])
    >>> conform.form.conformity, = invoice.conformities
    >>> conform.form.conforming_description = 'Test conformities'
    >>> conform.execute('conforming')

Check conformities are modified and activities are created throught the Wizard::

    >>> config.user = account_user.id
    >>> config._context = User.get_preferences(True, config.context)
    >>> invoice.reload()
    >>> invoice.conformities_state == 'conforming'
    True
    >>> len(invoice.activities) == 2
    True
    >>> Invoice.post([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state == 'posted'
    True

Create out invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state
    'posted'

Disable configuration and check error doesn't raise::

    >>> config.user = 1
    >>> account_config.ensure_conformity = False
    >>> account_config.save()
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> invoice.account = payable
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state
    'posted'
    >>> invoice.conformities_state == None
    True

Check to_conform invoices according account configuration::

    >>> new_invoce, = Invoice.copy([invoice], config.context)
    >>> len(Invoice.find([('to_conform', '=', True)])) == 3
    True
    >>> account_config.ensure_conformity = True
    >>> account_config.save()
    >>> len(Invoice.find([('to_conform', '=', True)])) == 4
    True
