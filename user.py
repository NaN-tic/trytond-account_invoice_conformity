# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['User']


class User:
    __metaclass__ = PoolMeta
    __name__ = "res.user"
    user_conform_groups = fields.Many2Many(
        'account.invoice.conform_group-res.user', 'user', 'group',
        'Conform Groups')
    conform_groups = fields.Function(fields.One2Many(
        'account.invoice.conform_group', 'user', 'Conform Groups IDs'),
        'on_change_with_user_conform_groups')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.insert(0, 'conform_groups')

    @fields.depends('conform_groups')
    def on_change_with_user_conform_groups(self, name=None):
        if self.user_conform_groups:
            return [x.id for x in self.user_conform_groups]
