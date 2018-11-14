#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import invoice
from . import user


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationConformity,
        invoice.ConformGroup,
        invoice.ConformGroupUser,
        invoice.Invoice,
        user.User,
        module='account_invoice_conformity', type_='model')
