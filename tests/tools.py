from decimal import Decimal
from proteus import Model


def create_animal_product(name, list_price, cost_price, weaning_price=None):
    Template = Model.get('product.template')
    ProductUom = Model.get('product.uom')
    unit, = ProductUom.find([('name', '=', 'Unit')])

    template = Template()
    template.name = name
    template.default_uom = unit
    template.type = 'goods'
    template.list_price = Decimal(str(list_price))
    if weaning_price:
        template.weaning_price = Decimal(str(weaning_price))
    template.save()
    product, = template.products
    product.cost_price = Decimal(str(cost_price))
    product.save()
    return product

def create_semen_product(name, list_price, cost_price):
    Template = Model.get('product.template')
    ProductUom = Model.get('product.uom')

    cm3, = ProductUom.find([('name', '=', 'Cubic centimeter')])
    template = Template()
    template.name = name
    template.default_uom = cm3
    template.type = 'goods'
    template.consumable = True
    template.list_price = Decimal(str(list_price))
    template.save()
    product, = template.products
    product.cost_price = Decimal(str(cost_price))
    product.save()
    return product

def create_feed_product(name, list_price, cost_price):
    Template = Model.get('product.template')
    ProductUom = Model.get('product.uom')

    kg, = ProductUom.find([('name', '=', 'Kilogram')])
    template = Template()
    template.name = name
    template.default_uom = kg
    template.type = 'goods'
    template.list_price = Decimal(str(list_price))
    template.save()
    product, = template.products
    product.cost_price = Decimal(str(cost_price))
    product.save()
    return product

def create_specie(name='Pig'):
    group_product = create_animal_product('Group of %s' % name, 30, 20, 25)
    individual_product = create_animal_product('Individual %s' % name, 40, 25)
    female_product = create_animal_product('Female %s' % name, 40, 25)
    male_product = create_animal_product('Male %s' % name, 40, 25)
    semen_product = create_semen_product('%s Semen' % name, 400, 250)

    SequenceType = Model.get('ir.sequence.type')
    event_order_sequence_type, = SequenceType.find([('name', '=',
                'Event Order')])
    Sequence = Model.get('ir.sequence')
    event_order_sequence = Sequence(
        name='Event Order Pig Warehouse 1',
        sequence_type=event_order_sequence_type,
        padding=4)
    event_order_sequence.save()
    animal_sequence_type, = SequenceType.find([('name', '=', 'Animal')])
    male_sequence = Sequence(
        name='Male Pig Warehouse 1',
        sequence_type=SequenceType(animal_sequence_type.id),
        padding=4)
    male_sequence.save()
    lot_sequence_type, = SequenceType.find([('name', '=', 'Stock Lot')])
    semen_lot_sequence = Sequence(
        name='Semen Extracted Lot Pig Warehouse 1',
        sequence_type=SequenceType(lot_sequence_type.id),
        padding=4)
    semen_lot_sequence.save()
    semen_dose_lot_sequence = Sequence(
        name='Semen Dose Lot Pig Warehouse 1',
        sequence_type=SequenceType(lot_sequence_type.id),
        padding=4)
    semen_dose_lot_sequence.save()
    female_sequence = Sequence(
        name='Female Pig Warehouse 1',
        sequence_type=SequenceType(animal_sequence_type.id),
        padding=4)
    female_sequence.save()
    individual_sequence = Sequence(
        name='Individual Pig Warehouse 1',
        sequence_type=SequenceType(animal_sequence_type.id),
        padding=4)
    individual_sequence.save()
    animal_group_sequence_type, = SequenceType.find([('name', '=',
                'Animal Group')])
    group_sequence = Sequence(
        name='Groups Pig Warehouse 1',
        sequence_type=SequenceType(animal_group_sequence_type.id),
        padding=4)
    group_sequence.save()

    Location = Model.get('stock.location')
    lost_found_location, = Location.find([('type', '=', 'lost_found')])
    warehouse, = Location.find([('type', '=', 'warehouse')])
    production_location, = Location.find([('type', '=', 'production')], limit=1)

    Specie = Model.get('farm.specie')
    SpecieBreed = Model.get('farm.specie.breed')
    SpecieFarmLine = Model.get('farm.specie.farm_line')
    specie = Specie(
        name=name,
        male_enabled=True,
        male_product=male_product,
        semen_product=semen_product,
        female_enabled=True,
        female_product=female_product,
        individual_enabled=True,
        individual_product=individual_product,
        group_enabled=True,
        group_product=group_product,
        removed_location=lost_found_location,
        foster_location=lost_found_location,
        lost_found_location=lost_found_location,
        feed_lost_found_location=lost_found_location)
    specie.save()
    breed = SpecieBreed(specie=specie, name='One Breed')
    breed.save()
    farm_line = SpecieFarmLine()
    farm_line.specie = specie
    farm_line.farm = warehouse
    farm_line.event_order_sequence = event_order_sequence
    farm_line.has_male = True
    farm_line.male_sequence = male_sequence
    farm_line.semen_lot_sequence = semen_lot_sequence
    farm_line.dose_lot_sequence = semen_dose_lot_sequence
    farm_line.has_female = True
    farm_line.female_sequence = female_sequence
    farm_line.has_individual = True
    farm_line.individual_sequence = individual_sequence
    farm_line.has_group = True
    farm_line.group_sequence = group_sequence
    farm_line.save()
    return specie, breed, {
        'group': group_product,
        'individual': individual_product,
        'female': female_product,
        'male': male_product,
        'semen': semen_product,
        }

def create_users(company):
    Group = Model.get('res.group')
    User = Model.get('res.user')

    farm_group, = Group.find([('name', '=', 'Farm')])
    stock_group, = Group.find([('name', '=', 'Stock')])
    individual_user = User()
    individual_user.name = 'Individuals'
    individual_user.login = 'individuals'
    individual_group, = Group.find([('name', '=', 'Farm / Individuals')])
    individual_user.groups.append(individual_group)
    individual_user.groups.append(farm_group)
    individual_user.groups.append(stock_group)
    individual_user.save()
    group_user = User()
    group_user.name = 'Groups'
    group_user.login = 'groups'
    group_group, = Group.find([('name', '=', 'Farm / Groups')])
    group_user.groups.append(group_group)
    group_user.groups.append(Group(farm_group.id))
    group_user.groups.append(Group(stock_group.id))
    group_user.save()
    female_user = User()
    female_user.name = 'Females'
    female_user.login = 'females'
    female_group, = Group.find([('name', '=', 'Farm / Females')])
    female_user.groups.append(female_group)
    female_user.groups.append(Group(farm_group.id))
    female_user.groups.append(Group(stock_group.id))
    female_user.save()
    male_user = User()
    male_user.name = 'Males'
    male_user.login = 'males'
    male_group, = Group.find([('name', '=', 'Farm / Females')])
    male_user.groups.append(male_group)
    male_user.groups.append(Group(farm_group.id))
    male_user.groups.append(Group(stock_group.id))
    male_user.save()
    return {
        'individual': individual_user,
        'group': group_user,
        'female': female_user,
        'male': male_user,
        }
