Coding conventions for the mesoSPIM project
===========================================

Naming conventions
------------------
* **Classes reimplementing PyQt5 functionalities** (e.g. QTableViews, QAbstractItemModel)
  and methods follow the CamelCase convention of PyQt:

  * buttons follow the same convention (e.g. ``QPushButtons, QLabel, QComboBox, ...``),
    which means that there are widgets such as: ``SnapButton, LiveButton, StackButton``
  * indicators are called ``XPositionIndicator``

* Method, function and variables names of **non-PyQt-reimplementations** are:
  in ``lowercase_with_underscores``
* major mesoSPIM classes are called ``mesoSPIM_...``, rest in CamelCase
* setters are called ``set_...``
* getters are called ``get_...``
* signals are called ``sig_...``
* mutexes are caled ``mutex_``
* Private methods and properties start with ``__double_underscore``
* “Protected” methods and properties start with ``_single_underscore``
