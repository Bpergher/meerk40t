import os

import wx
from wx import aui

from ..kernel import signal_listener
from .icons import (
    STD_ICON_SIZE,
    get_default_icon_size,
    icon_add_new,
    icon_edit,
    icon_trash,
    icons8_paste,
    icon_library,
)
from .mwindow import MWindow
from .wxutils import StaticBoxSizer, dip_size, ScrolledPanel

_ = wx.GetTranslation


class MaterialPanel(ScrolledPanel):
    def __init__(self, *args, context=None, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.TAB_TRAVERSAL
        ScrolledPanel.__init__(self, *args, **kwds)
        self.context = context
        self.SetHelpText("materialmanager")
        self.parent_panel = None
        self.current_item = None
        self._active_material = None
        # Dictionary with key=Materialname, entry=Description (Name, Lasertype, entries)
        self.material_list = dict()
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        filter_box = StaticBoxSizer(self, wx.ID_ANY, _("Filter Materials"), wx.HORIZONTAL)
        label_1 = wx.StaticText(self, wx.ID_ANY, _("Material"))
        filter_box.Add(label_1, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.txt_material = wx.TextCtrl(self, wx.ID_ANY, "")
        filter_box.Add(self.txt_material, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        label_2 = wx.StaticText(self, wx.ID_ANY, _("Lasertype"))
        filter_box.Add(label_2, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.laser_choices = [_("<All Lasertypes>"),]
        dev_infos = list(self.context.find("provider/friendly"))
        # Gets a list of tuples (description, key, path)
        dev_infos.sort(key=lambda e: e[0][1])
        for e in dev_infos:
            self.laser_choices.append(e[0][0])

        self.combo_lasertype = wx.ComboBox(self, wx.ID_ANY, choices=self.laser_choices, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        filter_box.Add(self.combo_lasertype, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        self.btn_reset = wx.Button(self, wx.ID_ANY, _("Reset Filter"))
        filter_box.Add(self.btn_reset, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(filter_box, 0, wx.EXPAND, 0)
        result_box = StaticBoxSizer(self, wx.ID_ANY, _("Matching library entries"), wx.VERTICAL)
        self.list_library_entries = wx.ListCtrl(
            self,
            wx.ID_ANY,
            style=wx.LC_HRULES | wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL,
        )
        self.list_library_entries.AppendColumn(_("#"), format=wx.LIST_FORMAT_LEFT, width=58)
        self.list_library_entries.AppendColumn(
            _("Material"),
            format=wx.LIST_FORMAT_LEFT,
            width=95,
        )
        self.list_library_entries.AppendColumn(
            _("Lasertype"), format=wx.LIST_FORMAT_LEFT, width=95
        )
        self.list_library_entries.AppendColumn(
            _("Operations"), format=wx.LIST_FORMAT_LEFT, width=65
        )
        self.list_preview = wx.ListCtrl(
            self,
            wx.ID_ANY,
            style=wx.LC_HRULES | wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL,
        )
        self.list_preview.AppendColumn(_("#"), format=wx.LIST_FORMAT_LEFT, width=58)
        self.list_preview.AppendColumn(
            _("Operation"),
            format=wx.LIST_FORMAT_LEFT,
            width=95,
        )
        self.list_preview.AppendColumn(
            _("Id"), format=wx.LIST_FORMAT_LEFT, width=95
        )
        self.list_preview.AppendColumn(
            _("Label"), format=wx.LIST_FORMAT_LEFT, width=95
        )
        self.list_preview.AppendColumn(
            _("Power"), format=wx.LIST_FORMAT_LEFT, width=65
        )
        self.list_preview.AppendColumn(
            _("Speed"), format=wx.LIST_FORMAT_LEFT, width=65
        )

        param_box = StaticBoxSizer(self, wx.ID_ANY, _("Information"), wx.HORIZONTAL)
        label_1 = wx.StaticText(self, wx.ID_ANY, _("Material"))
        param_box.Add(label_1, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.txt_entry_name = wx.TextCtrl(self, wx.ID_ANY, "")
        param_box.Add(self.txt_entry_name, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        label_2 = wx.StaticText(self, wx.ID_ANY, _("Lasertype"))
        param_box.Add(label_2, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        choices = self.laser_choices[1:]
        self.combo_entry_type = wx.ComboBox(self, wx.ID_ANY, choices=choices, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        param_box.Add(self.combo_entry_type, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        self.btn_set = wx.Button(self, wx.ID_ANY, _("Set"))
        self.btn_set.SetToolTip(_("Change the name / lasertype of the current entry"))
        param_box.Add(self.btn_set, 0, wx.EXPAND, 0)

        result_box.Add(self.list_library_entries, 1, wx.EXPAND, 0)
        result_box.Add(param_box, 0, wx.EXPAND, 0)
        result_box.Add(self.list_preview, 1, wx.EXPAND, 0)

        button_box = wx.BoxSizer(wx.VERTICAL)

        self.btn_use_current = wx.Button(self, wx.ID_ANY, _("Get current"))
        self.btn_use_current.SetToolTip(_("Use the currently defined operations"))
        self.btn_apply = wx.Button(self, wx.ID_ANY, _("Use for Tree"))
        self.btn_apply.SetToolTip(_("Apply the current library entry to the operations branch"))
        self.btn_simple_apply = wx.Button(self, wx.ID_ANY, _("Use for statusbar"))
        self.btn_simple_apply.SetToolTip(_("Use the current library entry for the statusbar icons"))
        self.btn_delete = wx.Button(self, wx.ID_ANY, _("Delete"))
        self.btn_delete.SetToolTip(_("Delete the current library entry"))
        self.btn_duplicate = wx.Button(self, wx.ID_ANY, _("Duplicate"))
        self.btn_duplicate.SetToolTip(_("Duplicate the current library entry"))
        self.btn_import = wx.Button(self, wx.ID_ANY, _("Import"))
        self.btn_import.SetToolTip(_("Import a material library from ezcad or LightBurn"))
        self.btn_share = wx.Button(self, wx.ID_ANY, _("Share"))
        self.btn_share.SetToolTip(_("Share the current library entry with the MeerK40t community"))

        button_box.Add(self.btn_use_current, 0, wx.EXPAND, 0)
        button_box.Add(self.btn_apply, 0, wx.EXPAND, 0)
        button_box.Add(self.btn_simple_apply, 0, wx.EXPAND, 0)
        button_box.Add(self.btn_delete, 0, wx.EXPAND, 0)
        button_box.Add(self.btn_duplicate, 0, wx.EXPAND, 0)
        button_box.AddSpacer(self.btn_duplicate.Size[1])
        button_box.Add(self.btn_import, 0, wx.EXPAND, 0)
        button_box.Add(self.btn_share, 0, wx.EXPAND, 0)
        outer_box = wx.BoxSizer(wx.HORIZONTAL)
        outer_box.Add(result_box, 1, wx.EXPAND, 0)
        outer_box.Add(button_box, 0, wx.EXPAND, 0)
        main_sizer.Add(outer_box, 1, wx.EXPAND, 0)

        self.SetSizer(main_sizer)
        self.Layout()
        self.btn_reset.Bind(wx.EVT_BUTTON, self.on_reset)
        self.combo_lasertype.Bind(wx.EVT_COMBOBOX, self.update_list)
        self.txt_material.Bind(wx.EVT_TEXT, self.update_list)
        self.btn_use_current.Bind(wx.EVT_BUTTON, self.on_use_current)
        self.btn_apply.Bind(wx.EVT_BUTTON, self.on_apply)
        self.btn_simple_apply.Bind(wx.EVT_BUTTON, self.on_simple_apply)
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_duplicate.Bind(wx.EVT_BUTTON, self.on_duplicate)
        self.btn_import.Bind(wx.EVT_BUTTON, self.on_import)
        self.btn_share.Bind(wx.EVT_BUTTON, self.on_share)
        self.btn_set.Bind(wx.EVT_BUTTON, self.update_entry)
        self.list_library_entries.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_selection)
        self.list_preview.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_preview_selection)
        self.SetupScrolling()
        # Set buttons
        self.active_material = None
        self.on_reset(None)

    @property
    def active_material(self):
        return self._active_material

    @active_material.setter
    def active_material(self, newvalue):
        self._active_material = newvalue
        active = bool(newvalue is not None)
        self.btn_apply.Enable(active)
        self.btn_simple_apply.Enable(active)
        self.btn_delete.Enable(active)
        self.btn_duplicate.Enable(active)
        self.txt_entry_name.Enable(active)
        self.combo_entry_type.Enable(active)
        self.btn_set.Enable(active)
        opcount = len(list(self.context.elements.ops()))
        self.btn_use_current.Enable(opcount > 0)

    def retrieve_material_list(self, filtername=None, filterlaser=None, reload=True):
        if reload:
            self.material_list.clear()
            for section in self.context.elements.op_data.section_set():
                if section == "previous":
                    continue
                count = 0
                secname = section
                secdesc = ""
                ltype = 0 # All lasers
                for subsection in self.context.elements.op_data.derivable(secname):
                    if subsection.endswith(" info"):
                        secdesc = self.context.elements.op_data.read_persistent(str, subsection, "name", secname)
                        ltype = self.context.elements.op_data.read_persistent(int, subsection, "laser", 0)
                    else:
                        count += 1

                entry = [secname, secdesc, count, ltype]
                self.material_list[secname] = entry
        self.list_library_entries.DeleteAllItems()
        idx = 0
        listidx = -1
        for key, entry in self.material_list.items():
            listidx += 1
            if filtername is not None and filtername.lower() not in entry[1].lower():
                continue
            if filterlaser is not None:
                if filterlaser == 0 or entry[2] == 0 or filterlaser==entry[2]:
                    pass
                else:
                    continue
            idx += 1
            list_id = self.list_library_entries.InsertItem(
                self.list_library_entries.GetItemCount(), f"#{idx+ 1}"
            )

            self.list_library_entries.SetItem(list_id, 1, entry[1])
            ltype = entry[3]
            if ltype is None:
                ltype = 0
            if isinstance(ltype, str):
                ltype = 0
            if 0 <= ltype < len(self.laser_choices):
                info = self.laser_choices[ltype]
            else:
                info = "???"
            self.list_library_entries.SetItem(list_id, 2, info)
            self.list_library_entries.SetItem(list_id, 3, str(entry[2]))
            self.list_library_entries.SetItemData(list_id, listidx)
        self.active_material = None

    def get_nth_material(self, n=0):
        dictionary = self.material_list
        if n < 0:
            n += len(dictionary)
        for i, key in enumerate(dictionary.keys()):
            if i == n:
                return key
        return None

    def on_share(self, event):
        print ("Sharing")

    def on_duplicate(self, event):
        if self.active_material is None:
            return
        op_list, op_info = self.context.elements.load_persistent_op_list(self.active_material)
        if len(op_list) == 0:
            return
        oldsection = self.active_material
        if oldsection.endswith(")"):
            idx = oldsection.rfind("(")
            if idx >= 0:
                oldsection = oldsection[:idx]
                if oldsection.endswith("_"):
                    oldsection = oldsection[:-1]

        counter = 0
        while True:
            counter += 1
            newsection = f"{oldsection}_({counter})"
            if newsection not in self.material_list:
                break

        # print (f"Section={oldsection} -> {newsection}")

        oldname = oldsection
        if "name" in op_info:
            oldname = op_info["name"]
            if oldname.endswith(")"):
                idx = oldname.rfind("(")
                if idx >= 0:
                    oldname = oldname[:idx]
        newname = f"{oldname} ({counter})"
        op_info["name"] = newname
        self.context.elements.save_persistent_operations_list(newsection, oplist=op_list, opinfo=op_info, inform=False)
        self.retrieve_material_list(reload=True)

    def on_delete(self, event):
        if self.active_material is None:
            return
        if self.context.kernel.yesno(
            _("Do you really want to delete this entry? This can't be undone.")
        ):
            self.context.elements.clear_persistent_operations(self.active_material)
            self.retrieve_material_list(reload=True)

    def on_import(self, event):
        print ("Importing")

    def on_simple_apply(self, event):
        if self.active_material is None:
            return
        op_list, op_info = self.context.elements.load_persistent_op_list(self.active_material)
        if len(op_list) == 0:
            return
        self.context.elements.default_operations = list(op_list)
        self.context.signal("default_operations")

    def on_apply(self, event):
        if self.active_material is None:
            return
        op_list, op_info = self.context.elements.load_persistent_op_list(self.active_material)
        if len(op_list) == 0:
            return
        self.context.elements.load_persistent_operations(self.active_material)
        self.context.elements.default_operations = list(op_list)
        self.context.signal("default_operations")

    def on_use_current(self, event):
        target_idx = None
        if self.active_material is not None:
            if self.context.kernel.yesno(
                _("Do you want to use the operations in the tree for the current entry?")
            ):
                target_idx = self.active_material
        if target_idx is None:
            entry_txt = self.txt_entry_name.GetValue()
            if entry_txt == "":
                entry_txt = "New material"
            if entry_txt in self.material_list:
                idx = 0
                while True:
                    idx += 1
                    entry_txt = f"New material ({idx})"
                    if entry_txt not in self.material_list:
                        break
            entry_type = self.combo_entry_type.GetSelection()
            if entry_type < 0 :
                entry_type = 0
            # We need to create a new one...
            op_info = dict()
            op_info["name"] = entry_txt
            op_info["laser"] = entry_type
        # TODO APPLY

        self.retrieve_material_list()

    def on_reset(self, event):
        self.txt_material.SetValue("")
        self.combo_lasertype.SetSelection(0)
        self.update_list(reload=True)

    def update_list(self, *args, **kwargs):
        filter_txt = self.txt_material.GetValue()
        filter_type = self.combo_lasertype.GetSelection()
        if filter_txt == "":
            filter_txt = None
        if filter_type < 0:
            filter_type = None
        reload = False
        if "reload" in kwargs:
            reload = kwargs["reload"]
        self.retrieve_material_list(filtername=filter_txt, filterlaser=filter_type, reload=reload)

    def update_entry(self, event):
        if self.active_material is None:
            return
        op_name = self.txt_entry_name.GetValue()
        op_ltype = self.combo_entry_type.GetSelection()
        if op_ltype < 0:
            op_ltype = 0
        op_list, op_info = self.context.elements.load_persistent_op_list(self.active_material)
        if len(op_list) == 0:
            return
        stored_name = ""
        if "name" in op_info:
            stored_name = op_info["name"]
        stored_ltype = 0
        if "laser" in op_info:
            stored_ltype = op_info["laser"]
        if stored_name != op_name or stored_ltype != op_ltype:
            op_info["laser"] = op_ltype
            op_info["name"] = op_name
            self.context.elements.save_persistent_operations_list(self.active_material, oplist=op_list, opinfo=op_info, inform=False)
            self.retrieve_material_list(reload=True)

    def on_list_selection(self, event):
        current_item = self.list_library_entries.GetFirstSelected()
        if current_item < 0:
            self.active_material = None
        else:
            listidx = self.list_library_entries.GetItemData(current_item)
            self.active_material = self.get_nth_material(listidx)
        self.list_preview.DeleteAllItems()
        secdesc = ""
        ltype = 0
        if self.active_material is not None:
            secdesc = self.active_material
            idx = 0
            for subsection in self.context.elements.op_data.derivable(self.active_material):
                if subsection.endswith(" info"):
                    secdesc = self.context.elements.op_data.read_persistent(str, subsection, "name", secdesc)
                    ltype = self.context.elements.op_data.read_persistent(int, subsection, "laser", 0)
                    continue
                optype = self.context.elements.op_data.read_persistent(str, subsection, "type", "")
                if optype is None or optype == "":
                    continue
                idx += 1
                opid = self.context.elements.op_data.read_persistent(str, subsection, "id", "")
                oplabel = self.context.elements.op_data.read_persistent(str, subsection, "label", "")
                speed = self.context.elements.op_data.read_persistent(str, subsection, "speed", "")
                power = self.context.elements.op_data.read_persistent(str, subsection, "power", "")
                if power == "" and optype.startswith("op "):
                    power = "1000"
                list_id = self.list_preview.InsertItem(
                    self.list_preview.GetItemCount(), f"#{idx}"
                )
                self.list_preview.SetItem(list_id, 1, optype)
                self.list_preview.SetItem(list_id, 2, opid)
                self.list_preview.SetItem(list_id, 3, oplabel)
                self.list_preview.SetItem(list_id, 4, power)
                self.list_preview.SetItem(list_id, 5, speed)

        self.txt_entry_name.SetValue(secdesc)
        self.combo_entry_type.SetSelection(ltype)


    def on_preview_selection(self, event):
        pass

    def set_parent(self, par_panel):
        self.parent_panel = par_panel

    def pane_show(self):
        self.update_list(reload=True)

    def pane_hide(self):
        pass


class ImportPanel(wx.Panel):
    def __init__(self, *args, context=None, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.TAB_TRAVERSAL
        wx.Panel.__init__(self, *args, **kwds)
        self.parent_panel = None
        self.context = context
        self.library_entries = []
        self.visible_list = []
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        filter_box = StaticBoxSizer(self, wx.ID_ANY, _("Import Materials"), wx.HORIZONTAL)

        label_1 = wx.StaticText(self, wx.ID_ANY, _("Material"))
        filter_box.Add(label_1, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.txt_material = wx.TextCtrl(self, wx.ID_ANY, "")
        filter_box.Add(self.txt_material, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        label_2 = wx.StaticText(self, wx.ID_ANY, _("Lasertype"))
        filter_box.Add(label_2, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.laser_choices = [_("<All Lasertypes>"),]
        dev_infos = list(self.context.find("provider/friendly"))
        # Gets a list of tuples (description, key, path)
        # description is a tuple itself containing description and index
        dev_infos.sort(key=lambda e: e[0][1])
        for e in dev_infos:
            self.laser_choices.append(e[0][0])
        self.combo_lasertype = wx.ComboBox(self, wx.ID_ANY, choices=self.laser_choices, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        filter_box.Add(self.combo_lasertype, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        self.btn_reset = wx.Button(self, wx.ID_ANY, _("Reset Filter"))
        filter_box.Add(self.btn_reset, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.btn_load = wx.Button(self, wx.ID_ANY, _("Load"))
        filter_box.Add(self.btn_load, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(filter_box, 0, wx.EXPAND, 0)
        result_box = StaticBoxSizer(self, wx.ID_ANY, _("Matching library entries"), wx.VERTICAL)
        self.list_library_entries = wx.ListCtrl(
            self,
            wx.ID_ANY,
            style=wx.LC_HRULES | wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL,
        )
        self.list_library_entries.AppendColumn(_("#"), format=wx.LIST_FORMAT_LEFT, width=58)
        self.list_library_entries.AppendColumn(
            _("Material"),
            format=wx.LIST_FORMAT_LEFT,
            width=95,
        )
        self.list_library_entries.AppendColumn(
            _("Lasertype"), format=wx.LIST_FORMAT_LEFT, width=95
        )
        self.list_library_entries.AppendColumn(
            _("Operations"), format=wx.LIST_FORMAT_LEFT, width=65
        )
        self.list_preview = wx.ListCtrl(
            self,
            wx.ID_ANY,
            style=wx.LC_HRULES | wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL,
        )
        self.list_preview.AppendColumn(_("#"), format=wx.LIST_FORMAT_LEFT, width=58)
        self.list_preview.AppendColumn(
            _("Operation"),
            format=wx.LIST_FORMAT_LEFT,
            width=95,
        )
        self.list_preview.AppendColumn(
            _("Id"), format=wx.LIST_FORMAT_LEFT, width=95
        )
        self.list_preview.AppendColumn(
            _("Label"), format=wx.LIST_FORMAT_LEFT, width=95
        )
        self.list_preview.AppendColumn(
            _("Power"), format=wx.LIST_FORMAT_LEFT, width=65
        )
        self.list_preview.AppendColumn(
            _("Speed"), format=wx.LIST_FORMAT_LEFT, width=65
        )

        result_box.Add(self.list_library_entries, 1, wx.EXPAND, 0)
        result_box.Add(self.list_preview, 1, wx.EXPAND, 0)
        self.btn_import = wx.Button(self, wx.ID_ANY, _("Import"))
        result_box.Add(self.btn_import, 0, wx.ALIGN_RIGHT, 0)

        main_sizer.Add(result_box, 1, wx.EXPAND, 0)
        self.SetSizer(main_sizer)
        self.Layout()
        self.btn_reset.Bind(wx.EVT_BUTTON, self.on_reset)
        self.btn_load.Bind(wx.EVT_BUTTON, self.on_load)
        self.combo_lasertype.Bind(wx.EVT_COMBOBOX, self.update_list)
        self.txt_material.Bind(wx.EVT_TEXT, self.update_list)
        self.list_library_entries.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_selection)
        ### TODO Look for locally cached entries...
        self.on_reset(None)
        self.enable_filter_controls()

    def on_import(self, event):
        idx = self.list_library_entries.GetFirstSelected()
        if idx >= 0:
            lib_idx = self.visible_list[idx]

    def on_reset(self, event):
        self.txt_material.SetValue("")
        self.combo_lasertype.SetSelection(0)
        self.update_list()

    def enable_filter_controls(self):
        flag = len(self.library_entries) > 0
        self.txt_material.Enable(flag)
        self.combo_lasertype.Enable(flag)
        self.btn_reset.Enable(flag)

    def on_load(self, event):
        self.library_entries.clear()
        ### TODO: Load material database from internet

        self.enable_filter_controls()
        self.update_list()

    def update_list(self, *args):
        filter_txt = self.txt_material.GetValue()
        filter_type = self.combo_lasertype.GetSelection()
        self.visible_list.clear()
        self.btn_import.Enable(False)
        self.list_library_entries.DeleteAllItems()
        for idx, entry in enumerate(self.library_entries):
            use_it = True
            if filter_txt and filter_txt not in entry[0]:
                use_it = False
            if filter_type > 0 and filter_type != entry[1]:
                use_it = False
            if use_it:
                try:
                    ltype = self.laser_choices(entry[1])
                except IndexError:
                    # Invalid...
                    continue
                self.visible_list.append(idx)
                list_id = self.list_library_entries.InsertItem(idx, f"#{idx}")
                self.list_library_entries.SetItem(list_id, 1, entry[0])
                self.list_library_entries.SetItem(list_id, 2, ltype)
                self.list_library_entries.SetItem(list_id, 3, len(entry[2]))

        if len(self.visible_list):
            self.list_library_entries.Select(0)
        self.on_selection(None)

    def on_selection(self, event):
        self.btn_import.Enable(False)
        idx = self.list_library_entries.GetFirstSelected()
        self.list_preview.DeleteAllItems()
        if idx >= 0:
            self.btn_import.Enable(True)
            lib_idx = self.visible_list[idx]
            entry = self.library_entries[lib_idx]
            for idx, op in enumerate(entry[2]):
                list_id = self.list_preview.InsertItem(idx, f"#{idx}")
                self.list_preview.SetItem(list_id, 1, op.type)
                self.list_preview.SetItem(list_id, 2, op.label)
                if hasattr(op, "power"):
                    self.list_preview.SetItem(list_id, 3, op.power)
                if hasattr(op, "speed"):
                    self.list_preview.SetItem(list_id, 4, op.speed)

    def set_parent(self, par_panel):
        self.parent_panel = par_panel


class AboutPanel(wx.Panel):
    def __init__(self, *args, context=None, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.TAB_TRAVERSAL
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        info_box = StaticBoxSizer(self, wx.ID_ANY, _("How to use..."), wx.VERTICAL)
        self.parent_panel = None
        s = self.context.asset("material_howto")
        info_label = wx.TextCtrl(
            self, wx.ID_ANY, value=s, style=wx.TE_READONLY | wx.TE_MULTILINE
        )
        font = wx.Font(
            10,
            wx.FONTFAMILY_TELETYPE,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL,
        )
        info_label.SetFont(font)
        info_label.SetBackgroundColour(self.GetBackgroundColour())
        info_box.Add(info_label, 1, wx.EXPAND, 0)
        main_sizer.Add(info_box, 1, wx.EXPAND, 0)
        self.SetSizer(main_sizer)
        self.Layout()

    def set_parent(self, par_panel):
        self.parent_panel = par_panel


class MaterialManager(MWindow):
    def __init__(self, *args, **kwds):
        super().__init__(500, 530, *args, **kwds)

        self.panel_library = MaterialPanel(self, wx.ID_ANY, context=self.context)
        self.panel_import = ImportPanel(self, wx.ID_ANY, context=self.context)
        self.panel_about = AboutPanel(self, wx.ID_ANY, context=self.context)

        self.panel_library.set_parent(self)
        self.panel_import.set_parent(self)
        self.panel_about.set_parent(self)

        _icon = wx.NullIcon
        _icon.CopyFromBitmap(icon_library.GetBitmap())
        self.SetIcon(_icon)
        self.notebook_main = wx.aui.AuiNotebook(
            self,
            -1,
            style=wx.aui.AUI_NB_TAB_EXTERNAL_MOVE
            | wx.aui.AUI_NB_SCROLL_BUTTONS
            | wx.aui.AUI_NB_TAB_SPLIT
            | wx.aui.AUI_NB_TAB_MOVE,
        )
        self.notebook_main.AddPage(self.panel_library, _("Library"))
        self.notebook_main.AddPage(self.panel_import, _("Import"))
        self.notebook_main.AddPage(self.panel_about, _("How to use"))
        # begin wxGlade: Keymap.__set_properties
        self.DragAcceptFiles(True)
        self.Bind(wx.EVT_DROP_FILES, self.on_drop_file)
        self.SetTitle(_("Material Library"))

    def on_drop_file(self, event):
        """
        Drop file handler
        Accepts only a single file drop.
        """
        for pathname in event.GetFiles():
            if self.panel_import.import_csv(pathname):
                break

    def delegates(self):
        yield self.panel_library
        yield self.panel_import
        yield self.panel_about

    @staticmethod
    def sub_register(kernel):
        kernel.register(
            "button/config/Material",
            {
                "label": _("Material Library"),
                "icon": icon_library,
                "tip": _("Manages Material Settings"),
                "help": "materialmanager",
                "action": lambda v: kernel.console("window toggle MatManager\n"),
            },
        )

    def window_open(self):
        pass

    def window_close(self):
        pass

    def edit_message(self, msg):
        self.panel_library.edit_message(msg)

    def populate_gui(self):
        self.panel_library.populate_gui()

    @staticmethod
    def submenu():
        # Suppress to avoid double menu-appearance
        return "", "Material Library", True