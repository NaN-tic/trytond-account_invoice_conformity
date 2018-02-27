#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import invoice


def register():
    Pool.register(
        configuration.Configuration,
        invoice.ConformGroup,
        invoice.ConformGroupUser,
        invoice.Invoice,
        module='account_invoice_conformity', type_='model')
