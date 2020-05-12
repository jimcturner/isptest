import functools
from asyncio import get_event_loop
from typing import Any, Callable, List, Optional, Tuple, TypeVar

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer
from prompt_toolkit.eventloop import run_in_executor_with_context
from prompt_toolkit.filters import FilterOrBool
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings, merge_key_bindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import AnyContainer, HSplit
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.styles import BaseStyle
from prompt_toolkit.widgets import (
    Box,
    Button,
    CheckboxList,
    Dialog,
    Label,
    ProgressBar,
    RadioList,
    TextArea,
    HorizontalLine
)


from prompt_toolkit.shortcuts.dialogs import _create_app

from prompt_toolkit.shortcuts.dialogs import _return_none

# Creates a multifield text input form.
# The arg textFieldsList[] is a list of tuples containing ["text label for the field", "default value"]
# It returns a dictionary. The keys are the labels supplied in textFieldsList[n][0]
# Sample usage:
# Define the dialogue colours
#                 styleDefinition = Style.from_dict({
#                     'dialog': 'bg:ansiblue',  # Screen background
#                     'dialog frame.label': 'bg:ansiwhite ansired ',
#                     'dialog.body': 'bg:ansiwhite ansiblack',
#                     'dialog shadow': 'bg:ansiblack'})
#     dialogUserFieldsList = [["Destination address", six.text_type(destAddr)],
#                             ["UDP destination port (1024-65535)", six.text_type(destPort)]]
#       newTxStreamParametersDict = multi_input_dialog(dialogUserFieldsList,
#                                                                    title=title,
#                                                                    style=styleDefinition).run()

def multi_input_dialog(
    textFieldsList,
    title: AnyFormattedText = "",
    # text: AnyFormattedText = "",
    ok_text: str = "OK",
    cancel_text: str = "Cancel",
    completer: Optional[Completer] = None,
    password: FilterOrBool = False,
    style: Optional[BaseStyle] = None,
    optionalFooterText = None
) -> Application[str]:
    """
    Display a text input box.
    Return the given text, or None when cancelled.
    """

    def accept(buf: Buffer) -> bool:
        get_app().layout.focus(ok_button)
        return True  # Keep text.

    def ok_handler() -> None:
        # Create dictionary containing entered text
        valuesEnteredDict = {}
        for x in range(len(textAreas)):
            # Build a dictionary using the labels as keys and the TextArea.text values as the values
            valuesEnteredDict[fieldLabels[x]] = textAreas[x].text
        get_app().exit(result=valuesEnteredDict)

    ok_button = Button(text=ok_text, handler=ok_handler)
    cancel_button = Button(text=cancel_text, handler=_return_none)

    fieldLabels = []  # A list of text labels for each field
    textAreas = []  # A list of TextArea objects whose text will be returned to the caller
    userFields = []  # An interleaved list of Labels and TextArea objects that will be passed to the dialog layout
                    # manager (HSplit?)

    # textfield = TextArea(
    #     multiline=False, password=password, completer=completer, accept_handler=accept
    # )
    # Iterate over supplied dict to create a series of Labels and TextAreas
    for textField in textFieldsList:
        # # Create list of Label objects. This will be used to create the return dictionary
        fieldLabels.append(textField[0])
        # # Create a list of TextArea objects prepopulated with a default value . This will serve as the
        # list of objects whose text will be returned by the dialogue
        textArea = TextArea(multiline=False,
                    password=password,
                    completer=completer,
                    accept_handler=accept, focus_on_click=False, text=textField[1])
        textAreas.append(textArea)
        # Append label object to the userFields[] list
        userFields.append(Label(text=textField[0], dont_extend_height=True))
        # Append the text area object to the userFields list
        userFields.append(textArea)

    # Append optional footer (if supplied)
    if optionalFooterText is not None:
        userFields.append(HorizontalLine())
        userFields.append(Label(text=str(optionalFooterText), dont_extend_height=True))

    dialog = Dialog(
        title=title,
        body=HSplit(
            userFields,
            padding=D(preferred=0, max=0),
        ),
        buttons=[ok_button, cancel_button],
        with_background=True,
    )

    return _create_app(dialog, style)