#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import logging
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Bool, Eval, Id, Not, Or
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import safe_eval

__all__ = ['Specie', 'SpecieModel', 'SpecieFarmLine', 'Breed', 'Menu',
    'ActWindow']

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
        #domain=[
        #    ('default_uom.category', '=', Id('product', 'uom_cat_volume')),
        #    ],
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
    actions = fields.One2Many('ir.action.act_window', 'specie', 'Actions')
    menus = fields.One2Many('ir.ui.menu', 'specie', 'Menus')

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
        Model = pool.get('ir.model')
        ModelData = pool.get('ir.model.data')
        ActWindow = pool.get('ir.action.act_window')
        EventOrder = pool.get('farm.event.order')

        lang_codes = cls._get_lang_codes()
        animal_types_data = cls._get_animal_types_data()
        animal_types_set = set(animal_types_data.keys())

        menu_farm = Menu(ModelData.get_id(MODULE_NAME, 'menu_farm'))
        act_window_event_order = ActWindow(ModelData.get_id(MODULE_NAME,
                'act_farm_event_order'))

        with Transaction().set_context(language='en_US'):
            event_configuration_data = (
                cls._get_act_window_and_animal_types_per_event_model(
                    animal_types_set))

        order_type_labels = dict(EventOrder.fields_get(
                ['event_type'])['event_type']['selection'])

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
            logging.getLogger('farm.specie').debug(
                "current_menus=%s\ncurrent_actions=%s"
                % (current_menus, current_actions))

            with Transaction().set_context(lang_codes=lang_codes):
                specie_menu = cls._create_submenu(specie, specie.name,
                    menu_farm, specie_seq, current_menus)
            specie_seq += 1

            specie_submenu_seq = 1
            ####    Animal Types and Events menu generation    ####
            for animal_type in enabled_animal_types:
                with Transaction().set_context(lang_codes=lang_codes):
                    animal_menu = cls._create_menu_w_action(specie, [
                            ('specie', '=', specie.id),
                            ], {
                            'specie': specie.id,
                            'animal_type': animal_type,
                            },
                        animal_types_data[animal_type]['title'], specie_menu,
                        specie_submenu_seq, 'STOCK_JUSTIFY_FILL',
                        animal_types_data[animal_type]['group'],
                        animal_types_data[animal_type]['action'], True,
                        current_menus, current_actions)

                # The event's models are created in the system in a logic order
                #     to improve useability
                event_ids = [x.id for x in specie.events]
                event_ids = sorted(event_ids)

                animal_submenu_seq = 1
                for event in Model.browse(event_ids):
                    event_model = event.model
                    if (animal_type not in event_configuration_data[
                            event_model]['valid_animal_types']):
                        continue

                    event_domain = [
                        ('specie', '=', specie.id),
                        ]
                    event_context = {
                        'specie': specie.id,
                        }
                    if (len(event_configuration_data[event_model][
                            'valid_animal_types']) > 1):
                        event_domain.append(('animal_type', '=', animal_type))
                        event_context['animal_type'] = animal_type

                    generic_event = event_configuration_data[event_model][
                            'is_generic_event']
                    event_act_window = (
                        event_configuration_data[event_model]['act_window'])
                    seq = (generic_event and animal_submenu_seq or
                        20 + animal_submenu_seq)
                    icon = (generic_event and 'tryton-list' or
                            'tryton-preferences-system')
                    with Transaction().set_context(lang_codes=lang_codes):
                        cls._create_menu_w_action(specie, event_domain,
                            event_context, event_act_window.name, animal_menu,
                            seq, icon, None, event_act_window, False,
                            current_menus, current_actions)
                    animal_submenu_seq += 1
                specie_submenu_seq += 1

            # Orders submenus
            for animal_type in enabled_animal_types:
                with Transaction().set_context(lang_codes=lang_codes):
                    animal_orders_menu = cls._create_submenu(specie,
                        animal_types_data[animal_type]['orders_title'],
                        specie_menu, specie_submenu_seq, current_menus)

                orders_submenu_seq = 1
                for order_type in EventOrder.event_types_by_animal_type(
                        animal_type, True):
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
                    with Transaction().set_context(lang_codes=lang_codes):
                        cls._create_menu_w_action(specie, order_domain,
                            order_context, order_type_labels[order_type],
                            animal_orders_menu, orders_submenu_seq,
                            'tryton-spreadsheet',
                            animal_types_data[animal_type]['group'],
                            act_window_event_order, True, current_menus,
                            current_actions)
                    orders_submenu_seq += 1
                specie_submenu_seq += 1

            with Transaction().set_context(lang_codes=lang_codes):
                cls._create_additional_menus(specie, specie_menu,
                    specie_submenu_seq, current_menus, current_actions)

            logging.getLogger('farm.specie').debug(
                "Current_actions (to be deleted): %s" % current_actions)
            if current_actions:
                ActWindow.delete(current_actions)
            logging.getLogger('farm.specie').debug(
                "Current_menus (to be deleted): %s" % current_menus)
            if current_menus:
                Menu.delete(current_menus)

    @classmethod
    def _get_lang_codes(cls):
        Lang = Pool().get('ir.lang')
        langs = Lang.search([
                ('translatable', '=', True),
                ])
        return [x.code for x in langs]

    @classmethod
    def _create_additional_menus(cls, specie, specie_menu, specie_submenu_seq,
            current_menus, current_actions):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        ActWindow = pool.get('ir.action.act_window')

        act_window_feed_inventory = ActWindow(ModelData.get_id(MODULE_NAME,
                'act_farm_feed_inventory'))
        act_window_feed_prov_inventory = ActWindow(
            ModelData.get_id(MODULE_NAME,
                'act_farm_feed_provisional_inventory'))

        # Feed Inventories submenu
        feed_inventories_menu = cls._create_submenu(specie,
            'Silo Inventories', specie_menu, specie_submenu_seq,
            current_menus)
        specie_submenu_seq += 1
        cls._create_menu_w_action(specie, [
                ('specie', '=', specie.id),
                ], {
                    'specie': specie.id,
                },
            'Inventory', feed_inventories_menu, 1, 'tryton-list',
            None, act_window_feed_inventory, False, current_menus,
            current_actions)
        cls._create_menu_w_action(specie, [
                ('specie', '=', specie.id),
                ], {
                    'specie': specie.id,
                },
            'Provisional Inventory', feed_inventories_menu, 2,
            'tryton-list', None, act_window_feed_prov_inventory, False,
            current_menus, current_actions)

    @staticmethod
    def _get_animal_types_data():
        '''
        Returns a static and hardcoded dictionary of all animal types and
        their titles with translations. It is implemented as a function to
        allow to extend animal types.

        Put translations is, basically, to force system to generate titles
        translations.

        Returns a dictionary of tuples. the keys are animal types identifiers
        and values are tuples of animal type title and translated title.
        '''
        pool = Pool()
        ActWindow = pool.get('ir.action.act_window')
        Group = pool.get('res.group')
        ModelData = pool.get('ir.model.data')

        act_window_male_id = ModelData.get_id(MODULE_NAME,
            'act_farm_animal_male')
        act_window_female_id = ModelData.get_id(MODULE_NAME,
            'act_farm_animal_female')
        act_window_group_id = ModelData.get_id(MODULE_NAME,
            'act_farm_animal_group')
        act_window_individual_id = ModelData.get_id(MODULE_NAME,
            'act_farm_animal_individual')

        group_males_id = ModelData.get_id(MODULE_NAME, 'group_farm_males')
        group_females_id = ModelData.get_id(MODULE_NAME, 'group_farm_females')
        group_individuals_id = ModelData.get_id(MODULE_NAME,
            'group_farm_individuals')
        group_groups_id = ModelData.get_id(MODULE_NAME,
            'group_farm_groups')

        return {
            'male': {
                'title': 'Males',
                'orders_title': 'Males Orders',
                'action': ActWindow(act_window_male_id),
                'group': Group(group_males_id),
                },
            'female': {
                'title': 'Females',
                'orders_title': 'Females Orders',
                'action': ActWindow(act_window_female_id),
                'group': Group(group_females_id),
                },
            'individual': {
                'title': 'Individuals',
                'orders_title': 'Individuals Orders',
                'action': ActWindow(act_window_individual_id),
                'group': Group(group_individuals_id),
                },
            'group': {
                'title': 'Groups',
                'orders_title': 'Groups Orders',
                'action': ActWindow(act_window_group_id),
                'group': Group(group_groups_id),
                },
            }

    @staticmethod
    def _get_act_window_and_animal_types_per_event_model(animal_types_set):
        '''
        Returns a dictionary of Events with 'model name' as keys and
        'act_window', 'act_window_name' and 'valid_animal_types' as values
        '''
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        ActWindow = pool.get('ir.action.act_window')

        # It find all 'act_window's with 'res_model' to some farm event
        event_act_windows = ActWindow.search([
                ('res_model', 'like', 'farm.%.event'),
                ])

        # It find 'ir.model.data' of found 'act_window's which name
        #     (XML identified) is not empty (they has been defined in module,
        #     not created on previos function execution)
        event_act_window_models = ModelData.search([
                ('model', '=', 'ir.action.act_window'),
                ('db_id', 'in', [x.id for x in event_act_windows]),
                ('fs_id', '!=', None),
                ])
        event_act_windows_ids = [md.db_id for md in event_act_window_models]

        event_configuration = {}
        for act_window in ActWindow.browse(event_act_windows_ids):
            valid_animal_types = set(
                Pool().get(act_window.res_model).valid_animal_types())

            event_configuration[act_window.res_model] = {
                'act_window': act_window,
                'act_window_name': act_window.name,
                'valid_animal_types': valid_animal_types,
                # is_generic_event if its valid_animal_types are all
                #     animal types => difference is empty
                'is_generic_event':
                        not animal_types_set.difference(valid_animal_types)
                }
        return event_configuration

    @classmethod
    def _create_submenu(cls, specie, untranslated_title, parent_menu, sequence,
            current_menus):
        Menu = Pool().get('ir.ui.menu')

        menus = Menu.search([
                ('id', 'in', [x.id for x in current_menus]),
                ('parent', '=', parent_menu.id),
                ('name', '=', untranslated_title),
                ])
        values = {
            'name': untranslated_title,
            'parent': parent_menu.id,
            'sequence': sequence,
            'specie': specie.id,
            }
        if menus:
            Menu.write(menus, values)
            menu = menus[0]
            logging.getLogger('farm.specie').debug("Writting menus %s and "
                "removing from current_menus" % menus)
            current_menus.remove(menu)
        else:
            menu, = Menu.create([values])
            logging.getLogger('farm.specie').debug("Created new menu %s"
                % menu)
        cls._write_field_in_langs(Menu, menu, 'name', untranslated_title)
        return menu

    @classmethod
    def _create_menu_w_action(cls, specie, new_domain, new_context,
            untranslated_title, parent_menu, sequence, menu_icon, group,
            original_action, translate_action, current_menus, current_actions):
        pool = Pool()
        ActWindow = pool.get('ir.action.act_window')
        Menu = pool.get('ir.ui.menu')
        ModelData = pool.get('ir.model.data')

        menus = Menu.search([
                ('id', 'in', [x.id for x in current_menus]),
                ('parent', '=', parent_menu.id),
                ('name', '=', untranslated_title),
                ])
        act_window = None
        menu = None
        if menus:
            menu = menus[0]
            act_window = menu.action

        if not new_domain:
            new_domain = []
        original_domain = (original_action.domain and
                safe_eval(original_action.domain))
        if original_domain and isinstance(original_domain, list):
            new_domain.extend(original_domain)

        original_context = (original_action.context
            and safe_eval(original_action.context))
        if original_context and isinstance(original_context, dict):
            new_context.update(original_context)

        action_vals = {
            'specie': specie.id,
            'domain': str(new_domain),
            'context': str(new_context),
            }

        if act_window:
            ActWindow.write([act_window], action_vals)
            logging.getLogger('farm.specie').debug("Writting action %s to be "
                "placed in a menu" % act_window)
            if act_window in current_actions:
                logging.getLogger('farm.specie').debug(
                    "Removing from current_actions")
                current_actions.remove(act_window)
        else:
            logging.getLogger('farm.specie').debug(
                "Creating new action to be placed in menu copying from "
                "original action %s"
                % original_action)
            act_window, = ActWindow.copy([original_action], action_vals)
        if translate_action:
            cls._write_field_in_langs(ActWindow, act_window, 'name',
                untranslated_title)
            pass

        group_ids = group and [group.id] or []
        if group_ids:
            group_manager_id = ModelData.get_id(MODULE_NAME,
                'group_farm_admin')
            group_ids.append(group_manager_id)

        menu_vals = {
            'name': untranslated_title,
            'parent': parent_menu.id,
            'sequence': sequence,
            'groups': [('set', group_ids)],
            'icon': 'tryton-list',
            'action': ('ir.action.act_window', act_window.id),
            'specie': specie.id,
            #'keyword': 'tree_open',
            }

        if menu:
            Menu.write([menu], menu_vals)
            logging.getLogger('farm.specie').debug("Writing menu %s with "
                "action %s and removing from current_menus"
                % (menu, act_window.id))
            current_menus.remove(menu)
        else:
            menu, = Menu.create([menu_vals])
            logging.getLogger('farm.specie').debug("Created new menu %s with "
                "action %s" % (menu, act_window.id))
        cls._write_field_in_langs(Menu, menu, 'name', untranslated_title)
        return menu

    @classmethod
    def _write_field_in_langs(cls, Proxy, obj, fieldname, untranslated_value):
        Translation = Pool().get('ir.translation')
        context = Transaction().context
        lang_codes = context.get('lang_codes') or cls._get_lang_codes()

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

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['actions'] = False
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


class Menu(ModelSQL, ModelView):
    __name__ = 'ir.ui.menu'
    specie = fields.Many2One('farm.specie', 'Specie', ondelete='CASCADE')


class ActWindow(ModelSQL, ModelView):
    __name__ = 'ir.action.act_window'
    specie = fields.Many2One('farm.specie', 'Specie', ondelete='CASCADE')
