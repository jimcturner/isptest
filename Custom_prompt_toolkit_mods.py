
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
def multi_input_dialog(title='', text='', ok_text='OK', cancel_text='Cancel',
                 completer=None, password=False, style=None, async_=False):
    """
    Display a text input box.
    Return the given text, or None when cancelled.
    """
    def accept(buf):
        get_app().layout.focus(ok_button)
        return True  # Keep text.

    def ok_handler():
        get_app().exit(result=textfield.text)

    ok_button = Button(text=ok_text, handler=ok_handler)
    cancel_button = Button(text=cancel_text, handler=_return_none)

    textfield = TextArea(
        multiline=False,
        password=password,
        completer=completer,
        accept_handler=accept)

    dialog = Dialog(
        title=title,
        body=HSplit([
            Label(text=text, dont_extend_height=True),
            textfield,
        ], padding=D(preferred=1, max=1)),
        buttons=[ok_button, cancel_button],
        with_background=True)

    return _run_dialog(dialog, style, async_=async_)