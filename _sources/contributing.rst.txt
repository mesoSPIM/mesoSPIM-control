Contributing
============

We welcome contributions of all kinds — bug reports, feature requests,
documentation improvements, and pull requests!

Branch strategy
---------------

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - Branch
     - Purpose
   * - ``master``
     - Stable, always-deployable code, tested on real hardware.
   * - ``release/candidate-py12``
     - Integration branch for new features and bugfixes.

We follow the
`GitHub Flow <https://guides.github.com/introduction/flow/>`_.
We recommend **GitHub Desktop** for branch management.

Contributing a new feature
--------------------------

0. **Fork** the repository on GitHub.
1. Check out ``release/candidate-py12`` and verify it works in demo mode and
   on your actual mesoSPIM.
2. Create a local branch from ``release/candidate-py12``::

      git checkout -b dev-my-feature

3. Make your changes, write tests (see below), and commit.
4. Open a **pull request** back to ``release/candidate-py12``.  We review
   and merge it.
5. Once merged and stable, your branch can be deleted.

Stable releases from ``release/candidate-py12`` are periodically merged into
``master`` after testing on several physical setups.

Reporting bugs
--------------

Please file a GitHub `issue <https://github.com/mesoSPIM/mesoSPIM-control/issues>`_
with:

* mesoSPIM-control version (or git commit hash)
* Python version and OS
* Relevant section of the log file from ``mesoSPIM/log/``
* Steps to reproduce

Testing
-------

Hardware-in-the-loop testing is hard to automate, so we rely on a two-step
approach:

1. **Demo mode** — run the software with ``demo_config.py`` (no physical
   hardware).
2. **Real hardware** — test on an actual mesoSPIM setup.

Unit tests live in ``mesoSPIM/test/``.  Run them with::

   pytest mesoSPIM/test/

Writing tests *before* implementing a feature (test-driven development) is
encouraged but not required.

Sharing ideas
-------------

Have a feature idea or want to discuss the project?  Head to the
`image.sc forum <https://forum.image.sc/tag/mesospim>`_ or open a GitHub
discussion.

.. include:: ../../CONTRIBUTING.md
   :parser: myst_parser.sphinx_
