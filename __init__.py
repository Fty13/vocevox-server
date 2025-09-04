# -*- coding: utf-8 -*-

# This file is part of Japanese Furigana <https://github.com/obynio/anki-japanese-furigana>.
#
# Japanese Furigana is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with Japanese Furigana.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
from typing import Any, Dict, List

from aqt.utils import tooltip, showWarning, showText
from aqt.operations import QueryOp
from aqt.qt import *
from aqt import gui_hooks

from aqt import mw

from anki.notes import Note
from anki.notes import NoteId

from . import reading
from .config import Config
from .selection import Selection
from .utils import removeFurigana
from .bulk import bulkGenerate, generateFurigana

# --- Globals ---
mecab = reading.MecabController()
config = Config(__name__)
auto_scan_timer = None

# --- Core Scan and Process Logic ---

def is_field_effectively_empty(field_content: str) -> bool:
    if not field_content:
        return True
    text_only = re.sub('<[^<]+?>', '', field_content)
    return not text_only.strip().replace('&nbsp;', '')

def find_notes_to_process(rules: List[Dict]) -> List[NoteId]:
    notes_to_process_ids = set()
    for rule in rules:
        rule_deck_name = rule.get("deckName")
        if not rule_deck_name:
            continue
        
        query = f'deck:"{rule_deck_name}"'
        nids = mw.col.find_notes(query)
        
        for nid in nids:
            note = mw.col.get_note(NoteId(nid))
            for pair in rule.get("fieldPairs", []):
                src_field = pair.get("source")
                dest_field = pair.get("destination")

                if src_field in note and dest_field in note and note[src_field]:
                    source_text = note[src_field]
                    destination_text = note[dest_field]
                    
                    if is_field_effectively_empty(destination_text) or source_text == destination_text:
                        notes_to_process_ids.add(note.id)
                        break 
                        
    return list(notes_to_process_ids)

def run_furigana_scan(is_manual: bool = False):
    scan_config = config.getAutoGenerateConfig()
    if not scan_config.get("enabled", False) and not is_manual:
        return

    rules = scan_config.get("rules", [])
    if not rules:
        if is_manual:
            tooltip("No rules configured. Please set up rules in 'Automatic Furigana...' options.")
        return

    if is_manual:
        tooltip("Starting scan for notes needing furigana...")

    notes_to_process_ids = find_notes_to_process(rules)

    if not notes_to_process_ids:
        if is_manual:
            tooltip("Scan complete. No notes needed furigana generation.")
        return

    if is_manual:
        msg = f"Found {len(notes_to_process_ids)} note(s) to process. Generating furigana..."
        showText(msg, title="Furigana Scan Results")

    def do_update(col, nids):
        notes_modified_count = 0
        for nid in nids:
            note = col.get_note(NoteId(nid))
            note_was_modified = False
            for rule in rules:
                rule_deck_name = rule.get("deckName")
                if not note.cards(): continue
                deck = col.decks.get(note.cards()[0].did)
                if not deck: continue
                deck_name = deck['name']

                if deck_name == rule_deck_name or deck_name.startswith(rule_deck_name + '::'):
                    for pair in rule.get("fieldPairs", []):
                        src_field = pair.get("source")
                        dest_field = pair.get("destination")

                        if src_field in note and dest_field in note and note[src_field]:
                            source_text = note[src_field]
                            destination_text = note[dest_field]
                            
                            if is_field_effectively_empty(destination_text) or source_text == destination_text:
                                generated_text = generateFurigana(source_text, config.getIgnoreNumbers(), config.getUseRubyTags())
                                if generated_text != destination_text:
                                    note[dest_field] = generated_text
                                    note_was_modified = True
            if note_was_modified:
                notes_modified_count += 1
                note.flush()
        return notes_modified_count

    def on_done(count: int):
        if count > 0:
            if is_manual or not scan_config.get("hideNotifications", False):
                tooltip(f"Successfully generated furigana for {count} note(s).")

    QueryOp(parent=mw, op=lambda col: do_update(col, notes_to_process_ids), success=on_done).run_in_background()


# --- Configuration Dialogs ---

class AutoGenerateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Automatic Furigana Generation")
        self.setMinimumSize(600, 500)
        self.rules_layout: QVBoxLayout = None
        self.all_decks = sorted(mw.col.decks.all_names())
        self.all_fields = self._get_all_field_names()
        self._setup_ui()
        self._load_config()

    def _get_all_field_names(self) -> List[str]:
        all_fields = set()
        for m in mw.col.models.all():
            for f in m["flds"]:
                all_fields.add(f["name"])
        return sorted(list(all_fields))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        options_layout = QHBoxLayout()
        self.enabled_checkbox = QCheckBox("Enable automatic background scan")
        options_layout.addWidget(self.enabled_checkbox)
        options_layout.addStretch()
        options_layout.addWidget(QLabel("Scan interval (seconds):"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(5)
        self.interval_spinbox.setMaximum(600)
        options_layout.addWidget(self.interval_spinbox)
        main_layout.addLayout(options_layout)

        self.hide_notifications_checkbox = QCheckBox("Hide background scan notifications")
        main_layout.addWidget(self.hide_notifications_checkbox)

        rules_group = QGroupBox("Configuration Rules")
        rules_group_layout = QVBoxLayout(rules_group)
        main_layout.addWidget(rules_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        rules_group_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        self.rules_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)

        add_rule_button = QPushButton("Add Rule for a Deck")
        add_rule_button.clicked.connect(lambda: self._add_rule())
        rules_group_layout.addWidget(add_rule_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _add_rule(self, rule_config: Dict = None):
        rule_config = rule_config or {}
        rule_group = QGroupBox("Rule")
        rule_group.setStyleSheet("QGroupBox { border: 1px solid gray; border-radius: 5px; margin-top: 1ex; }")
        self.rules_layout.addWidget(rule_group)
        
        rule_content_layout = QVBoxLayout(rule_group)

        deck_row = QHBoxLayout()
        deck_combo = QComboBox()
        deck_combo.addItems(self.all_decks)
        if rule_config.get("deckName"):
            deck_combo.setCurrentText(rule_config.get("deckName"))
        deck_row.addWidget(QLabel("Scan Deck (and sub-decks):"))
        deck_row.addWidget(deck_combo, 1)
        remove_rule_button = QPushButton("Remove Rule")
        deck_row.addWidget(remove_rule_button)
        
        field_pairs_layout = QVBoxLayout()

        add_pair_button = QPushButton("Add Source/Destination Pair")
        
        rule_content_layout.addLayout(deck_row)
        rule_content_layout.addLayout(field_pairs_layout)
        rule_content_layout.addWidget(add_pair_button, 0, Qt.AlignmentFlag.AlignRight)

        remove_rule_button.clicked.connect(lambda checked, rg=rule_group: rg.deleteLater())
        add_pair_button.clicked.connect(lambda: self._add_field_pair(field_pairs_layout))
        
        # Use fieldPairs from config, not a mix of source/destination
        pairs = rule_config.get("fieldPairs", [])
        if not pairs:
            # If no pairs are defined, add one empty one to start
            self._add_field_pair(field_pairs_layout)
        else:
            for pair in pairs:
                self._add_field_pair(field_pairs_layout, pair)

    def _add_field_pair(self, layout: QVBoxLayout, pair_config: Dict = None):
        pair_config = pair_config or {}
        pair_layout = QHBoxLayout()
        
        source_combo = QComboBox()
        source_combo.addItems(self.all_fields)
        if pair_config.get("source"):
             source_combo.setCurrentText(pair_config.get("source"))
        
        dest_combo = QComboBox()
        dest_combo.addItems(self.all_fields)
        if pair_config.get("destination"):
             dest_combo.setCurrentText(pair_config.get("destination"))

        remove_pair_button = QPushButton("Remove")
        
        pair_layout.addWidget(QLabel("Source:"))
        pair_layout.addWidget(source_combo)
        pair_layout.addWidget(QLabel("Destination:"))
        pair_layout.addWidget(dest_combo)
        pair_layout.addWidget(remove_pair_button)

        layout.addLayout(pair_layout)
        remove_pair_button.clicked.connect(lambda: self._remove_widget_and_layout(pair_layout))

    def _remove_widget_and_layout(self, layout: QLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        layout.deleteLater()

    def _load_config(self):
        auto_gen_config = config.getAutoGenerateConfig()
        self.enabled_checkbox.setChecked(auto_gen_config.get("enabled", False))
        self.interval_spinbox.setValue(auto_gen_config.get("scanIntervalSeconds", 30))
        self.hide_notifications_checkbox.setChecked(auto_gen_config.get("hideNotifications", False))
        for rule in auto_gen_config.get("rules", []):
            self._add_rule(rule)

    def get_config(self) -> Dict:
        final_config = {
            "enabled": self.enabled_checkbox.isChecked(),
            "scanIntervalSeconds": self.interval_spinbox.value(),
            "hideNotifications": self.hide_notifications_checkbox.isChecked(),
            "rules": []
        }
        
        for i in range(self.rules_layout.count()):
            rule_group_box = self.rules_layout.itemAt(i).widget()
            if not isinstance(rule_group_box, QGroupBox):
                continue
            
            rule_content_layout = rule_group_box.layout()

            deck_row_layout = rule_content_layout.itemAt(0).layout()
            deck_combo = deck_row_layout.itemAt(1).widget()
            
            rule_data = {"deckName": deck_combo.currentText(), "fieldPairs": []}
            
            field_pairs_layout = rule_content_layout.itemAt(1).layout()
            for j in range(field_pairs_layout.count()):
                pair_layout_item = field_pairs_layout.itemAt(j)
                if pair_layout_item:
                    pair_layout = pair_layout_item.layout()
                    if pair_layout:
                        source_combo = pair_layout.itemAt(1).widget()
                        dest_combo = pair_layout.itemAt(3).widget()
                        rule_data["fieldPairs"].append({
                            "source": source_combo.currentText(),
                            "destination": dest_combo.currentText()
                        })
            final_config["rules"].append(rule_data)
            
        return final_config

def onShowAutoConfig():
    dialog = AutoGenerateDialog(mw)
    if dialog.exec():
        new_config = dialog.get_config()
        config.setAutoGenerateConfig(new_config)
        setup_auto_scanner()

def setupGuiMenu():
    useRubyTags = QAction("Use ruby tags", mw, checkable=True, checked=config.getUseRubyTags())
    useRubyTags.toggled.connect(config.setUseRubyTags)
    ignoreNumbers = QAction("Ignore numbers", mw, checkable=True, checked=config.getIgnoreNumbers())
    ignoreNumbers.toggled.connect(config.setIgnoreNumbers)
    
    mw.form.menuTools.addSeparator()
    mw.form.menuTools.addAction(useRubyTags)
    mw.form.menuTools.addAction(ignoreNumbers)
    
    mw.form.menuTools.addSeparator()
    manual_scan_action = QAction("Scan Decks for Furigana", mw)
    manual_scan_action.triggered.connect(lambda: run_furigana_scan(is_manual=True))
    mw.form.menuTools.addAction(manual_scan_action)

    autoGenAction = QAction("Automatic Furigana...", mw)
    autoGenAction.triggered.connect(onShowAutoConfig)
    mw.form.menuTools.addAction(autoGenAction)

def addButtons(buttons, editor):
    return buttons + [
        editor.addButton(
            icon=os.path.join(os.path.dirname(__file__), "icons", "add_furigana.svg"),
            cmd="generateFurigana",
            tip="Add furigana",
            func=lambda ed=editor: doIt(ed, onGenerateFurigana),
            keys=config.getKeyboardShortcut("add_furigana"),
        ),
        editor.addButton(
            icon=os.path.join(os.path.dirname(__file__), "icons", "del_furigana.svg"),
            cmd="deleteFurigana",
            tip="Delete furigana",
            func=lambda ed=editor: doIt(ed, onDeleteFurigana),
            keys=config.getKeyboardShortcut("del_furigana"),
        ),
    ]

def addBrowserButtons(browser):
    menu = browser.form.menuEdit
    menu.addSeparator()
    a = menu.addAction('Bulk Generate Furigana')
    a.triggered.connect(lambda _, b=browser: onBulkUpdate(b))

def doIt(editor, action):
    Selection(editor, lambda s: action(s, editor))

def onGenerateFurigana(s, editor):
    html = s.selected
    html_with_furigana = generateFurigana(html, config.getIgnoreNumbers(), config.getUseRubyTags())
    if html_with_furigana == html:
        tooltip("Nothing to generate!")
    else:
        s.modify(html_with_furigana)

def onDeleteFurigana(s, editor):
    stripped = removeFurigana(s.selected)
    if stripped == s.selected:
        tooltip("No furigana found to delete")
    else:
        s.modify(stripped)

def onBulkUpdate(browser):
    pass

def setup_auto_scanner():
    global auto_scan_timer
    scan_config = config.getAutoGenerateConfig()
    
    if not auto_scan_timer:
        auto_scan_timer = QTimer(mw)
        auto_scan_timer.setSingleShot(False)
        auto_scan_timer.timeout.connect(lambda: run_furigana_scan(is_manual=False))
        
    if scan_config.get("enabled", False):
        interval_seconds = scan_config.get("scanIntervalSeconds", 120)
        interval_ms = interval_seconds * 1000
        if not auto_scan_timer.isActive() or auto_scan_timer.interval() != interval_ms:
            auto_scan_timer.start(interval_ms)
            if not scan_config.get("hideNotifications", False):
                tooltip(f"Automatic furigana scan enabled (runs every {interval_seconds} seconds).")
    else:
        if auto_scan_timer.isActive():
            auto_scan_timer.stop()
            if not scan_config.get("hideNotifications", False):
                tooltip("Automatic furigana scan disabled.")

def on_main_window_did_init():
    setupGuiMenu()
    setup_auto_scanner()

gui_hooks.main_window_did_init.append(on_main_window_did_init)
gui_hooks.editor_did_init_buttons.append(addButtons)
gui_hooks.browser_menus_did_init.append(addBrowserButtons)
