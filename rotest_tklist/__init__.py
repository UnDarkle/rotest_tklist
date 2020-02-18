"""Tklist implementation."""
import sys
from functools import partial

import tkinter as tk
from rotest.core import TestCase, TestFlow, TestBlock, TestSuite


def tk_list_option(parser):
    """Add the 'tklist' flag to the CLI options."""
    parser.add_argument("--tklist", "-L", action="store_true",
                        help="Like list but better")


def tk_list_action(tests, config):
    """Open the Tkinter tests explorer if 'tklist' flag is on."""
    if getattr(config, "tklist", False):
        _tk_list_tests(tests, config)
        sys.exit(0)


def _tk_list_tests(tests, config):
    """Create the tests explorer main window."""
    window = tk.Tk()
    tab_control = tk.ttk.Notebook(window)
    tab_control.bind("<ButtonRelease-1>", partial(forget_children_tabs,
                                                  tab_control=tab_control))

    main_tab = tk.ttk.Frame(tab_control)
    tab_control.add(main_tab, text='Main')
    tab_control.pack(expand=1, fill='both')

    list_frame = tk.ttk.Frame(main_tab)
    list_frame.grid(column=0, row=0, sticky=tk.N)
    desc_frame = tk.ttk.Frame(main_tab)
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
                      config=config,
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
    sub_tab = tk.ttk.Frame(tab_control)
    sub_tab.pack(fill='both')
    tab_control.add(sub_tab, text=test.__name__)
    tab_control.select(tab_control.index(tk.END)-1)
    for class_key, explorer in _class_to_explorer.items():
        if issubclass(test, class_key):
            explorer(sub_tab, test)
            return


def _explore_case(frame, test):
    """Show metadata for a TestCase."""
    list_frame = tk.ttk.Frame(frame)
    list_frame.grid(column=0, row=0, sticky=tk.N)
    desc_frame = tk.ttk.Frame(frame)
    desc_frame.grid(column=1, row=0, sticky=tk.N)

    desc = tk.Text(desc_frame)
    desc.grid(column=0, row=0)

    methods = test.load_test_method_names()
    _update_desc(None, desc, test)

    for index, method_name in enumerate(methods):
        label = tk.Label(list_frame, text=test.get_name(method_name))
        label.grid(column=0, row=index, sticky=tk.W+tk.E)


def _explore_flow(frame, test):
    pass
    # TODO: init, catching validation error and informing about it


def _explore_block(frame, test):
    pass
    # TODO: init, catching validation error and informing about it


_class_to_explorer = {TestCase: _explore_case,
                      TestFlow: _explore_flow,
                      TestBlock: _explore_block}