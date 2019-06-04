# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import logging
from operator import attrgetter

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONDecoder, PYSONEncoder, Bool, Eval, Id, Not, Or
from trytond.transaction import Transaction

__all__ = ['Specie', 'SpecieModel', 'SpecieFarmLine', 'Breed',
    'UIMenu', 'ActionActWindow', 'ActionWizard']

MODULE_NAME = 'farm'


def _enabled_STATES(depending_fieldname):
    return {
        'readonly': Not(Bool(Eval(depending_fieldname))),
        'required': Bool(Eval(depending_fieldname)),
        }


class Specie(ModelSQL, ModelView):
    '''Animal Specie'''
    __name__ = 'farm.specie'

    name = fields.Char('Name', translate=True, required=True,
        help='Name of the specie. ie. "Pig"')
    male_product = fields.Many2One('product.product', "Male's Product",
        domain=[('default_uom.category', '=', Id('product', 'uom_cat_unit'))],
        states=_enabled_STATES('male_enabled'), depends=['male_enabled'])
    male_enabled = fields.Boolean('Males Enabled', help="If checked the menus "
        "to manage this kind of animal will be generated. If you don't want "
        "it, uncheck and put a generic product or other type of animal "
        "because it is required.")
    female_product = fields.Many2One('product.product', "Female's Product",
        domain=[('default_uom.category', '=', Id('product', 'uom_cat_unit'))],
        states=_enabled_STATES('female_enabled'), depends=['female_enabled'])
    female_enabled = fields.Boolean('Females Enabled', help="If checked the "
        "menus to manage this kind of animal will be generated. If you don't "
        "want it, uncheck and put a generic product or other type of animal "
        "because it is required.")
    individual_product = fields.Many2One('product.product',
        "Individual's Product",
        domain=[('default_uom.category', '=', Id('product', 'uom_cat_unit'))],
        states=_enabled_STATES('individual_enabled'),
        depends=['individual_enabled'])
    individual_enabled = fields.Boolean('Individuals Enabled', help="If "
        "checked the menus to manage this kind of animal will be generated. "
        "If you don't want it, uncheck and put a generic product or other "
        "type of animal because it is required.")
    group_product = fields.Many2One('product.product', "Group's Product",
        domain=[('default_uom.category', '=', Id('product', 'uom_cat_unit'))],
        states=_enabled_STATES('group_enabled'), depends=['group_enabled'])
    group_enabled = fields.Boolean('Groups Enabled', help="If checked the "
        "menus to manage this kind of animal will be generated. If you don't "
        "want it, uncheck and put a generic product or other type of animal "
        "because it is required.")
    semen_product = fields.Many2One('product.product', "Semen's Product",
        # TODO: it doesn't work but it should
        # domain=[
        #     ('default_uom.category', '=', Id('product', 'uom_cat_volume')),
        #     ],
        states={
            'readonly': Not(Or(Bool(Eval('male_enabled')),
                    Bool(Eval('female_enabled')))),
            'required': Or(Bool(Eval('male_enabled')),
                    Bool(Eval('female_enabled'))),
            }, depends=['male_enabled', 'female_enabled'],
        help="Product for the mixture of semen to raise the expected "
        "quality.\nIt is used in the Production lots produced in the "
        "Extraction Events and in the BoM containers for doses used in "
        "deliveries to farms for inseminations.")
    breeds = fields.One2Many('farm.specie.breed', 'specie', 'Breeds')
    farm_lines = fields.One2Many('farm.specie.farm_line',
        'specie', 'Farms')
    removed_location = fields.Many2One('stock.location', 'Removed Location',
        domain=[('type', '=', 'lost_found')], required=True,
        help='Virtual location where removed animals are moved to.')
    foster_location = fields.Many2One('stock.location', 'Foster Location',
        domain=[('type', '=', 'lost_found')], required=True,
        help='Virtual location where fostered animals are moved to.')
    lost_found_location = fields.Many2One('stock.location',
        'Lost and Found Location', domain=[('type', '=', 'lost_found')],
        required=True,
        help='Virtual location where lost or found animals are moved to.')
    feed_lost_found_location = fields.Many2One('stock.location',
        'Feed Lost Location', domain=[('type', '=', 'lost_found')],
        required=True)
    events = fields.Many2Many('farm.specie-ir.model', 'specie', 'model',
        'Events', domain=[('model', 'like', 'farm.%.event')],
        help='Type of events available for this specie')
    menus = fields.One2Many('ir.ui.menu', 'specie', 'Menus')
    actions = fields.One2Many('ir.action.act_window', 'specie', 'Actions')
    wizards = fields.One2Many('ir.action.wizard', 'specie', 'Wizards')

    @classmethod
    def __setup__(cls):
        super(Specie, cls).__setup__()
        cls._sql_constraints += [
            ('semen_product_uniq', 'UNIQUE (semen_product)',
                'The Semen\'s Product of the Specie must be unique.'),
            ]
        cls._error_messages.update({
                'no_animal_type_enabled': ('The action "Create menus and '
                    'actions" has been launched for the specie "%s" but it '
                    'does not have any animal type enabled.')
                })
        cls._buttons.update({
                'create_menu_entries': {}
                })

    @staticmethod
    def default_male_enabled():
        return True

    @staticmethod
    def default_female_enabled():
        return True

    @staticmethod
    def default_individual_enabled():
        return True

    @staticmethod
    def default_group_enabled():
        return True

    @classmethod
    @ModelView.button
    def create_menu_entries(cls, species):
        """
        Create all menu options (and actions) for:
        - Males
        - Females
        - Groups/Lots
        - Individuals
        - Events related with the specie

        Store menus and actions created in order to be able to remove or
        recreate them later.

        If menu entries (and actions) had already been created, do not remove
        them but create only the missing ones, otherwise user shortcuts to
        existing menu entries would become invalid or would be removed.
        If necessary, replace events many2many by a one2many one with
        related menu and actions.
        """
        pool = Pool()
        Menu = pool.get('ir.ui.menu')
        ModelData = pool.get('ir.model.data')
        ActWindow = pool.get('ir.action.act_window')
        EventOrder = pool.get('farm.event.order')

        menus_by_animal_type = cls._get_menus_by_animal_type()
        animal_types_set = set(menus_by_animal_type.keys())
        menus_by_event_type = cls._get_menus_by_event_type()
        event_name_by_model = {}

        farm_menu = Menu(ModelData.get_id(MODULE_NAME, 'menu_farm'))
        specie_menu_template = Menu(ModelData.get_id(MODULE_NAME,
                'menu_specie_menu_template'))
        event_order_menu = Menu(ModelData.get_id(MODULE_NAME,
                'menu_farm_event_order'))

        # order_type_labels = dict(EventOrder.fields_get(
        #         ['event_type'])['event_type']['selection'])

        specie_seq = 1
        for specie in species:
            enabled_animal_types = []
            for animal_type in animal_types_set:
                if getattr(specie, '%s_enabled' % animal_type):
                    enabled_animal_types.append(animal_type)
            if not enabled_animal_types:
                cls.raise_user_error('no_animal_type_enabled', specie.rec_name)

            current_menus = list(specie.menus)[:]
            current_actions = list(specie.actions)[:]
            current_wizards = list(specie.wizards)[:]
            logging.getLogger('farm.specie').debug(
                "current_menus=%s\ncurrent_actions=%s\ncurrent_wizards=%s"
                % (current_menus, current_actions, current_wizards))

            specie_menu = specie._duplicate_menu(specie_menu_template,
                farm_menu, specie_seq, current_menus, current_actions,
                current_wizards, new_name=specie.name)
            specie_seq += 1

            specie_submenu_seq = 1
            for animal_type in enabled_animal_types:
                new_domain = [
                    ('specie', '=', specie.id),
                    ]
                new_context = {
                    'specie': specie.id,
                    'animal_type': animal_type,
                    }
                animals_menu = specie._duplicate_menu(
                    menus_by_animal_type[animal_type]['animals'],
                    specie_menu, specie_submenu_seq, current_menus,
                    current_actions, current_wizards, new_domain=new_domain,
                    new_context=new_context)
                specie_submenu_seq += 1

                # The event's models are created in the system in a logic order
                #     to improve useability
                enabled_events = sorted(specie.events[:], key=attrgetter('id'))

                new_domain.append(('animal_type', '=', animal_type))

                animal_submenu_seq = 1
                for event in enabled_events:
                    model_name = event.model
                    event_menu = None
                    if model_name in menus_by_event_type['generic']:
                        event_menu = menus_by_event_type['generic'][model_name]
                    elif (animal_type in menus_by_event_type and
                            model_name in menus_by_event_type[animal_type]):
                        event_menu = (
                            menus_by_event_type[animal_type][model_name])
                    else:
                        continue
                    event_name_by_model[model_name] = event_menu.name

                    specie._duplicate_menu(event_menu, animals_menu,
                        animal_submenu_seq, current_menus, current_actions,
                        current_wizards, new_domain=new_domain,
                        new_context=new_context)
                    animal_submenu_seq += 1

                for extra_menu in menus_by_animal_type[animal_type]['extra']:
                    specie._duplicate_menu(extra_menu, animals_menu,
                        animal_submenu_seq, current_menus, current_actions,
                        current_wizards, new_domain=new_domain,
                        new_context=new_context)
                    animal_submenu_seq += 1

            # Orders submenus
            for animal_type in enabled_animal_types:
                orders_menu = specie._duplicate_menu(
                    menus_by_animal_type[animal_type]['orders'],
                    specie_menu, specie_submenu_seq, current_menus,
                    current_actions, current_wizards)
                specie_submenu_seq += 1

                orders_submenu_seq = 1
                for order_type in EventOrder.event_types_by_animal_type(
                        animal_type, True):
                    event_name = event_name_by_model.get('farm.%s.event'
                        % order_type)
                    order_domain = [
                        ('specie', '=', specie.id),
                        ('animal_type', '=', animal_type),
                        ('event_type', '=', order_type),
                        ]
                    order_context = {
                        'specie': specie.id,
                        'animal_type': animal_type,
                        'event_type': order_type,
                        }
                    specie._duplicate_menu(event_order_menu,
                        orders_menu, orders_submenu_seq, current_menus,
                        current_actions, current_wizards,
                        new_name=event_name, new_icon='tryton-spreadsheet',
                        new_domain=order_domain, new_context=order_context)
                    orders_submenu_seq += 1
                specie_submenu_seq += 1

            specie._create_additional_menus(specie_menu,
                specie_submenu_seq, current_menus, current_actions,
                current_wizards)

            logging.getLogger('farm.specie').debug(
                "Current actions (to be deleted): %s" % current_actions)
            if current_actions:
                ActWindow.delete(current_actions)
            logging.getLogger('farm.specie').debug(
                "Current wizards (to be deleted): %s" % current_wizards)
            if current_wizards:
                ActWindow.delete(current_wizards)
            logging.getLogger('farm.specie').debug(
                "Current menus (to be deleted): %s" % current_menus)
            if current_menus:
                Menu.delete(current_menus)
        return 'reload menu'

    def _create_additional_menus(self, specie_menu, specie_submenu_seq,
            current_menus, current_actions, current_wizards):
        pool = Pool()
        Menu = pool.get('ir.ui.menu')
        ModelData = pool.get('ir.model.data')

        silo_inventories_menu = Menu(ModelData.get_id(MODULE_NAME,
                'menu_farm_silo_inventories'))
        feed_inventory_menu = Menu(ModelData.get_id(MODULE_NAME,
                'menu_farm_feed_inventory'))
        feed_provisional_inventory_menu = Menu(ModelData.get_id(MODULE_NAME,
                'menu_farm_feed_provisional_inventory'))

        # Feed Inventories submenu
        feed_inventories_menu = self._duplicate_menu(silo_inventories_menu,
            specie_menu, specie_submenu_seq, current_menus,
            current_actions, current_wizards)
        specie_submenu_seq += 1

        new_domain = [
            ('specie', '=', self.id),
            ]
        new_context = {
            'specie': self.id,
            }
        self._duplicate_menu(feed_inventory_menu, feed_inventories_menu, 1,
            current_menus, current_actions, current_wizards,
            new_domain=new_domain, new_context=new_context)
        self._duplicate_menu(feed_provisional_inventory_menu,
            feed_inventories_menu, 2, current_menus, current_actions,
            current_wizards, new_domain=new_domain, new_context=new_context)

        return specie_submenu_seq

    @staticmethod
    def _get_menus_by_animal_type():
        pool = Pool()
        Menu = pool.get('ir.ui.menu')
        ModelData = pool.get('ir.model.data')
        return {
            'male': {
                'animals': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_animal_males')),
                'orders': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_order_males')),
                'extra': [],
                },
            'female': {
                'animals': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_animal_females')),
                'orders': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_order_females')),
                'extra': [
                    Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_create_female')),
                    ],
                },
            'individual': {
                'animals': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_animal_individuals')),
                'orders': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_order_individuals')),
                'extra': [],
                },
            'group': {
                'animals': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_animal_groups')),
                'orders': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_order_groups')),
                'extra': [],
                },
            }

    @staticmethod
    def _get_menus_by_event_type():
        pool = Pool()
        Menu = pool.get('ir.ui.menu')
        ModelData = pool.get('ir.model.data')
        return {
            'generic': {
                'farm.move.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_move_event')),
                'farm.feed.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_feed_event')),
                'farm.medication.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_medication_event')),
                'farm.transformation.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_transformation_event')),
                'farm.removal.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_removal_event')),
                },
            'male': {
                'farm.semen_extraction.event': Menu(
                    ModelData.get_id(MODULE_NAME,
                        'menu_farm_semen_extraction_event')),
                },
            'female': {
                'farm.insemination.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_insemination_event')),
                'farm.pregnancy_diagnosis.event': Menu(
                    ModelData.get_id(MODULE_NAME,
                        'menu_farm_pregnancy_diagnosis_event')),
                'farm.abort.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_abort_event')),
                'farm.farrowing.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_farrowing_event')),
                'farm.foster.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_foster_event')),
                'farm.weaning.event': Menu(ModelData.get_id(MODULE_NAME,
                        'menu_farm_weaning_event')),
                },
        }

    def _duplicate_menu(self, original_menu, parent_menu, sequence,
            current_menus, current_actions, current_wizards, new_name=None,
            new_icon=None, new_domain=None, new_context=None):
        pool = Pool()
        Menu = pool.get('ir.ui.menu')

        menus = Menu.search([
                ('id', 'in', [x.id for x in current_menus]),
                ('parent', '=', parent_menu.id),
                ('name', '=', new_name if new_name else original_menu.name),
                ])
        menu = None
        if menus:
            menu = menus[0]

        menu_action = self._duplicate_menu_action(menu, original_menu,
            current_actions, current_wizards, new_domain, new_context)

        menu_vals = {
            'parent': parent_menu.id,
            'sequence': sequence,
            'action': str(menu_action) if menu_action else None,
            'specie': self.id,
            'active': True,
            }
        if new_name:
            menu_vals['name'] = new_name
        if new_icon:
            menu_vals['icon'] = new_icon

        if menu:
            logging.getLogger('farm.specie').debug("Writting menu %s" % menu)
            Menu.write([menu], menu_vals)
            if menu in current_menus:
                current_menus.remove(menu)
        else:
            logging.getLogger('farm.specie').debug("Creating new menu copying "
                "from original menu %s" % original_menu)
            menu, = Menu.copy([original_menu])
            Menu.write([menu], menu_vals)
        if new_name:
            self._write_field_in_langs(Menu, menu, 'name', new_name)
        return menu

    def _duplicate_menu_action(self, menu, original_menu, current_actions,
            current_wizards, new_domain=None, new_context=None):
        pool = Pool()
        Keyword = pool.get('ir.action.keyword')

        if not original_menu.action:
            return None

        original_action = original_menu.action
        Action = original_action.__class__

        action_vals = {
            'specie': self.id,
            }

        if hasattr(original_action, 'domain'):
            domain = (
                PYSONDecoder().decode(original_action.pyson_domain)
                if original_action.pyson_domain else [])
            if new_domain:
                domain.extend(new_domain)

            action_vals['domain'] = PYSONEncoder().encode(domain)

        if hasattr(original_action, 'context'):
            original_context = (
                PYSONDecoder().decode(original_action.pyson_context)
                if original_action.pyson_context else [])
            if original_context:
                new_context.update(original_context)

            action_vals['context'] = PYSONEncoder().encode(new_context)

        menu_action = menu.action if menu else None
        if menu_action:
            Action.write([menu_action], action_vals)
            logging.getLogger('farm.specie').debug("Writting action %s to "
                "be placed in menu %s" % (menu_action, menu))
            if menu_action in current_actions:
                logging.getLogger('farm.specie').debug(
                    "Removing from current_actions")
                current_actions.remove(menu_action)
            elif menu_action in current_wizards:
                logging.getLogger('farm.specie').debug(
                    "Removing from current_wizards")
                current_wizards.remove(menu_action)
        else:
            logging.getLogger('farm.specie').info(
                "Creating new action as copy of %s to be placed in menu %s"
                % (original_action, menu if menu else original_menu))
            menu_action, = Action.copy([original_action], action_vals)
            Keyword.delete([a for a in menu_action.keywords])
        return menu_action

    @classmethod
    def _write_field_in_langs(cls, Proxy, obj, fieldname, untranslated_value):
        Translation = Pool().get('ir.translation')
        lang_codes = cls._get_lang_codes()

        for lang in lang_codes:
            translated_value = Translation.get_source('farm.specie', 'view',
                lang, untranslated_value)
            logging.getLogger('farm.specie').debug(
                "Translated value of name='farm.specie', ttype='view', "
                "lang='%s', source='%s': >%s<" % (lang, untranslated_value,
                    translated_value))
            if translated_value:
                with Transaction().set_context(language=lang):
                    Proxy.write([obj], {
                            fieldname: translated_value,
                            })

    @staticmethod
    def _get_lang_codes():
        Lang = Pool().get('ir.lang')
        langs = Lang.search([
                ('translatable', '=', True),
                ])
        return [x.code for x in langs]

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['actions'] = False
        default['wizards'] = False
        default['menus'] = False
        return super(Specie, cls).copy(records, default=default)


class Breed(ModelSQL, ModelView):
    'Breed of Specie'
    __name__ = 'farm.specie.breed'

    specie = fields.Many2One('farm.specie', 'Specie', required=True,
            ondelete='CASCADE')
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(Breed, cls).__setup__()
        cls._sql_constraints = [
            ('name_specie_uniq', 'UNIQUE(specie, name)',
                'Breed name must be unique per specie.'),
            ]


class SpecieFarmLine(ModelSQL, ModelView):
    'Managed Farm of specie'
    __name__ = 'farm.specie.farm_line'

    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        ondelete='CASCADE')
    farm = fields.Many2One('stock.location', 'Farm', required=True,
        domain=[('type', '=', 'warehouse')])
    event_order_sequence = fields.Many2One('ir.sequence',
        "Events Orders' Sequence", required=True, domain=[
            ('code', '=', 'farm.event.order')
            ],
        help="Sequence used for the Event Orders in this farm.")
    has_male = fields.Boolean('Males', help="In this farm there are males.")
    male_sequence = fields.Many2One('ir.sequence', "Males' Sequence",
        domain=[('code', '=', 'farm.animal')],
        states=_enabled_STATES('has_male'), depends=['has_male'],
        help='Sequence used for male lots and animals.')
    semen_lot_sequence = fields.Many2One('ir.sequence',
        "Extracted Semen Lots' Sequence", domain=[
            ('code', '=', 'stock.lot'),
            ], states=_enabled_STATES('has_male'), depends=['has_male'])
    dose_lot_sequence = fields.Many2One('ir.sequence',
        "Semen Dose Lots' Sequence", domain=[
            ('code', '=', 'stock.lot'),
            ], states=_enabled_STATES('has_male'), depends=['has_male'])
    has_female = fields.Boolean('Females',
        help="In this farm there are females.")
    female_sequence = fields.Many2One('ir.sequence', "Females' Sequence",
        domain=[('code', '=', 'farm.animal')],
        states=_enabled_STATES('has_female'), depends=['has_female'],
        help='Sequence used for female production lots and animals.')
    has_individual = fields.Boolean('Individuals',
        help="In this farm there are individuals.")
    individual_sequence = fields.Many2One('ir.sequence',
        "Individuals' Sequence", domain=[('code', '=', 'farm.animal')],
        states=_enabled_STATES('has_individual'), depends=['has_individual'],
        help="Sequence used for individual lots and animals.")
    has_group = fields.Boolean('Groups',
        help="In this farm there are groups.")
    group_sequence = fields.Many2One('ir.sequence', "Groups' Sequence",
        domain=[('code', '=', 'farm.animal.group')],
        states=_enabled_STATES('has_group'), depends=['has_group'],
        help='Sequence used for group production lots and animals.')

    @classmethod
    def __setup__(cls):
        super(SpecieFarmLine, cls).__setup__()
        cls._sql_constraints += [
            ('specie_farm_uniq', 'UNIQUE (specie, farm)',
                'The Farm of Managed Farms of an specie must be unique.'),
            ]


class SpecieModel(ModelSQL):
    'Specie - Model'
    __name__ = 'farm.specie-ir.model'
    _table = 'farm_specie_ir_model'
    specie = fields.Many2One('farm.specie', 'Specie', ondelete='CASCADE',
        required=True, select=True)
    model = fields.Many2One('ir.model', 'Model', required=True, select=True)


class UIMenu:
    __name__ = 'ir.ui.menu'
    __metaclass__ = PoolMeta
    specie = fields.Many2One('farm.specie', 'Specie', ondelete='CASCADE')


class ActionActWindow:
    __name__ = 'ir.action.act_window'
    __metaclass__ = PoolMeta
    specie = fields.Many2One('farm.specie', 'Specie', ondelete='CASCADE')


class ActionWizard:
    __name__ = 'ir.action.wizard'
    __metaclass__ = PoolMeta
    specie = fields.Many2One('farm.specie', 'Specie', ondelete='CASCADE')
