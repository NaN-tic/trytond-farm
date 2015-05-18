
.. inheritref:: farm/farm:section:gestion_granjas

=======
Granjas
=======


.. inheritref:: farm/farm:section:configuracion

Configuración
~~~~~~~~~~~~~

--------
Especies
--------

La gestión de granjas en Tryton es multiespecie. Cada especie tiene configurado
qué tipo de animales y eventos gestionará, así como una serie de productos,
ubicaciones y secuencias.
Con esta configuración se generan menús específicos para cada especie.

Configuraremos las especies desde el menú |menu_species|

.. TODO Complete

.. |menu_species| tryref:: farm.menu_farm_specie/complete_name

-------
Granjas
-------

.. TODO


-----------------
Tipos de animales
-----------------
Existen 4 tipos de animales según su propósito y los procesos asociados a él:

 * **Hembra**: animal de sexo femenino usado para la reproducción. Se registran
   sus  ciclos reproductivos, que se gestionan con los eventos específicos.

 * **Macho**: animal de sexo masculino usado para obtener semen que se usará
   para  inseminar a las hembras.

 * **Individuo**: animal tratado individualmente sin un propósito aún definido
   o  destinado al engorde o pendiente de sacrificar.
   Normalmente este es un paso intermedio antes de decidir su destino (ser
   usado para la inseminación o reproducción) o cuando una hembra o un macho
   finalizan su vida útil y esperan a ser sacrificados.

 * **Grupo**: grupo de animales que van a ser tratados conjuntamente.
   Normalmente  trabajamos con grupos en dos situaciones: cuando una hembra
   pare,
   que siempre  genera un grupo (después, si hace falta, se pueden ir
   extrayendo los animales  individualmente), y para gestionar los animales
   destinados a engorde, los  cuales normalmente se gestionan por las
   ubicaciones (lo que llamamos  **Crianzas**).

Cada animal o grupo tiene asociado un, y sólo un, Lote. El lote servirá para
la trazabilidad a bajo nivel.

.. Imágenes de Formulario de Individuo (u otro tipo de animal). Todos los
   campos que se ven, excepto el sexo y el propósito, los encontramos en los
   otros tipos de animales.

.. Otra imagen con excepción: pestaña Extracciones de semen. Sólo disponible
   para animales de tipo macho

Estado de la hembra y ciclos de gestación
-----------------------------------------
Una hembra tiene un estado que corresponde a los estados definidos por la NPPC
Production and Financial Standards:

 * **Prospección**: cuando no ha sido inseminada ninguna vez o no ha tenido
   ningún embarazo satisfactorio (han acabado en aborto o con todos los fetos
   muertos).
 * **Inseminada**: desde que se insemina hasta que aborta, pare con todos los
   fetos muertos o hasta que finaliza el ciclo satisfactoriamente con el
   destete.
 * **No inseminada**: desde que finaliza el último ciclo hasta que no se inicia
   uno nuevo con una nueva inseminación.
 * **Eliminada**: cuando muere o nos deshacemos de la hembra.

.. Imagen de gestación de la hembra, mostrar pestaña Ciclos (mostrar formulario
   si es necesario)

Los *Ciclos de gestación* también tienen un estado con los siguientes posibles
valores (según el orden que se van sucediendo):

 * **Inseminada**: desde la primera inseminación hasta que la hembra se
   considera preñada.
 * **Preñada**: cuando es diagnosticada como preñada hasta el parto o aborto.
 * **Lactando**: desde el parto hasta el destete
 * **No inseminada**: cuando el ciclo finaliza. O con un aborto, un parto sin
   ninguna cría viva o después del destete.

Una hembra, si ha sido inseminada alguna vez, tiene un *Ciclo actual*. Como el
estado del ciclo actual es más detallado, normalmente nos fijaremos en éste para
la operativa diaria.
El cambio de estado, tanto de la hembra como de sus ciclos, siempre está
asociado a un evento. Se actualiza cuando el evento se valida.

----------------
Tipos de eventos
----------------
La gestión de granjas se basa en eventos equivalentes a los que encontramos en
el día a día de la granja.
Estos eventos acaban generando registros a bajo nivel (normalmente,
*movimientos de stock*) que mantienen la trazabilidad e integridad de los datos
a bajo nivel de todos los elementos implicados: animales, piensos, medicaciones…
Algunos eventos también generan otro tipo de documentos como Órdenes de
producción o Tests de calidad.

Los eventos tienen un pequeño flujo de trabajo de 3 estados:**Borrador,**
**Validado y Cancelado**. Es cuando se valida que se crean los registros y
documentos relacionados y, cuando corresponde, actualizan el estado de la
hembra.
Un evento validado no se puede cancelar ya que podría dejar incoherencias en el
sistema. En algunos casos podremos hacer un evento inverso para *deshacer* un
evento que, por algún motivo, queremos omitir.

Podemos clasificar los eventos en dos tipos:

 * **Genéricos**: eventos que pueden aplicar a cualquier tipo de animal. No
  están relacionados con su especificidad sino con las necesidades básicas de
  los animales.
 * **Específicos**: eventos que solo aplican a un (o unos) tipo de animal.

Eventos genéricos
-----------------

 * **Movimiento**: mueve un animal, o una cantidad específica de animales de un
   grupo, de una ubicación a otra. Permite registrar el peso en aquél momento,
   información que se asociará a la ficha del animal o grupo. Si se disponen de
   los permisos adecuados también permite introducir un Precio unitario para
   actualizar el valor de aquel animal.
 * **Pienso**: registra el consumo por parte del animal o grupo especificado,
   de la cantidad dada de pienso, desde el silo seleccionado y durante el
   periodo indicado.
 * **Medicación**: como el anterior, pero para registrar cuando se administran
   medicamentos.
 * **Transformación**: permite convertir un animal de un tipo a otro, o unir o
   separar grupos. Las transformaciones más habituales son:

   * Grupo -> animal (macho, hembra o individuo): un individuo se separa del
     grupo  para destinarlo a la reproducción
   * Grupo -> grupo: se unen grupos de animales jóvenes provenientes de
     diferentes madres para crear el grupo con el que se gestionará su crianza.
 * **Eliminación**: registra la muerte de un animal (o animales), pudiendo
   indicar el tipo de muerte y el motivo.

Eventos específicos de machos
-----------------------------

**Extracción de semen**: registra la extracción de semen de un macho y su
procesado hasta convertirlo endosis utilizables en una inseminación.

Eventos específicos de hembras
------------------------------
Todos los eventos específicos de hembras se asocian, de forma automática cuando
el evento es validado, al ciclo actual de la hembra.

 * **Inseminación**: registra la inseminación de una hembra con dosis de semen.
   Si el ciclo actual de la hembra ha finalizado, crea automáticamente uno
   nuevo asociándose a él y asignándolo como ciclo actual de la hembra. El
   ciclo y la hembra pasarán a estar *Inseminada*.
   Normalmente una hembra tiene más de un evento de inseminación por ciclo.
   Sólo el primer evento cambia el estado del ciclo y de la hembra.
 * **Diagnóstico de gestación**: registra el diagnóstico, más o menos formal,
   del estado de la hembra. La hembra se considerará preñada si, no habiendo
   parido, su último evento de diagnóstico es positivo.
 * **Aborto**: registra la interrupción del embarazo cerrando su ciclo actual.
 * **Parto**: registra el parto de la hembra indicando el número de hijos
   muertos y vivos (pudiendo dar más detalles sobre los muertos). Al validarse,
   si el número de vivos es positivo se crea un nuevo grupo de animales para
   los vivos ubicado en el mismo sitio que la hembra.
 * **Adopción**: registra la reasignación de hijos entre madres, normalmente
   para equilibrar entre una madre con una camada grande y otra con una
   especialmente pequeña.
   Estos eventos permiten indicar la otra hembra implicada o no. En caso de que
   se indique se genera automáticamente el evento recíproco, completando así el
   intercambio de unidades entre los grupos de parto de las hembras.
   Si no se especifica la otra hembra, las unidades indicadas se extraen o se
   añaden al grupo de la hembra del evento desde o hacia la *Ubicación*
   *adopciones*  configurada en la especie.
 * **Destete**: registra la separación del grupo de parto de la hembra,
   cerrando  así el ciclo actual de ésta. Normalmente, el grupo de parto ahora
   independiente se juntará con otros grupos para formar una **crianza**.

.. Imagen de orden de trabajo mostrando los diferentes tipos de evento

.. inheritref:: farm/farm:section:configuracion_produccion_pienso

--------------------
Producción de pienso
--------------------

Para obtener el pienso que utilizaremos a un animal debemos producir-lo a
través de sus materias primas.


.. inheritref:: farm/farm:section:producto_pienso

Crear un producto de pienso
---------------------------

.. _create-feed-product:

Un producto de pienso debe ser de |product_type| Bienes y no estar marcado cómo
|consumable|, para poder gestionar sus existencias. Cómo |product_unit|
utilizaremos Kilogramo.

En la pestanya *Lotes* debemos marcar los tipos ubicaciones por las que
queremos que el lote sea obligatorio. Lo normal es marcar todos los tipos para
que el lote siempre sea obligatorio.

.. TODO ¿Precios?

.. |product_unit| field:: product.template/default_uom
.. |product_type| field:: product.template/type
.. |consumable| field:: product.template/consumable

.. inheritref:: farm/farm:paragraph:variante_pienso

La variante, además, deberá tener una *Lista de materiales* en la que los
indicaremos los productos necessarios para producir el pienso. En el apartado
:ref:`Crear una lista de materiales<production-create-bom>` tenemos con más
detalle de cómo debemos hacer-lo.

Crear un animal
~~~~~~~~~~~~~~~

.. TODO

Mover un animal
~~~~~~~~~~~~~~~~

.. TODO

Transformar un animal
~~~~~~~~~~~~~~~~~~~~~

.. TODO


Órdenes de trabajo
~~~~~~~~~~~~~~~~~~

Las órdenes de trabajo de los eventos de granja son una forma rápida de
introducir un mismo tipo de evento para varios animales.
La cabecera tiene los campos compartidos por los diferentes eventos que se van a
crear, y es la misma para todos los tipos.
Los tipos de evento que disponen de orden de trabajo son:

 * Genéricos:

   * Medicación

 * Específicos de hembras:

   * Inseminación
   * Diagnóstico de gestación
   * Aborto
   * Parto
   * Adopción
   * Destete

Una orden de trabajo tiene los mismos estados y flujo de trabajo que los
eventos, ya que lo único que hace es realizar la misma transición de estado para
todos sus eventos.

Producción de pienso
~~~~~~~~~~~~~~~~~~~~

.. inheritref:: farm/farm:paragraph:produccion_pienso

Para la producción de pienso utilizaremos el flujo normal de producciones,
cómo se describe en la sección :ref:`Producir materiales<produce-goods>`. Lo
único que debemos tener en cuenta es utilizar un producto configurado cómo
pieno, tal cómo se explica en
:ref:`Crear un producto de pienso<create-feed-product>`.

