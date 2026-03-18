.. mesoSPIM-control documentation master file

mesoSPIM Control
================

.. image:: _static/mesoSPIM-logo.png
   :alt: mesoSPIM logo
   :align: right
   :width: 120px

.. badges

|doi| |python| |license| |forum|

.. |doi| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.6109315.svg
   :target: https://doi.org/10.5281/zenodo.6109315

.. |python| image:: https://img.shields.io/badge/python-3.12-blue.svg
   :target: https://www.python.org/downloads/release/python-312/

.. |license| image:: https://img.shields.io/badge/License-GPLv3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0

.. |forum| image:: https://img.shields.io/badge/user_forum-image.sc-blue
   :target: https://forum.image.sc/tag/mesospim

**mesoSPIM-control** is the open-source Python/PyQt acquisition software for
`mesoSPIM <http://mesospim.org/>`_ light-sheet microscopes.  It drives all
hardware, manages acquisition protocols, and provides a GUI for multichannel,
multiview, and tiled imaging of large cleared-tissue samples.

.. tip::

   New to mesoSPIM?  Start with the :doc:`getting_started` page to install
   the software and run it in demo mode within minutes.

.. note::

   These docs were initially drafted with AI assistance and may contain
   inaccuracies or gaps.  If you spot an error or something unclear, please
   open an `issue on GitHub <https://github.com/mesoSPIM/mesoSPIM-control/issues>`_
   or post in the `image.sc forum <https://forum.image.sc/tag/mesospim>`_ —
   your feedback is very welcome!

----

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: :octicon:`rocket` Getting Started
      :link: getting_started
      :link-type: doc

      Quick-start guide — clone, install, and launch in demo mode.

   .. grid-item-card:: :octicon:`tools` Installation
      :link: installation
      :link-type: doc

      Full installation instructions, including device drivers.

   .. grid-item-card:: :octicon:`sliders` Configuration
      :link: configuration
      :link-type: doc

      How to write and manage your hardware configuration file.

   .. grid-item-card:: :octicon:`desktop-download` User Guide
      :link: user_guide
      :link-type: doc

      Walk-through of the GUI, acquisition modes, and scripting.

   .. grid-item-card:: :octicon:`cpu` Supported Hardware
      :link: hardware
      :link-type: doc

      Cameras, stages, filter wheels, lasers, and more.

   .. grid-item-card:: :octicon:`history` Changelog
      :link: changelog
      :link-type: doc

      Release notes and version history.

----

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: User documentation

   getting_started
   installation
   configuration
   user_guide
   hardware
   changelog

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Developer documentation

   contributing
   plugins
   api/index

Indices and tables
------------------

* :ref:`modindex`
* :ref:`search`
