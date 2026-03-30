{{ objname | escape | underline}}

.. currentmodule:: {{ module }}

{% if objtype == 'class' %}
.. autoclass:: {{ objname }}
   :members:
   :show-inheritance:
   :special-members: __call__, __add__, __mul__
{% else %}
.. autofunction:: {{ objname }}
{% endif %}
