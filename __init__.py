#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool

from .animal import *
from .animal_group import *
from .events import *
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
        Menu,
        ActWindow,
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
        AnimalGroup,
        AnimalGroupTag,
        AnimalGroupWeight,
        Location,
        LocationSiloLocation,
        LotAnimal,
        LotAnimalGroup,
        Lot,
        User,
        UserLocation,
        EventOrder,
        AbstractEvent,
        MoveEvent,
        FeedInventory,
        FeedInventoryLocation,
        FeedProvisionalInventory,
        FeedProvisionalInventoryLocation,
        FeedInventoryLine,
        FeedLocationDate,
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
