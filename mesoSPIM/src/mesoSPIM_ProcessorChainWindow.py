"""Processor Chain Window - UI for configuring the image processor chain."""

import logging

from PyQt5 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class ProcessorChainWindow(QtWidgets.QDialog):
    """
    Dialog window for configuring the image processor chain.
    
    Allows users to add/remove processors, enable/disable them, and reorder.
    """
    
    def __init__(self, parent=None, processor_chain=None, config_filepath=None):
        super().__init__(parent)
        self.parent = parent
        self.processor_chain = processor_chain
        self.config_filepath = config_filepath
        self.processor_info = {}
        self._working_chain = []
        self._entry_counter = 0
        self._current_entry_id = None
        self._parameter_widgets = {}
        self._live_parameter_changes_pending_save = False

        self.setWindowTitle("Image Processor Chain")
        self.setMinimumSize(860, 520)

        self._setup_ui()
        self.refresh_from_chain()
    
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
        self.chain_list.currentItemChanged.connect(self._on_chain_selection_changed)
        self.chain_list.itemChanged.connect(self._on_chain_item_changed)
        self.chain_list.model().rowsMoved.connect(self._on_chain_rows_moved)
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

        params_box = QtWidgets.QGroupBox("Selected Processor Parameters")
        params_layout = QtWidgets.QVBoxLayout()
        self.parameter_intro_label = QtWidgets.QLabel("Select a processor in the active chain to review and edit its parameters.")
        self.parameter_intro_label.setWordWrap(True)
        params_layout.addWidget(self.parameter_intro_label)

        self.auto_apply_params_checkbox = QtWidgets.QCheckBox("Auto-apply parameter changes")
        self.auto_apply_params_checkbox.setToolTip(
            "Apply parameter edits to the live processor chain immediately. "
            "Click Apply to save them to the config file."
        )
        self.auto_apply_params_checkbox.toggled.connect(self._on_auto_apply_toggled)
        params_layout.addWidget(self.auto_apply_params_checkbox)

        self.auto_apply_hint_label = QtWidgets.QLabel("Parameter edits stay staged until you click Apply.")
        self.auto_apply_hint_label.setWordWrap(True)
        params_layout.addWidget(self.auto_apply_hint_label)

        self.parameter_scroll_area = QtWidgets.QScrollArea()
        self.parameter_scroll_area.setWidgetResizable(True)
        self.parameter_scroll_widget = QtWidgets.QWidget()
        self.parameter_form_layout = QtWidgets.QFormLayout()
        self.parameter_form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.parameter_form_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.parameter_scroll_widget.setLayout(self.parameter_form_layout)
        self.parameter_scroll_area.setWidget(self.parameter_scroll_widget)
        params_layout.addWidget(self.parameter_scroll_area)

        self.parameter_message_label = QtWidgets.QLabel("No processor selected")
        self.parameter_message_label.setWordWrap(True)
        self.parameter_message_label.setAlignment(QtCore.Qt.AlignTop)
        params_layout.addWidget(self.parameter_message_label)

        params_box.setLayout(params_layout)
        chain_layout.addWidget(params_box)

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
        
        chain_names = {entry['name'] for entry in self._working_chain}

        for proc in self.processor_chain.available_processors:
            if proc['name'] not in chain_names:
                item = QtWidgets.QListWidgetItem(proc['name'])
                item.setToolTip(proc.get('description', ''))
                self.available_list.addItem(item)

    def _populate_chain(self, selected_entry_id=None):
        """Populate the list of active processors in the chain."""
        self.chain_list.clear()

        if self.processor_chain is None:
            self._clear_parameter_editor("No processor chain available")
            return

        if selected_entry_id is None:
            selected_entry_id = self._current_entry_id

        selected_row = -1
        for row, entry in enumerate(self._working_chain):
            item = QtWidgets.QListWidgetItem(entry['name'])
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if entry['enabled'] else QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, entry['id'])
            item.setToolTip(self._build_item_tooltip(entry))

            self.chain_list.addItem(item)

            if entry['id'] == selected_entry_id:
                selected_row = row

        if selected_row >= 0:
            self.chain_list.setCurrentRow(selected_row)
        elif self.chain_list.count() > 0:
            self.chain_list.setCurrentRow(0)
        else:
            self._clear_parameter_editor("No processors in the active chain")

        self._update_status()
    
    def _add_processor(self):
        """Add a processor to the chain."""
        current_item = self.available_list.currentItem()
        if current_item is None:
            return
        
        name = current_item.text()

        entry = self._create_working_entry(name, enabled=True)
        if entry is None:
            return

        self._working_chain.append(entry)

        self._populate_available_processors()
        self._populate_chain(selected_entry_id=entry['id'])
    
    def _remove_processor(self):
        """Remove a processor from the chain."""
        current_row = self.chain_list.currentRow()
        if current_row < 0:
            return
        
        entry_id = self.chain_list.item(current_row).data(QtCore.Qt.UserRole)
        self._working_chain = [entry for entry in self._working_chain if entry['id'] != entry_id]

        if self._current_entry_id == entry_id:
            self._current_entry_id = None

        self._populate_available_processors()
        self._populate_chain()
    
    def _move_up(self):
        """Move a processor up in the chain."""
        current_row = self.chain_list.currentRow()
        if current_row <= 0:
            return
        
        self._sync_working_chain_order_from_list()
        self._working_chain[current_row - 1], self._working_chain[current_row] = (
            self._working_chain[current_row],
            self._working_chain[current_row - 1],
        )

        self._populate_chain(selected_entry_id=self._working_chain[current_row - 1]['id'])
        self.chain_list.setCurrentRow(current_row - 1)
    
    def _move_down(self):
        """Move a processor down in the chain."""
        current_row = self.chain_list.currentRow()
        if current_row < 0 or current_row >= self.chain_list.count() - 1:
            return
        
        self._sync_working_chain_order_from_list()
        self._working_chain[current_row], self._working_chain[current_row + 1] = (
            self._working_chain[current_row + 1],
            self._working_chain[current_row],
        )

        self._populate_chain(selected_entry_id=self._working_chain[current_row + 1]['id'])
        self.chain_list.setCurrentRow(current_row + 1)

    def _apply_working_chain_to_live_chain(self, save=False):
        """Apply the current working chain to the live processor chain."""
        if self.processor_chain is None:
            return

        self._sync_working_chain_order_from_list()
        config = {
            'processors': [
                {
                    'name': entry['name'],
                    'enabled': entry['enabled'],
                    'config': dict(entry['config']),
                }
                for entry in self._working_chain
            ]
        }
        self.processor_chain.set_config(config)

        if save and self.config_filepath and self.processor_chain:
            self.processor_chain.save_to_file(self.config_filepath)

        if save:
            self._live_parameter_changes_pending_save = False

        self.refresh_from_chain(selected_entry_id=self._current_entry_id)
        self._update_status()
        if save:
            logger.info("Processor chain configuration applied and saved")
        else:
            logger.info("Processor chain configuration applied to live chain")

    def _apply_changes(self):
        """Apply the staged chain changes to the live processor chain and save them."""
        self._apply_working_chain_to_live_chain(save=True)
    
    def _update_status(self):
        """Update the status label."""
        if self.processor_chain is None:
            self.status_label.setText("No processor chain available")
            return

        enabled_count = sum(1 for entry in self._working_chain if entry['enabled'])
        auto_apply_enabled = self.auto_apply_params_checkbox.isChecked()

        if auto_apply_enabled:
            if enabled_count > 0:
                status_text = f"Active: {enabled_count} of {len(self._working_chain)} processors enabled"
            else:
                status_text = "No processors enabled"

            if self._live_parameter_changes_pending_save:
                status_text += " (parameter edits are live; click Apply to save)"
            else:
                status_text += " (parameter edits auto-apply; click Apply to save)"
            self.status_label.setText(status_text)
            return

        if enabled_count > 0:
            self.status_label.setText(f"Active: {enabled_count} of {len(self._working_chain)} processors enabled (pending until Apply)")
        else:
            self.status_label.setText("No processors enabled (pending until Apply)")

    def refresh_from_chain(self, selected_entry_id=None):
        """Reload the dialog working copy from the live processor chain."""
        self._load_processor_metadata()
        self._working_chain = []
        self._current_entry_id = None

        if self.processor_chain is not None:
            for live_index, proc in enumerate(self.processor_chain.chain):
                entry = self._create_working_entry(
                    proc['name'],
                    enabled=proc.get('enabled', True),
                    config=proc.get('instance').get_config() if proc.get('instance') else {},
                    live_index=live_index,
                )
                if entry is not None:
                    self._working_chain.append(entry)

        self._populate_available_processors()
        self._populate_chain(selected_entry_id=selected_entry_id)

    def _load_processor_metadata(self):
        """Cache available processor metadata for UI rendering."""
        self.processor_info = {}
        if self.processor_chain is None:
            return

        for proc in self.processor_chain.available_processors:
            self.processor_info[proc['name']] = proc

    def _create_working_entry(self, name, enabled=True, config=None, live_index=None):
        """Create a local editable processor entry."""
        processor_class = self._get_processor_class(name)
        if processor_class is None:
            logger.warning(f"Processor not found while building UI entry: {name}")
            return None

        if config is None:
            try:
                config = processor_class().get_config()
            except Exception as exc:
                logger.warning(f"Failed to load default config for {name}: {exc}")
                config = {}

        entry = {
            'id': self._entry_counter,
            'live_index': live_index,
            'name': name,
            'enabled': enabled,
            'config': dict(config),
        }
        self._entry_counter += 1
        return entry

    def _get_processor_class(self, name):
        """Return the processor class for a given processor name."""
        info = self.processor_info.get(name, {})
        return info.get('processor_class')

    def _get_parameter_descriptions(self, name):
        """Return editable parameter descriptions for a processor."""
        processor_class = self._get_processor_class(name)
        if processor_class is None or not hasattr(processor_class, 'parameter_descriptions'):
            return {}

        try:
            return processor_class.parameter_descriptions() or {}
        except Exception as exc:
            logger.warning(f"Failed to load parameter descriptions for {name}: {exc}")
            return {}

    def _find_entry_by_id(self, entry_id):
        """Return the working entry with the given id."""
        for entry in self._working_chain:
            if entry['id'] == entry_id:
                return entry
        return None

    def _sync_working_chain_order_from_list(self):
        """Update the local chain order from the current list widget order."""
        if not self._working_chain:
            return

        entry_by_id = {entry['id']: entry for entry in self._working_chain}
        ordered_entries = []
        for row in range(self.chain_list.count()):
            item = self.chain_list.item(row)
            entry_id = item.data(QtCore.Qt.UserRole)
            entry = entry_by_id.get(entry_id)
            if entry is not None:
                entry['enabled'] = item.checkState() == QtCore.Qt.Checked
                ordered_entries.append(entry)

        if len(ordered_entries) == len(self._working_chain):
            self._working_chain = ordered_entries

    def _build_item_tooltip(self, entry):
        """Build the tooltip shown for a chain entry."""
        info = self.processor_info.get(entry['name'], {})
        description = info.get('description', '')
        config_summary = self._format_config_summary(entry.get('config', {}))
        if config_summary:
            return f"{description}\n\nParameters: {config_summary}".strip()
        return description

    def _format_config_summary(self, config):
        """Return a compact summary string for a processor config."""
        if not config:
            return ''
        return ', '.join(f"{key}={value}" for key, value in config.items())

    def _on_chain_selection_changed(self, current, previous):
        """Refresh the parameter pane when the selected processor changes."""
        del previous
        if current is None:
            self._current_entry_id = None
            self._clear_parameter_editor("No processor selected")
            return

        entry_id = current.data(QtCore.Qt.UserRole)
        self._current_entry_id = entry_id
        self._show_parameter_editor(entry_id)

    def _on_chain_item_changed(self, item):
        """Keep the local enabled state in sync with the checklist."""
        if item is None:
            return

        entry = self._find_entry_by_id(item.data(QtCore.Qt.UserRole))
        if entry is None:
            return

        entry['enabled'] = item.checkState() == QtCore.Qt.Checked
        item.setToolTip(self._build_item_tooltip(entry))
        self._update_status()

    def _on_chain_rows_moved(self, *args):
        """Track drag-and-drop reorder operations in the staged working copy."""
        del args
        self._sync_working_chain_order_from_list()

    def _clear_parameter_editor(self, message):
        """Clear all editable parameter widgets and show a message."""
        while self.parameter_form_layout.rowCount() > 0:
            self.parameter_form_layout.removeRow(0)

        self._parameter_widgets = {}
        self.parameter_message_label.setText(message)

    def _on_auto_apply_toggled(self, checked):
        """Refresh status and parameter hint text when auto-apply changes."""
        if checked:
            self.auto_apply_hint_label.setText(
                "Parameter edits affect the live chain immediately. Click Apply to save them."
            )
            entry = self._find_entry_by_id(self._current_entry_id)
            if entry is not None:
                self._apply_entry_config_to_live_chain(entry)
        else:
            self.auto_apply_hint_label.setText(
                "Parameter edits stay staged until you click Apply."
            )
        self._update_status()

    def _apply_entry_config_to_live_chain(self, entry):
        """Apply one entry's config to the corresponding live processor when possible."""
        if self.processor_chain is None or entry is None:
            return False

        live_index = entry.get('live_index')
        if live_index is None:
            self.parameter_message_label.setText(
                "This processor is not in the live chain yet. Click Apply to add it and save its parameters."
            )
            return False

        live_chain = self.processor_chain.chain
        if live_index >= len(live_chain):
            return False

        live_entry = live_chain[live_index]
        if live_entry.get('name') != entry['name']:
            logger.warning(
                "Skipping auto-apply for %s because the live chain no longer matches the staged entry",
                entry['name'],
            )
            return False

        if self.processor_chain.configure_processor(live_index, dict(entry['config'])):
            self._live_parameter_changes_pending_save = True
            return True
        return False

    def _show_parameter_editor(self, entry_id):
        """Build the parameter editor for the selected staged processor entry."""
        entry = self._find_entry_by_id(entry_id)
        if entry is None:
            self._clear_parameter_editor("No processor selected")
            return

        specs = self._get_parameter_descriptions(entry['name'])
        inferred = False
        if not specs and entry.get('config'):
            specs = self._infer_parameter_descriptions(entry)
            inferred = True
        self._clear_parameter_editor("")

        if not specs:
            self.parameter_message_label.setText("This processor has no configurable parameters.")
            return

        if inferred:
            self.parameter_message_label.setText("Using generic controls inferred from the current config for this processor.")
        else:
            self.parameter_message_label.setText("")
        self._parameter_widgets = {}

        for param_name, spec in specs.items():
            widget = self._create_parameter_widget(entry, param_name, spec)
            if widget is None:
                continue

            description = spec.get('description', '')
            label_text = param_name if not description else f"{param_name} - {description}"
            self.parameter_form_layout.addRow(label_text, widget)
            self._parameter_widgets[param_name] = widget

    def _create_parameter_widget(self, entry, param_name, spec):
        """Create a typed editor widget for a processor parameter."""
        param_type = spec.get('type', 'str')
        current_value = entry['config'].get(param_name, spec.get('default'))
        choices = spec.get('choices')

        if choices:
            widget = QtWidgets.QComboBox()
            for choice in choices:
                widget.addItem(str(choice), choice)

            choice_index = widget.findData(current_value)
            if choice_index < 0 and current_value is not None:
                widget.addItem(str(current_value), current_value)
                choice_index = widget.findData(current_value)
            if choice_index >= 0:
                widget.setCurrentIndex(choice_index)
            widget.currentIndexChanged.connect(
                lambda _index, entry_id=entry['id'], name=param_name, control=widget: self._update_entry_config(entry_id, name, control.currentData())
            )
            return widget

        if param_type == 'int':
            widget = QtWidgets.QSpinBox()
            widget.setMinimum(spec.get('min', -2147483648))
            widget.setMaximum(spec.get('max', 2147483647))
            widget.setSingleStep(spec.get('step', 1))
            if current_value is not None:
                widget.setValue(int(current_value))
            widget.valueChanged.connect(
                lambda value, entry_id=entry['id'], name=param_name: self._update_entry_config(entry_id, name, int(value))
            )
            return widget

        if param_type == 'float':
            widget = QtWidgets.QDoubleSpinBox()
            widget.setMinimum(spec.get('min', -1e12))
            widget.setMaximum(spec.get('max', 1e12))
            widget.setSingleStep(spec.get('step', 0.1))
            widget.setDecimals(spec.get('decimals', 3))
            if current_value is not None:
                widget.setValue(float(current_value))
            widget.valueChanged.connect(
                lambda value, entry_id=entry['id'], name=param_name: self._update_entry_config(entry_id, name, float(value))
            )
            return widget

        if param_type == 'bool':
            widget = QtWidgets.QCheckBox()
            widget.setChecked(bool(current_value))
            widget.toggled.connect(
                lambda checked, entry_id=entry['id'], name=param_name: self._update_entry_config(entry_id, name, bool(checked))
            )
            return widget

        widget = QtWidgets.QLineEdit('' if current_value is None else str(current_value))
        widget.textChanged.connect(
            lambda text, entry_id=entry['id'], name=param_name: self._update_entry_config(entry_id, name, text)
        )
        return widget

    def _update_entry_config(self, entry_id, param_name, value):
        """Update the staged config for a processor entry."""
        entry = self._find_entry_by_id(entry_id)
        if entry is None:
            return

        entry['config'][param_name] = value
        for row in range(self.chain_list.count()):
            item = self.chain_list.item(row)
            if item.data(QtCore.Qt.UserRole) == entry_id:
                item.setToolTip(self._build_item_tooltip(entry))
                break

        if self.auto_apply_params_checkbox.isChecked():
            self._apply_entry_config_to_live_chain(entry)
        self._update_status()

    def _infer_parameter_descriptions(self, entry):
        """Infer editable parameter metadata from the current config values."""
        inferred_specs = {}
        for param_name, value in entry.get('config', {}).items():
            if isinstance(value, bool):
                param_type = 'bool'
            elif isinstance(value, int):
                param_type = 'int'
            elif isinstance(value, float):
                param_type = 'float'
            else:
                param_type = 'str'

            inferred_specs[param_name] = {
                'type': param_type,
                'default': value,
                'description': 'Inferred from current processor config.',
            }

        return inferred_specs
