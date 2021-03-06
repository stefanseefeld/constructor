The `artefact` class
====================

.. currentmodule:: faber.artefact

An artefact is generated by an action. In a fabscript artefacts are typically
created by invoking a `rule` that declares how to generate an artefact using
an action. The artefact class may be subclassed, to change its behaviour (e.g.
how it reports its update) or to allow it to have additional internal state
(e.g., for composite artefacts that require intermediate steps to be built).

.. _a_attributes:

attributes
----------

.. py:data:: intermediate

.. py:data:: notfile

   `notfile` artefacts do not have corresponding files in the file system,
   thus whether or not they require being updated cannot be determined from
   a file's timestamp.

.. py:data:: always

   Never consider this artefact up to date.

Constructor
-----------

.. method:: artefact(name, attrs=0, features=(), use=(), condition=None)

   Construct an artefact.

   :parameter string name: the artefact's name
   :kwarg int attrs: :ref:`a_attributes`
   :kwarg features: Set of artefact-specific features to add.
   :kwarg use: Set of features to be exported to other artefacts using this as a source.
   :kwarg condition: Condition in case this artefact is conditional.
				   

Call operator
-------------

.. automethod:: faber.artefact.artefact.__call__

Attributes
----------

.. attribute:: name

   The artefact's name, as set in the constructor.

.. attribute:: qname

   The artefact's qualified name, i.e. the name prefixed with the (qualified) name of the module it was defined in.

.. attribute:: filename

   The artefact's filename, if the artefact is a file.

Methods
-------

.. automethod:: artefact.__status__
		   

Examples
--------

::

   a = rule('a', recipe=fileutils.touch)
