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

from aqt.addons import AbortAddonImport
from aqt import mw


def saveMe(func):
    """Decorator to save config to file after a setter is called."""
    def wrapper(self, *args):
        # The first argument to the wrapped function is the instance (self),
        # so we pass the actual arguments from the caller.
        func(self, *args)
        # Use the stored addon package name to write to the correct config file.
        mw.addonManager.writeConfig(self.addon_package, self.data)

    return wrapper


class Config:
    def __init__(self, addon_package: str):
        if mw is None:
            raise AbortAddonImport("No Anki main window?")

        # Store the addon's package name to ensure config is loaded from and
        # saved to the correct location (e.g., addon_folder/config.json)
        self.addon_package = addon_package
        self.data = mw.addonManager.getConfig(self.addon_package)
        
        # Ensure default values exist for new settings without overwriting user's file
        auto_gen_config = self.data.setdefault('autoGenerateConfig', {})
        auto_gen_config.setdefault("enabled", False)
        auto_gen_config.setdefault("scanIntervalSeconds", 30)
        auto_gen_config.setdefault("rules", [])
        
        self.data.setdefault('lastBulkConfig', {
            "deck": "All Decks",
            "noteType": "All Note Types",
            "fieldPairs": [{"source": "Expression", "destination": "Reading"}]
        })
        # Legacy fields for backward compatibility, can be removed later
        self.data.setdefault('useRubyTags', False)
        self.data.setdefault('ignoreNumbers', True)
        self.data.setdefault('keyboardShortcut', {
            "add_furigana": "Ctrl+R", "del_furigana": "Ctrl+Alt+R"
        })


    def getUseRubyTags(self):
        return self.data["useRubyTags"]

    @saveMe
    def setUseRubyTags(self, isEnabled):
        self.data["useRubyTags"] = isEnabled

    def getIgnoreNumbers(self):
        return self.data["ignoreNumbers"]

    @saveMe
    def setIgnoreNumbers(self, isEnabled):
        self.data["ignoreNumbers"] = isEnabled

    def getKeyboardShortcut(self, name):
        return self.data["keyboardShortcut"][name]

    @saveMe
    def setKeyboardShortcut(self, name, key):
        self.data["keyboardShortcut"][name] = key
    
    # --- Getters and Setters for Automatic Generation ---
    
    def getAutoGenerateConfig(self):
        # Return a copy to prevent accidental modification
        return self.data.get('autoGenerateConfig', {}).copy()

    @saveMe
    def setAutoGenerateConfig(self, auto_gen_config):
        self.data['autoGenerateConfig'] = auto_gen_config

    # --- Getter and Setter for Bulk Generation ---

    def getLastBulkConfig(self):
        return self.data.get('lastBulkConfig', {})

    @saveMe
    def setLastBulkConfig(self, bulkConfig):
        self.data['lastBulkConfig'] = bulkConfig
