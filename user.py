#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['User']


class User:
    __metaclass__ = PoolMeta
    __name__ = "res.user"
    conform_groups = fields.One2Many('account.invoice.conform_group-res.user',
        'user', 'Conform Groups')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        # TODO
        # cls._context_fields.insert(0, 'conform_groups')
