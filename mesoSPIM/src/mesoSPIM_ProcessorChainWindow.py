"""
Processor Chain Window - UI for configuring the image processor chain
"""

from PyQt5 import QtWidgets, QtCore
import logging

logger = logging.getLogger(__name__)


class ProcessorChainWindow(QtWidgets.QDialog):
    """
    Dialog window for configuring the image processor chain.
    
    Allows users to add/remove processors, enable/disable them, and reorder.
    """
    
    def __init__(self, parent=None, processor_chain=None):
        super().__init__(parent)
        self.parent = parent
        self.processor_chain = processor_chain
        
        self.setWindowTitle("Image Processor Chain")
        self.setMinimumSize(600, 400)
        
        self._setup_ui()
        self._populate_available_processors()
        self._populate_chain()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QtWidgets.QVBoxLayout()
        
        title = QtWidgets.QLabel("<h3>Image Processor Chain</h3>")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        desc = QtWidgets.QLabel("Add processors to apply to live view and saved images:")
        layout.addWidget(desc)
        
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        available_box = QtWidgets.QGroupBox("Available Processors")
        available_layout = QtWidgets.QVBoxLayout()
        self.available_list = QtWidgets.QListWidget()
        self.available_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        available_layout.addWidget(self.available_list)
        
        available_btn_layout = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add →")
        self.add_btn.clicked.connect(self._add_processor)
        available_btn_layout.addWidget(self.add_btn)
        available_layout.addLayout(available_btn_layout)
        
        available_box.setLayout(available_layout)
        splitter.addWidget(available_box)
        
        chain_box = QtWidgets.QGroupBox("Active Chain")
        chain_layout = QtWidgets.QVBoxLayout()
        self.chain_list = QtWidgets.QListWidget()
        self.chain_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.chain_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        chain_layout.addWidget(self.chain_list)
        
        chain_btn_layout = QtWidgets.QHBoxLayout()
        self.remove_btn = QtWidgets.QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_processor)
        self.up_btn = QtWidgets.QPushButton("↑ Up")
        self.up_btn.clicked.connect(self._move_up)
        self.down_btn = QtWidgets.QPushButton("↓ Down")
        self.down_btn.clicked.connect(self._move_down)
        
        chain_btn_layout.addWidget(self.remove_btn)
        chain_btn_layout.addWidget(self.up_btn)
        chain_btn_layout.addWidget(self.down_btn)
        chain_layout.addLayout(chain_btn_layout)
        
        chain_box.setLayout(chain_layout)
        splitter.addWidget(chain_box)
        
        splitter.setSizes([250, 350])
        layout.addWidget(splitter)
        
        status_layout = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel()
        status_layout.addWidget(self.status_label)
        layout.addLayout(status_layout)
        
        button_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_changes)
        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addStretch()
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _populate_available_processors(self):
        """Populate the list of available processors."""
        self.available_list.clear()
        
        if self.processor_chain is None:
            return
        
        available = self.processor_chain.available_processors
        chain_names = {p['name'] for p in self.processor_chain.chain}
        
        for proc in available:
            if proc['name'] not in chain_names:
                item = QtWidgets.QListWidgetItem(proc['name'])
                item.setToolTip(proc.get('description', ''))
                self.available_list.addItem(item)
    
    def _populate_chain(self):
        """Populate the list of active processors in the chain."""
        self.chain_list.clear()
        
        if self.processor_chain is None:
            return
        
        for proc in self.processor_chain.chain:
            name = proc['name']
            enabled = proc['enabled']
            
            item = QtWidgets.QListWidgetItem(name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked)
            
            desc = proc.get('instance', None)
            if desc:
                desc = desc.description() if hasattr(desc, 'description') else ''
                item.setToolTip(desc)
            
            self.chain_list.addItem(item)
        
        self._update_status()
    
    def _add_processor(self):
        """Add a processor to the chain."""
        current_item = self.available_list.currentItem()
        if current_item is None:
            return
        
        name = current_item.text()
        
        if self.processor_chain:
            self.processor_chain.add_processor(name, enabled=True)
        
        self._populate_available_processors()
        self._populate_chain()
    
    def _remove_processor(self):
        """Remove a processor from the chain."""
        current_row = self.chain_list.currentRow()
        if current_row < 0:
            return
        
        if self.processor_chain:
            self.processor_chain.remove_processor(current_row)
        
        self._populate_available_processors()
        self._populate_chain()
    
    def _move_up(self):
        """Move a processor up in the chain."""
        current_row = self.chain_list.currentRow()
        if current_row <= 0:
            return
        
        if self.processor_chain:
            self.processor_chain.move_processor(current_row, current_row - 1)
        
        self._populate_chain()
        self.chain_list.setCurrentRow(current_row - 1)
    
    def _move_down(self):
        """Move a processor down in the chain."""
        current_row = self.chain_list.currentRow()
        if current_row < 0 or current_row >= self.chain_list.count() - 1:
            return
        
        if self.processor_chain:
            self.processor_chain.move_processor(current_row, current_row + 1)
        
        self._populate_chain()
        self.chain_list.setCurrentRow(current_row + 1)
    
    def _apply_changes(self):
        """Apply the enabled/disabled state changes."""
        if self.processor_chain is None:
            return
        
        for i in range(self.chain_list.count()):
            item = self.chain_list.item(i)
            enabled = item.checkState() == QtCore.Qt.Checked
            
            if i < len(self.processor_chain.chain):
                if enabled:
                    self.processor_chain.enable_processor(i)
                else:
                    self.processor_chain.disable_processor(i)
        
        self._update_status()
        logger.info("Processor chain configuration applied")
    
    def _update_status(self):
        """Update the status label."""
        if self.processor_chain is None:
            self.status_label.setText("No processor chain available")
            return
        
        chain = self.processor_chain.chain
        enabled_count = sum(1 for p in chain if p['enabled'])
        
        if enabled_count > 0:
            self.status_label.setText(f"Active: {enabled_count} of {len(chain)} processors enabled")
        else:
            self.status_label.setText("No processors enabled (images will pass through unchanged)")
