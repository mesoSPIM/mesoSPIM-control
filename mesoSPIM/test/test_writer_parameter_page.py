"""
The writer parameter page of the filename wizard.

Run from the mesoSPIM/ directory:  python -m pytest test/test_writer_parameter_page.py -q

Needs PyQt5 but no hardware: the page runs offscreen.
"""
import os
import sys
import types
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from PyQt5 import QtWidgets

from mesoSPIM.src.utils.filename_wizard import FilenameWizard, WriterParameterPage

# Module level, and kept alive: a QApplication that gets garbage collected takes the
# interpreter down with it.
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FakeWriter:
    """Stands in for the OME-Zarr plugins: same wizard_parameters() contract, no zarr import."""
    @classmethod
    def name(cls):
        return 'OME_Zarr_Writer'

    @classmethod
    def wizard_parameters(cls):
        return {'ome_version': ('0.5', ''), 'generate_multiscales': (True, ''),
                'compression': ('zstd', ''), 'compression_level': (5, ''),
                'shards': ((64, 6000, 6000), ''), 'write_cache': (None, '')}


@pytest.fixture
def page():
    class FakeWizard(QtWidgets.QWizard):
        cfg = types.ModuleType('cfg')
        selected_writer = {'name': 'OME_Zarr_Writer', 'writer_class': FakeWriter}
        num_of_pages = 4
        writer_parameters = None
        apply_writer_parameters = FilenameWizard.apply_writer_parameters

    wizard = FakeWizard()
    wizard.cfg.OME_Zarr_Writer = {'compression': 'lz4'}   # a config file entry
    p = WriterParameterPage(wizard)
    p.initializePage()
    return p


def test_page_shows_config_values_over_plugin_defaults(page):
    assert set(page.editors) == set(FakeWriter.wizard_parameters())
    assert page.editors['compression'].text() == 'lz4'          # from the config
    assert page.editors['shards'].text() == '(64, 6000, 6000)'  # from the plugin
    assert page.editors['ome_version'].text() == '0.5'          # a string, shown unquoted
    assert page.editors['generate_multiscales'].isChecked()
    assert page.editors['compression_level'].value() == 5


def test_edits_reach_the_config_attribute_the_writer_reads(page):
    page.editors['shards'].setText('(32, 2048, 2048)')
    page.editors['write_cache'].setText(r'D:\scratch')   # a path, not a Python literal
    page.editors['compression'].setText('None')          # None must survive as None
    page.editors['generate_multiscales'].setChecked(False)
    page.editors['compression_level'].setValue(9)
    page.validatePage()
    page.parent.apply_writer_parameters()

    cfg_entry = page.parent.cfg.OME_Zarr_Writer
    assert cfg_entry['shards'] == (32, 2048, 2048)
    assert cfg_entry['write_cache'] == r'D:\scratch'
    assert cfg_entry['compression'] is None
    assert cfg_entry['generate_multiscales'] is False
    assert cfg_entry['compression_level'] == 9
    assert cfg_entry['ome_version'] == '0.5'             # untouched rows are written too
