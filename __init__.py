#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import invoice
from . import company


def register():
    Pool.register(
        invoice.Configuration,
        invoice.ConformGroup,
        invoice.ConformGroupUser,
        invoice.Invoice,
        company.Company,
        module='account_invoice_conformity', type_='model')
