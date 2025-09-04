# -*- coding: utf-8 -*-

# This file is part of Japanese Furigana <https://github.com/obynio/anki-japanese-furigana>.
#
# Japanese Furigana is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Japanese Furigana is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Japanese Furigana.  If not, see <http://www.gnu.org/licenses/>.

import time
from typing import List, Dict

from . import reading
from .utils import removeFurigana
from aqt import *

# This module no longer needs its own config instance.
# It uses values passed in from __init__.py
mecab = reading.MecabController()

def bulkGenerate(collection, noteIds, field_pairs: List[Dict[str, str]], progress, ignore_numbers: bool, use_ruby_tags: bool) -> int:
    """
    Processes a list of notes to generate furigana for multiple field pairs.
    Returns the number of notes that were modified.
    """
    undo_entry = collection.add_custom_undo_entry('Batch Generate Furigana')
    last_progress_update = 0
    notes_modified_count = 0
    total_notes = len(noteIds)

    for i, noteId in enumerate(noteIds):
        note = collection.get_note(noteId)
        is_modified = False

        for pair in field_pairs:
            source_field = pair.get("source")
            dest_field = pair.get("destination")

            if not source_field or not dest_field:
                continue
            
            if source_field in note and dest_field in note and note[source_field]:
                source_text = note[source_field]
                # Pass config values to the generation function
                generated_text = generateFurigana(source_text, ignore_numbers, use_ruby_tags)
                
                # Only update if the content has changed
                if note[dest_field] != generated_text:
                    note[dest_field] = generated_text
                    is_modified = True

        if is_modified:
            notes_modified_count += 1
            collection.update_note(note)
            collection.merge_undo_entries(undo_entry)

        # Update progress bar periodically
        if time.time() - last_progress_update >= 0.1:
            if progress:
                progress(i + 1, total_notes)
            last_progress_update = time.time()
            
    return notes_modified_count

def generateFurigana(html: str, ignore_numbers: bool, use_ruby_tags: bool) -> str:
    """
    Takes a string with Japanese text and returns it with furigana.
    Accepts config options as arguments instead of using a global object.
    """
    # This check prevents errors if the source field is empty
    if not html or not html.strip():
        return ""
    html_no_furigana = removeFurigana(html)
    html_with_furigana = mecab.reading(html_no_furigana, ignore_numbers, use_ruby_tags)
    return html_with_furigana
