#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool

from .animal import *
from .animal_group import *
from .events import *
from .product import *
from .production import *
from .quality import *
from .specie import *
from .stock import *
from .user import *


def register():
    Pool.register(
        Specie,
        SpecieModel,
        SpecieFarmLine,
        Breed,
        UIMenu,
        ActionActWindow,
        ActionWizard,
        Tag,
        RemovalType,
        RemovalReason,
        FarrowingProblem,
        Animal,
        AnimalTag,
        AnimalWeight,
        Male,
        FemaleCycle,
        Female,
        CreateFemaleStart,
        CreateFemaleLine,
        AnimalGroup,
        AnimalGroupTag,
        AnimalGroupWeight,
        Location,
        LocationSiloLocation,
        LotAnimal,
        LotAnimalGroup,
        Lot,
        LotCostLine,
        User,
        UserLocation,
        Template,
        EventOrder,
        AbstractEvent,
        MoveEvent,
        FeedInventory,
        FeedProvisionalInventory,
        FeedInventoryLocation,
        FeedAnimalLocationDate,
        FeedEvent,
        MedicationEvent,
        TransformationEvent,
        RemovalEvent,
        SemenExtractionEvent,
        SemenExtractionEventQualityTest,
        SemenExtractionDose,
        SemenExtractionDelivery,
        InseminationEvent,
        PregnancyDiagnosisEvent,
        AbortEvent,
        AbortEventFemaleCycle,
        FarrowingEvent,
        FarrowingEventFemaleCycle,
        FarrowingEventAnimalGroup,
        FosterEvent,
        WeaningEvent,
        WeaningEventFemaleCycle,
        Move,
        BOM,
        QualityTest,
        module='farm', type_='model')
    Pool.register(
        CreateFemale,
        module='farm', type_='wizard')
