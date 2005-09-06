#!/usr/bin/python
COPYRIGHT = """Copyright (c) 2005 Chris McDonough and Contributors.
All Rights Reserved."""

LICENSE = """\
This software is subject to the provisions of the Zope Public License,
Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
FOR A PARTICULAR PURPOSE."""

import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import gnome
import gnome.ui
import gobject
import time
import os
import pickle
import sys
import socket

here = os.path.abspath(os.path.split(__file__)[0])

VERSION = '0.4'
AUTHORS = ['Chris McDonough (chrism@plope.com)']
WEBSITE = 'http://www.plope.com/software/wfyd'

ISO = "%Y-%m-%d %H:%M:%S"

class MainWindow(object):
    
    def __init__(self, datafile):
        if os.path.exists(datafile):
            self.root = pickle.load(open(datafile))
        else:
            self.root = Root()
        gnome.init('WFYD', VERSION)
        self.wtree = gtk.glade.XML(os.path.join(here, 'wfyd.glade'))
        self.window = self.wtree.get_widget('main')
        #gnome.ui.window_icon_set_from_default(self.window)
        self.window.set_icon_from_file(os.path.join(here, 'resources',
                                                    'wfyd-32x32.png'))
        self.start_time = None
        init_signals(self, self.wtree.signal_autoconnect)
        self.entrytree_widget = EntryTree(self.wtree, self.root)
        self.preferences = PreferencesWindow(self.wtree, self.root)
        self.projectbox = self.wtree.get_widget('projectbox')
        self.gobutton = self.wtree.get_widget('gobutton')
        self.gobutton_set_add()
        self.refresh_projectbox()

        # can't see projectbox child in glade, so need to connect signal here
        self.projectbox.get_child().connect('changed',
                                            self.on_projectbox_entry_changed)

        #self.projectbox.set_active(0)
        self.nagging = False
        self.last_nag_time = time.time()
        self.nag_id = gobject.timeout_add(1000, self.nag_cb)

    def on_main_destroy(self, *args):
        self.root.save()
        gtk.main_quit()

    def gobutton_set_add(self):
        widget = self.gobutton
        alignment = widget.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        #image.set_from_file(os.path.join(here, 'resources', 'record.png'))

        image.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        label.set_text('Add   ')
        # cold do something like this instead but above is easier
        #icon_theme = gtk.icon_theme_get_default()
        #pixbuf = icon_theme.load_icon('Add', 24, 0)
        #image.set_from_pixbuf(pixbuf)

    def gobutton_set_stop(self):
        widget = self.gobutton
        alignment = widget.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        #image.set_from_file(os.path.join(here, 'resources', 'record.png'))

        image.set_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON)
        label.set_text('Stop  ')
        # cold do something like this instead but above is easier
        #icon_theme = gtk.icon_theme_get_default()
        #pixbuf = icon_theme.load_icon('Add', 24, 0)
        #image.set_from_pixbuf(pixbuf)

        # or an animation
        #anim = os.path.join(here, 'resources', 'smallgears.gif')
        #pixbufanim = gtk.gdk.PixbufAnimation(anim)
        #image.set_from_animation(pixbufanim)
        #image.set_from_file(os.path.join(here, 'resources', 'stop.png'))


    def on_gobutton_toggled(self, widget):
        projectbox = self.wtree.get_widget('projectbox')
        projectname = projectbox.get_child().get_text().strip()

        if widget.get_active():
            if not projectname:
                widget.set_active(False)
                self.change_status('You must choose or create a project in '
                                   'the dropdown to start an entry.')
                return
            self.change_status('')
            self.start_time = int(time.time())
            self.gobutton_set_stop()
            self.source_id = gobject.timeout_add(100, self.gobutton_refresh_cb)
        else:
            if not projectname:
                return
            assert self.start_time is not None
            gobject.source_remove(self.source_id)
            self.source_id = None
            end_time = time.time()
            seconds = int((end_time - self.start_time))
            notesbox = self.wtree.get_widget('notesbox')
            buffer = notesbox.get_buffer()
            start, end = buffer.get_bounds()
            text = buffer.get_text(start, end)
            project = self.root.get_or_create(projectname)
            project.add_entry(self.start_time, self.start_time + seconds,
                              text)
            self.root.save()
            notesbox.set_buffer(gtk.TextBuffer())
            self.start_time = None
            self.refresh_projectbox()
            self.gobutton_set_add()
        self.change_status('')
        self.entrytree_widget.refresh(projectname)

    def on_projectbox_entry_changed(self, entrybox):
        projectname = entrybox.get_text().strip()
        if self.root.get(projectname):
            self.entrytree_widget.refresh(projectname)

    def on_projectbox_changed(self, projectbox):
        entrybox = projectbox.get_child()
        return self.on_projectbox_entry_changed(entrybox)

    def on_projectbox_editing_done(self, *args):
        print args

    def on_deleteprojectbutton_clicked(self, button):
        projectbox = self.wtree.get_widget('projectbox')
        projectname = projectbox.get_child().get_text().strip()
        if not projectname:
            return
        window = button.get_toplevel()
        dia = gtk.Dialog('Delete Project',
                 window,  #the toplevel wgt of your app
                 gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,  
                 (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                  gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
        dia.set_transient_for(window)
        dia.vbox.pack_start(gtk.Label('    Deleting a project will delete\n'
                                      'its associated entries, are you sure?'))
        dia.show_all()
        result = dia.run()
        if result in (gtk.RESPONSE_CLOSE, gtk.RESPONSE_REJECT):
            pass
        elif result == gtk.RESPONSE_ACCEPT:
            self.root.remove(projectname)
            self.root.save()
            self.refresh_projectbox()
        dia.destroy()

    def on_notesbox_key_press_event(self, *args):
        gobutton = self.wtree.get_widget('gobutton')
        active = gobutton.get_active()
        if not gobutton.get_active():
            gobutton.set_active(True)
            self.on_gobutton_toggled(gobutton)
        self.change_status('')

    def on_quit1_activate(self, *args):
        self.root.save()
        gtk.main_quit()

    def on_export_to_ical1_activate(self, *args):
        dialog = gtk.FileSelection("Export vCal file..")
        dialog.set_filename('wfyd.vcs')
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.export_vcal(filename)
        dialog.destroy()

    def on_about1_activate(self, *args):
        dialog = gtk.AboutDialog()
        dialog.set_version(VERSION)
        dialog.set_authors(AUTHORS)
        dialog.set_copyright(COPYRIGHT)
        dialog.set_license(LICENSE)
        dialog.set_website(WEBSITE)
        dialog.set_comments('A simple time tracker for GNOME')
        dialog.run()
        dialog.destroy()

    def on_preferences1_activate(self, *args):
        self.preferences.display()

    def on_contents1_activate(self, *args):
        # frameworkitis has consumed the help system api, so let's avoid that
        # by calling yelp directly
        helpfile = os.path.join(here, 'doc', 'wfyd.xml')
        os.spawnvpe(os.P_NOWAIT, 'yelp', ['yelp', helpfile], os.environ)

    # callbacks

    def gobutton_refresh_cb(self):
        alignment = self.gobutton.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        if self.start_time:
            label.set_text(minutes_repr(time.time() - self.start_time)+ ' ')
        # must return True to reschedule
        return True
        
    def nag_cb(self):
        window = self.window
        nag_interval = self.root.get_option('nag_interval', None)
        if not nag_interval:
            return
        if self.last_nag_time + (nag_interval * 60) < time.time():
            self.nagging = True
            self.last_nag_time = time.time()
            self.change_status('Nagging')
            window.present()
        return True

    # utility methods

    def refresh_projectbox(self):
        projectbox = self.projectbox
        active = projectbox.get_active()
        listlen = len(projectbox.get_model())

        completion = gtk.EntryCompletion()
        completion_liststore = gtk.ListStore(str)

        for n in range(listlen):
            projectbox.remove_text(0)

        projectnames = self.root.get_projectnames()

        for projectname in projectnames:
            projectbox.append_text(projectname)
            completion_liststore.append([projectname])

        completion.set_model(completion_liststore)
        projectbox.get_child().set_completion(completion)
        completion.set_text_column(0)

        numprojects = len(projectnames)

        if active > numprojects:
            active = 0

        if not numprojects:
            projectbox.get_child().set_text('')
            self.entrytree_widget.clear()

        projectbox.set_active(active)

    def change_status(self, status):
        appbar = self.wtree.get_widget('appbar1')
        statusframe = appbar.get_children()[0]
        label = statusframe.get_children()[0]
        label.set_text(status)

    def export_vcal(self, filename):
        f = open(filename, 'w')
        f.write("BEGIN:VCALENDAR\n")
        f.write("PRODID:-//plope.com/NONSGML WFYD//EN\n")
        f.write("VERSION:2.0\n")
        idhost = socket.getfqdn()
        dtstamp = time.strftime("%Y%m%dT%H%M%SZ", time.localtime(time.time()))
        for projectname in self.root.get_projectnames():
            project = self.root.get(projectname)
            for entry in project.get_entries():
                b = time.strftime('%Y%m%dT%H%M%S',time.localtime(entry.begin))
                e = time.strftime('%Y%m%dT%H%M%S', time.localtime(entry.end))
                notes = (entry.notes.replace('\\', '\\\\')
                         .replace(';', '\\;')
                         .replace(',', '\\,')
                         .replace('\r', '')
                         .replace('\n', '  '))
                f.write("BEGIN:VEVENT\n")
                f.write("UID:%s@%s\n" % (hash((b, e, notes)), idhost))
                f.write("SUMMARY:[%s] %s\n" % (projectname, notes))
                f.write("DTSTART:%s\n" % b)
                f.write("DTEND:%s\n" % e)
                f.write("DTSTAMP:%s\n" % dtstamp)
                f.write("END:VEVENT\n")
        f.write("END:VCALENDAR\n")
        f.close()

class EntryTree(object):
    def __init__(self, wtree, root):
        self.wtree = wtree
        self.root = root
        self.projectbox = self.wtree.get_widget('projectbox')
        self.entrytree = self.wtree.get_widget('entrytree')
        self.entrytree.set_rules_hint(True) # alternating colors
        treeselection = self.entrytree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        self.store = gtk.ListStore(gobject.TYPE_INT,    # time.time() date
                                   gobject.TYPE_STRING, # date repr
                                   gobject.TYPE_INT,    # int seconds
                                   gobject.TYPE_STRING, # repr in minutes
                                   gobject.TYPE_STRING  # notes
                                   )
        self.store.set_sort_column_id(0, gtk.SORT_DESCENDING)
        self.entrytree.set_model(self.store)

        col = gtk.TreeViewColumn('Date', gtk.CellRendererText(), text=1)
        col.set_sort_column_id(0)
        col.set_resizable(True)
        self.entrytree.append_column(col)

        col = gtk.TreeViewColumn('Time', gtk.CellRendererText(), text=3)
        col.set_sort_column_id(2)
        col.set_resizable(True)
        self.entrytree.append_column(col)

        col = gtk.TreeViewColumn('Notes', gtk.CellRendererText(), text=4)
        col.set_sort_column_id(4)
        col.set_resizable(True)
        self.entrytree.append_column(col)

        self.entrytree.set_property('headers-visible', True)
        self.entrytree.set_search_column(4)
        self.entrytree.set_search_equal_func(self.notes_search)
        projectbox = self.wtree.get_widget('projectbox')
        self.editwindow = EntryEditWindow(self)
        init_signals(self, self.wtree.signal_autoconnect)

    def clear(self):
        self.store.clear()

    def refresh(self, projectname):
        self.store.clear()
        if not projectname:
            return
        project = self.root.get_or_create(projectname)
        for entry in project.get_entries():
            begin = int(entry.begin)
            duration = int(entry.end - entry.begin)
            iter = self.store.append()
            self.store.set_value(iter, 0, entry.begin)
            self.store.set_value(iter, 1, time.strftime(ISO,
                                                        time.localtime(begin)))
            self.store.set_value(iter, 2, duration)
            self.store.set_value(iter, 3, minutes_repr(duration))
            self.store.set_value(iter, 4, entry.notes)

    def on_entrytree_button_press_event(self, view, event):
        if event.button != 3:
            # right button
            return
        count = self.entrytree.get_selection().count_selected_rows()
        if count < 1:
            return True
        elif count == 1:
            popup = self.wtree.get_widget('entry_rightclick_popup')
        elif count > 1:
            popup = self.wtree.get_widget('entry_rightclick_popup_multi')
        popup.popup(None, None, None, event.button, event.time)
        return True

    def on_edit_entry_activate(self, *args):
        self.editwindow.display()

    def on_entry_delete_activate(self, menuitem):
        model, paths = self.entrytree.get_selection().get_selected_rows()
        iters = [ model.get_iter(path) for path in paths ]
        for iter in iters:
            self.delete_entry_row(model, iter)

    def delete_entry_row(self, store, iter):
        time = store.get_value(iter, 0)
        projectname = self.projectbox.get_child().get_text().strip()
        project = self.root.get(projectname)
        if not project:
            return
        n = 0
        for entry in project.get_entries():
            if time == entry.begin:
                project.remove_entry(n)
            n+=1
        store.remove(iter)
        self.root.save()

    def on_entrytree_row_activated(self, *args):
        self.editwindow.display()

    def notes_search(self, model, column_num, searchstring, rowiter, d=None):
        # this is less than ideal because it's not an incremental search
        text = model.get_value(rowiter, column_num)
        if text.find(searchstring) != -1:
            return False # this means it was found
        return True

class EntryEditWindow(object):
    def __init__(self, parent):
        self.wtree = parent.wtree
        self.root = parent.root
        self.store = parent.store
        self.entrytree = parent.entrytree
        self.projectbox = parent.projectbox
        self.parent = parent
        self.window = self.wtree.get_widget('entry_edit')
        self.datebox = self.wtree.get_widget('date_edit_box')
        self.minutebox = self.wtree.get_widget('minutes_edit_box')
        self.notesbox   = self.wtree.get_widget('notes_edit_box')
        init_signals(self, self.wtree.signal_autoconnect)
    
    def display(self):
        store, paths = self.entrytree.get_selection().get_selected_rows()
        path = paths[0]
        iter = store.get_iter(path)
        start = store.get_value(iter, 0)
        minutes = store.get_value(iter, 2) / 60
        notes = store.get_value(iter, 4)
        self.datebox.set_time(start)
        self.minutebox.set_value(minutes)
        self.notesbox.get_buffer().set_text(notes)
        self.window.set_transient_for(self.entrytree.get_toplevel())
        self.window.show_all()

    def hide(self):
        self.window.hide()

    def on_entry_edit_cancel_clicked(self, *args):
        self.hide()

    def on_entry_edit_apply_clicked(self, *args):
        begin = int(self.datebox.get_time())
        seconds = int(self.minutebox.get_value() * 60)
        buffer = self.notesbox.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end)
        store, paths = self.entrytree.get_selection().get_selected_rows()
        path = paths[0]
        iter = store.get_iter(path)
        oldbegin = self.store.get_value(iter, 0)
        projectname = self.projectbox.get_child().get_text().strip()
        project = self.root.get(projectname)

        if not project:
            return 

        n = 0
        for entry in project.get_entries():
            if oldbegin == entry.begin:
                entry.begin = begin
                entry.end = begin + seconds
                entry.set_notes(text)
            n+=1

        self.root.save()
        self.hide()
        self.parent.refresh(projectname)

    def on_entry_edit_delete_event(self, *args):
        self.hide()
        return True # dont allow this window to be destroyed

class PreferencesWindow(object):
    def __init__(self, wtree, root):
        self.wtree = wtree
        self.root = root
        self.window = self.wtree.get_widget('prefs')
        self.nag_interval = self.wtree.get_widget('nag_interval')
        init_signals(self, self.wtree.signal_autoconnect)

    def display(self):
        self.nag_interval.set_value(self.root.get_option('nag_interval', 0))
        self.window.set_transient_for(self.wtree.get_widget('main'))
        self.window.show_all()

    def hide(self):
        self.window.hide()

    def on_prefs_ok_clicked(self, *args):
        self.root.set_option('nag_interval', self.nag_interval.get_value())
        self.root.save()
        self.hide()

    def on_prefs_cancel_clicked(self, *args):
        self.hide()

    def on_prefs_delete_event(self, *args):
        self.hide()
        return True # dont allow this window to be destroyed

def minutes_repr(seconds):
    minutes = seconds / 60
    hours = minutes / 60
    minutes = minutes - (hours * 60)
    return '%02d:%02d' % (hours, minutes)

def init_signals(instance, cb):
    dict = {}
    for k in instance.__class__.__dict__:
        if k.startswith('on_'):
            dict[k] = getattr(instance, k)
    cb(dict)


# persistent objects

class Root(object):
    options = None
    
    def __init__(self):
        self.projects = {}
        self.categories = {}
        self.options = {}
        
    def get(self, projectname):
        return self.projects.get(projectname)

    def get_or_create(self, projectname):
        if self.get(projectname) is None:
            project = Project(projectname)
            self.projects[projectname] = project
            return project
        return self.projects[projectname]

    def get_projectnames(self):
        names = self.projects.keys()
        names.sort(lambda a, b: cmp(a.lower(), b.lower()))
        return names

    def add(self, projectname):
        self.projects[projectname] = Project(projectname)

    def remove(self, projectname):
        if self.projects.get(projectname) is not None:
            del self.projects[projectname]

    def save(self):
        pickle.dump(self, open(datafile, 'w'))

    def set_option(self, name, value):
        if self.options is None:
            self.options = {}
        self.options[name] = value

    def get_option(self, name, default):
        return self.options.get(name, default)

class Project(object):
    def __init__(self, name):
        self.entries = []
        self.name = name

    def add_entry(self, start, stop, notes):
        entry = Entry()
        entry.start(start)
        entry.set_notes(notes)
        entry.stop(stop)
        self.entries.append(entry)

    def remove_entry(self, num):
        del self.entries[num]

    def get_entries(self):
        return self.entries

class Entry(object):
    def __init__(self):
        self.notes = ''
        self.begin = None
        self.end = None

    def set_notes(self, notes):
        self.notes = notes

    def stop(self, when=None):
        if when is None:
            self.end = time.time()
        else:
            self.end = when

    def start(self, when=None):
        if when is None:
            self.begin = time.time()
        else:
            self.begin = when

if __name__ == '__main__':
    try:
        datafile = sys.argv[1]
    except IndexError:
        datafile = os.path.expanduser('~/.wfyd.dat')
    app = MainWindow(datafile)
    try:
        gtk.main()
    except KeyboardInterrupt:
        pass
    

                                         
