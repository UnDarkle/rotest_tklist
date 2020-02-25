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

        except AttributeError as error:
            btn.config(bg='red')
            test._tklist_error = str(error)

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

        if hasattr(test, '_tklist_error'):
            text.insert(tk.END, "\nErrors:\n{}".format(test._tklist_error))


def _explore_subtest(_, tab_control, test):
    """Open another tab for the give test or test component."""
    sub_tab = ttk.Frame(tab_control)
    sub_tab.pack(fill='both')
    tab_control.add(sub_tab, text=test.__name__)
    tab_control.select(tab_control.index(tk.END)-1)
    for class_key, explorer in _class_to_explorer.items():
        if issubclass(test, class_key):
            explorer(sub_tab, test)
            return


def _explore_case(frame, test):
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


class FlowComponentData(object):
    def __init__(self, cls, indent=0, parent=None):
        self.cls = cls
        self.indent = indent
        self.parent = parent
        self.name = cls.__name__
        self.long_name = cls.__name__
        if indent > 1:
            self.long_name = "{}.{}".format(self.parent.long_name, self.name)

        self.actual_inputs = {}  # inputs name -> provider name
        self.actual_outputs = {}  # outputs name -> list of usages

        self.inputs = {}  # original input name -> actual input name
        self.outputs = {}  # original input name -> actual input name

        self.errors = []
        self.unconnected_inputs = []
        self._description = None

        self.is_flow = issubclass(cls, TestFlow)
        self.children = []
        self.resources = [request.name for request in
                          cls.get_resource_requests()]

        if self.is_flow:
            for block_class in self.cls.blocks:
                self.children.append(FlowComponentData(block_class, indent+1,
                                                       self))

            for name, value in cls.common.items():
                self.outputs[name] = name
                self.actual_outputs[name] = []

        else:
            for name, instance in cls.get_inputs().items():
                self.inputs[name] = name
                if instance.is_optional():
                    self.actual_inputs[name] = '(default value = %s)' % \
                                                            instance.default

                else:
                    self.actual_inputs[name] = ''

            for name, instance in cls.get_outputs().items():
                self.outputs[name] = name
                self.actual_outputs[name] = []

        self.handle_common()
        self.find_connections()

    def handle_common(self):
        for name, value in self.cls.common.items():
            if name in self.inputs:
                if isinstance(value, Pipe) and value.parameter_name != name:
                    self.inputs[name] = value.parameter_name
                    self.actual_inputs.pop(name)
                    if value.parameter_name not in self.actual_inputs:
                        self.actual_inputs[value.parameter_name] = ''

            elif name in self.outputs:
                if isinstance(value, Pipe) and value.parameter_name != name:
                    self.outputs[name] = value.parameter_name
                    self.actual_outputs[value.parameter_name] = \
                                                self.actual_outputs.pop(name)

            else:
                if not self.is_flow:
                    self.errors.append("Unknown input %r" % name)

    def propagate_value(self, name, value, provider):
        total_connections = []
        if not self.is_flow:
            if name in self.actual_inputs:
                if isinstance(value, Pipe):
                    if value.parameter_name != name:
                        self.inputs[name] = value.parameter_name
                        self.actual_inputs.pop(name)
                        if value.parameter_name not in self.actual_inputs:
                            self.actual_inputs[value.parameter_name] = ''

                else:
                    self.actual_inputs[name] = provider
                    return [self.long_name]

            elif name in self.actual_outputs and isinstance(value, Pipe):
                if value.parameter_name != name:
                    self.outputs[name] = value.parameter_name
                    self.actual_outputs[value.parameter_name] = \
                                                self.actual_outputs.pop(name)

        else:
            for child in self.children:
                total_connections.extend(child.propagate_value(
                                                        name, value, provider))

        return total_connections

    def apply_common(self):
        if not self.is_flow:
            for name, value in self.cls.common.items():
                if name in self.actual_inputs and not isinstance(value, Pipe):
                    self.actual_inputs[name] = '(parameter = %s)' % value

        else:
            for name, value in self.cls.common.items():
                total_usages = []
                for child in self.children:
                    total_usages.extend(child.propagate_value(name, value,
                                                      '(parent = %s)' % value))

                if total_usages:
                    if name in self.actual_outputs:
                        self.actual_outputs[name].extend(total_usages)

                else:
                    self.errors.append("Unknown input %r" % name)

    def apply_resources(self):
        for resource in self.resources:
            self.propagate_value(resource, None, '(parent resource)')

    def connect_children(self):
        for index, child in enumerate(self.children):
            for output, connections in child.actual_outputs.items():
                for sibling in self.children[index+1:]:
                    connections.extend(
                        sibling.propagate_value(output, None, child.long_name))

    def find_connections(self):
        # parent common value
        # child common value (overrides parent)
        # parent resource
        # output (overrides previous)
        # child resource
        self.apply_common()
        for child in self.children:
            child.apply_common()

        self.apply_resources()
        self.connect_children()
        for child in self.children:
            child.apply_resources()

    def find_unconnected(self):
        for input_name, provider in self.actual_inputs.items():
            if not provider:
                self.errors.append("Input %r is not connected!" % input_name)
                self.unconnected_inputs.append(
                                    "{}.{}".format(self.long_name, input_name))

        for child in self.children:
            child.find_unconnected()
            self.errors.extend(child.errors)
            self.unconnected_inputs.extend(child.unconnected_inputs)

        if self.is_flow and self.indent > 0:
            shadow = FlowComponentData(self.cls)
            shadow.find_unconnected()
            self.inputs.update({name: name for name in shadow.unconnected_inputs})
            self.actual_inputs.update({name: '' for name in shadow.unconnected_inputs})

    def get_description(self):
        if self._description:
            return self._description

        self._description = ""
        if self.is_flow:
            self._description += "Required Inputs:\n"

        else:
            self._description += "Inputs:\n"

        for name, actual_input in self.inputs.items():
            self._description += "    {} <- ".format(name)
            if name != actual_input:
                self._description += "{} <- ".format(actual_input)
            self._description += "{}\n".format(self.actual_inputs[actual_input])

        if self.is_flow:
            self._description += "\nCommon:\n"

        else:
            self._description += "\nOutputs:\n"

        for output, actual_output in self.outputs.items():
            self._description += "    {} -> ".format(output)
            if output != actual_output:
                self._description += "{} -> ".format(actual_output)
            self._description += "{}\n".format(
                                ', '.join(self.actual_outputs[actual_output]))

        if self.errors:
            self._description += "\nErrors:\n"
            for error in self.errors:
                self._description += "    {}\n".format(error)

        return self._description

    def iterate(self):
        yield self

        for child in self.children:
            for sub_component in child.iterate():
                yield sub_component


def _explore_flow(frame, test):
    """Show metadata for a flow."""
    list_frame = ttk.Frame(frame)
    list_frame.grid(column=0, row=0, sticky=tk.N, rowspan=2)
    desc_frame = ttk.Frame(frame)
    desc_frame.grid(column=1, row=0, sticky=tk.N)
    connection_frame = ttk.Frame(frame)
    connection_frame.grid(column=1, row=1, sticky=tk.N)

    desc = tk.Text(desc_frame)
    desc.grid(column=0, row=0)

    connections = tk.Text(connection_frame)
    connections.grid(column=0, row=0)

    flow_data = FlowComponentData(test)
    flow_data.find_unconnected()

    for index, sub_data in enumerate(flow_data.iterate()):
        btn = tk.Label(list_frame, text=sub_data.name)
        btn.grid(column=sub_data.indent, row=index, sticky=tk.W+tk.E)

        btn.bind("<Enter>", partial(_update_flow_desc, desc=desc,
                                    connections=connections, test=sub_data))
        btn.bind("<Leave>", partial(_update_flow_desc, desc=desc,
                                    connections=connections, test=None))

        if sub_data.errors:
            btn.config(bg='red')

    _update_flow_desc(None, desc, flow_data)


def _update_flow_desc(_, desc, connections, test):
    """Update text according to the metadata of a test.

    Args:
        text (tkinter.Text): text to update.
        test (type): test class to update according to.
    """
    desc.delete("1.0", tk.END)
    connections.delete("1.0", tk.END)
    if test:
        desc.insert(tk.END, test.cls.__name__+"\n")
        desc.insert(tk.END, "Resource requests:\n")
        for request in test.cls.get_resource_requests():
            desc.insert(tk.END, "  {} = {}({})\n".format(request.name,
                                                         request.type.__name__,
                                                         request.kwargs))

        desc.insert(tk.END, "\n")

        if test.cls.__doc__:
            desc.insert(tk.END, test.cls.__doc__)

        connections.insert(tk.END, test.get_description())


_class_to_explorer = {TestCase: _explore_case,
                      TestFlow: _explore_flow}