=========================
Invoice Supplier Scenario
=========================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_invoice_conformity::

    >>> Module = Model.get('ir.module')
    >>> account_invoice_module, = Module.find(
    ...     [('name', '=', 'account_invoice_conformity')])
    >>> Module.install([account_invoice_module.id], config.context)
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Configure account::

    >>> AccountConfig = Model.get('account.configuration')
    >>> account_config = AccountConfig()
    >>> account_config.ensure_conformity = True
    >>> account_config.save()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> tax = set_tax_code(create_tax(Decimal('.10')))
    >>> tax.save()
    >>> invoice_base_code = tax.invoice_base_code
    >>> invoice_tax_code = tax.invoice_tax_code
    >>> credit_note_base_code = tax.credit_note_base_code
    >>> credit_note_tax_code = tax.credit_note_tax_code

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

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
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.supplier_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Term')
    >>> payment_term_line = PaymentTermLine(type='remainder')
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create in invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'Invoice "1 Party" can not be posted because it is not conformed.', ''))
    >>> invoice.conformity_state = 'pending'
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state
    u'posted'
    >>> invoice.rec_name
    u'***1 Party'

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
    u'posted'

Disable configuration and check error doesn't raise::

    >>> account_config.ensure_conformity = False
    >>> account_config.save()
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state
    u'posted'
    >>> invoice.conformity_state == None
    True
