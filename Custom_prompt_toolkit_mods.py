
from __future__ import unicode_literals

import functools

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.eventloop import run_in_executor
from prompt_toolkit.key_binding.bindings.focus import (
    focus_next,
    focus_previous,
)
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding.key_bindings import (
    KeyBindings,
    merge_key_bindings,
)
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.widgets import (
    Box,
    Button,
    Dialog,
    Label,
    ProgressBar,
    RadioList,
    TextArea,
)

from prompt_toolkit.shortcuts.dialogs import _return_none, _run_dialog


# This is a modified version of the Prompt_Toolkit input_dialog function in prompt_toolkit.shortcuts.dialogs.py

# textFieldsList is a list of tuples of the form [[label 1, default value 1], [label 2, default value 2], ....]
# It will return a dictionary whose keys will be the lables specifed in the input list, and the values will be
# the text entered (or the default value, if no value entered)
# Example usage:
#     textFieldsList = [["dest addr", "127.0.0.1"], ["port", "5000"]]
#     print(str(multi_input_dialog(textFieldsList, title='Enter IP addr and port')))

def multi_input_dialog(textFieldsList, title='', ok_text='OK', cancel_text='Cancel',
                 completer=None, password=False, style=None, async_=False):
    """
    Display a text input box.
    Return the given text, or None when cancelled.
    """
    def accept(buf):
        get_app().layout.focus(ok_button)
        return True  # Keep text.

    def ok_handler():
        # Create dictionary containing entered text
        valuesEnteredDict = {}
        for x in range(len(textAreas)):
            # Build a dictionary using the labels as keys and the TextArea.text values as the values
            valuesEnteredDict[fieldLabels[x]] = textAreas[x].text

        get_app().exit(result=valuesEnteredDict)

    ok_button = Button(text=ok_text, handler=ok_handler)
    cancel_button = Button(text=cancel_text, handler=_return_none)


    # textFieldsList = [["dest addr", "127.0.0.1"], ["port", 5000]]

    fieldLabels = []     # A list of text labels for each field
    textAreas = []  # A list of TextArea objects whose text will be returned to the caller
    userFields = [] # An interleaved list of Labels and TextArea objects that will be passed to the dialog layout
                    # manager (HSplit?)

    # textFieldsList = [["dest addr", "127.0.0.1"], ["port", "5000"]]

    for textField in textFieldsList:
        # # Create list of Label objects. This will be used to create the return dictionary
        fieldLabels.append(textField[0])
        # # Create a list of TextArea objects prepopulated with a default value . This will serve as the
        # list of objects whose text will be returned by the dialogue
        textArea = TextArea(multiline=False,
                    password=password,
                    completer=completer,
                    accept_handler=accept, focus_on_click=True, text=textField[1])
        textAreas.append(textArea)
        # Append label object to the userFields[] list
        userFields.append(Label(text=textField[0], dont_extend_height=True))
        # Append the text area object to the userFields list
        userFields.append(textArea)



    # # Create a list of tuples containing the textfield label and the text field
    # textFields = []
    # # Iterate over fieldTextDict
    # if len(textFieldDict) > 0:
    #     for key, value in textFieldDict.items():
    #         # Create a new text area to be associated with that field
    #         value = TextArea(multiline=False, password=password, completer=completer, accept_handler=accept)
    #         textFields.append([Label(text=key, dont_extend_height=True), value])

    dialog = Dialog(
        title=title,
        body=HSplit(userFields, padding=D(preferred=1, max=1)),
        buttons=[ok_button, cancel_button],
        with_background=True)

    return _run_dialog(dialog, style, async_=async_)