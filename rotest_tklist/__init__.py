"""Tklist implementation."""
import sys
from functools import partial

import tkinter as tk
from tkinter import ttk
from rotest.core import TestCase, TestFlow, TestBlock, TestSuite, Pipe


def tk_list_option(parser):
    """Add the 'tklist' flag to the CLI options."""
    parser.add_argument("--tklist", "-L", action="store_true",
                        help="Like list but better")


def tk_list_action(tests, config):
    """Open the Tkinter tests explorer if 'tklist' flag is on."""
    if getattr(config, "tklist", False):
        _tk_list_tests(tests)
        sys.exit(0)


def _tk_list_tests(tests):
    """Create the tests explorer main window."""
    window = tk.Tk()
    tab_control = ttk.Notebook(window)
    tab_control.bind("<ButtonRelease-1>", partial(forget_children_tabs,
                                                  tab_control=tab_control))

    main_tab = ttk.Frame(tab_control)
    tab_control.add(main_tab, text='Main')
    tab_control.pack(expand=1, fill='both')

    list_frame = ttk.Frame(main_tab)
    list_frame.grid(column=0, row=0, sticky=tk.N)
    desc_frame = ttk.Frame(main_tab)
    desc_frame.grid(column=1, row=0, sticky=tk.N)

    desc = tk.Text(desc_frame)
    desc.grid(column=0, row=0)

    for index, test in enumerate(tests):
        btn = tk.Button(list_frame, text=test.__name__)
        btn.grid(column=0, row=index, sticky=tk.W+tk.E)

        btn.bind("<Enter>", partial(_update_desc, text=desc, test=test))
        btn.bind("<Leave>", partial(_update_desc, text=desc, test=None))
        btn.bind("<Button-1>", partial(_explore_subtest,
                                       tab_control=tab_control,
                                       test=test))

        try:
            TestSuite(tests=[test],
                      run_data=None,
                      config=None,
                      skip_init=False,
                      save_state=False,
                      enable_debug=False,
                      resource_manager=False)

        except AttributeError:
            btn.config(bg='red')

    window.mainloop()

    # TODO: Add 'get-estimated-time' button take will calculate for all items
    # in the current tab (save it into the class for quick access),
    # and give an estimation of the total run time


def forget_children_tabs(_, tab_control):
    """Remove the tabs to the right of the current one."""
    current_index = tab_control.index(tk.CURRENT)
    last_index = tab_control.index(tk.END) - 1
    while last_index > current_index:
        tab_control.hide(last_index)
        tab_control.forget(last_index)
        last_index -= 1

    tab_control.pack()


def _update_desc(_, text, test):
    """Update text according to the metadata of a test.

    Args:
        text (tkinter.Text): text to update.
        test (type): test class to update according to.
    """
    text.delete("1.0", tk.END)
    if test:
        text.insert(tk.END, test.__name__+"\n")
        text.insert(tk.END, "Tags: {}\n".format(test.TAGS))
        text.insert(tk.END, "Timeout: {} min\n".format(test.TIMEOUT/60.0))
        text.insert(tk.END, "Resource requests:\n")
        for request in test.get_resource_requests():
            text.insert(tk.END, "  {} = {}({})\n".format(request.name,
                                                         request.type.__name__,
                                                         request.kwargs))

        text.insert(tk.END, "\n")
        if test.__doc__:
            text.insert(tk.END, test.__doc__)


def _explore_subtest(_, tab_control, test):
    """Open another tab for the give test or test component."""
    sub_tab = ttk.Frame(tab_control)
    sub_tab.pack(fill='both')
    tab_control.add(sub_tab, text=test.__name__)
    tab_control.select(tab_control.index(tk.END)-1)
    for class_key, explorer in _class_to_explorer.items():
        if issubclass(test, class_key):
            explorer(tab_control, sub_tab, test)
            return


def _explore_case(_, __, frame, test):
    """Show metadata for a TestCase."""
    list_frame = ttk.Frame(frame)
    list_frame.grid(column=0, row=0, sticky=tk.N)
    desc_frame = ttk.Frame(frame)
    desc_frame.grid(column=1, row=0, sticky=tk.N)

    desc = tk.Text(desc_frame)
    desc.grid(column=0, row=0)

    methods = test.load_test_method_names()
    _update_desc(None, desc, test)

    for index, method_name in enumerate(methods):
        label = tk.Label(list_frame, text=test.get_name(method_name))
        label.grid(column=0, row=index, sticky=tk.W+tk.E)


class Redirector(object):
    def __init__(self, var_name, pipe_to=None, pipe_from=None):
        self.var_name = var_name
        self.pipe_to = pipe_to
        self.pipe_from = pipe_from

    def __str__(self):
        if self.pipe_to:
            return "{} -> {}".format(self.var_name, self.pipe_to)

        if self.pipe_from:
            return "{} <- {}".format(self.var_name, self.pipe_from)

        return self.var_name

    def __repr__(self):
        return self.__str__()

    @property
    def name(self):
        return self.pipe_from or self.var_name

    def __eq__(self, other):
        if isinstance(other, Redirector):
            print('greg')
            return (other.pipe_to or self.name) == (other.pipe_to or other.name)

        else:
            print("stas")
        return self.name == other

    def __hash__(self):
        return hash(self.var_name)


def _explore_flow(tab_control, frame, test):
    """Show metadata for a flow."""
    list_frame = ttk.Frame(frame)
    list_frame.grid(column=0, row=0, sticky=tk.N)
    desc_frame = ttk.Frame(frame)
    desc_frame.grid(column=1, row=0, sticky=tk.N)

    desc = tk.Text(desc_frame)
    desc.grid(column=0, row=0)

    total_outputs = {Redirector(request.name): test
                     for request in test.get_resource_requests()}

    for key, value in test.common.items():
        if isinstance(value, Pipe):
            total_outputs[Redirector(key, pipe_from=value.parameter_name)] = \
                test

        else:
            total_outputs[Redirector(key)] = test

    unconnected_inputs = set()
    total_inputs = {}
    test._tklist_outputs = {key: [] for key in total_outputs.keys()}

    for index, sub_test in enumerate(test.blocks):
        btn = tk.Button(list_frame, text=sub_test.__name__)
        btn.grid(column=0, row=index, sticky=tk.W+tk.E)

        btn.bind("<Enter>", partial(_update_flow_desc, text=desc, test=sub_test))
        btn.bind("<Leave>", partial(_update_flow_desc, text=desc, test=test))
        btn.bind("<Button-1>", partial(_explore_subtest,
                                       tab_control=tab_control,
                                       test=test))

        sub_test._tklist_inputs = {}
        block_inputs = _get_inputs(sub_test)
        for block_input in block_inputs:
            print("searching for", block_input, "in", list(total_outputs.keys()))
            matching_output = total_outputs.get(block_input, None)
            if not matching_output:
                if block_input in sub_test.common:
                    matching_output = 'parameter'

                else:
                    has_default_value = False
                    if issubclass(sub_test, TestBlock):
                        actual_input = sub_test.get_inputs().get(block_input,
                                                                 None)
                        if actual_input:
                            has_default_value = actual_input.is_optional()

                    if has_default_value:
                        matching_output = 'default value'

                    else:
                        matching_output = ''
                        unconnected_inputs.add(block_input)
                        btn.config(bg='red')

            else:
                matching_output._tklist_outputs[block_input.name].append(
                                                    sub_test.__name__)
                matching_output = matching_output.__name__

            total_inputs[block_input] = total_inputs.get(block_input, []) + \
                                        [sub_test.__name__]

            sub_test._tklist_inputs[block_input] = matching_output

        block_outputs = _update_outputs(sub_test, total_outputs)
        sub_test._tklist_outputs = {key: [] for key in block_outputs}

    _update_flow_desc(None, desc, test)
    # TODO: init, catching validation error and informing about it


def _update_outputs(flow_component, target_outputs):
    outputs = set()
    if issubclass(flow_component, TestBlock):
        for output in flow_component.get_outputs().keys():
            outputs.add(Redirector(output))

    for key, value in flow_component.common.items():
        if isinstance(value, Pipe):
            if key in outputs:
                outputs -= {key}
                outputs.add(Redirector(key, pipe_to=value.parameter_name))

    target_outputs.update({key: flow_component
                           for key in outputs})

    return outputs


def _get_inputs(flow_component):
    inputs = set()
    if issubclass(flow_component, TestBlock):
        for input in flow_component.get_inputs().keys():
            inputs.add(Redirector(input))

    else:
        for sub_component in flow_component.blocks:
            inputs.union(_get_inputs(sub_component))

    for key, value in flow_component.common.items():
        if isinstance(value, Pipe):
            if key in inputs:
                inputs -= {key}
                inputs.add(Redirector(key, pipe_from=value.parameter_name))

    return inputs


def _update_flow_desc(_, text, test):
    """Update text according to the metadata of a test.

    Args:
        text (tkinter.Text): text to update.
        test (type): test class to update according to.
    """
    text.delete("1.0", tk.END)
    if test:
        text.insert(tk.END, test.__name__+"\n")
        text.insert(tk.END, "Resource requests:\n")
        for request in test.get_resource_requests():
            text.insert(tk.END, "  {} = {}({})\n".format(request.name,
                                                         request.type.__name__,
                                                         request.kwargs))

        text.insert(tk.END, "\n")
        if test.__doc__:
            text.insert(tk.END, test.__doc__)

        if hasattr(test, '_tklist_inputs'):
            text.insert(tk.END, "\nInputs:\n")
            for input_name, input_target in test._tklist_inputs.items():
                text.insert(tk.END, "    {} <- {}\n".format(input_name,
                                                            input_target))

        if hasattr(test, '_tklist_outputs'):
            text.insert(tk.END, "\nOutputs:\n")
            for output_name, output_target in test._tklist_outputs.items():
                text.insert(tk.END, "    {} -> {}\n".format(output_name,
                                                    ', '.join(output_target)))


def _explore_block(_, frame, test):
    pass
    # TODO: init, catching validation error and informing about it


_class_to_explorer = {TestCase: _explore_case,
                      TestFlow: _explore_flow,
                      TestBlock: _explore_block}