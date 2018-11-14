# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['User']


class User(metaclass=PoolMeta):
    __name__ = "res.user"
    user_conform_groups = fields.Many2Many(
        'account.invoice.conform_group-res.user', 'user', 'group',
        'Conform Groups')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.insert(0, 'user_conform_groups')