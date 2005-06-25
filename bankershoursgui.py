#!/usr/bin/python
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

VERSION = '0.1'
AUTHORS = ['Chris McDonough (chrism@plope.com)']
COPYRIGHT = AUTHORS[0]

datafile = os.path.expanduser('~/.bankershours.dat')

ISO = "%Y-%m-%d %H:%M:%S"

class GUI(object):
    store = None
    recording = None
    
    def __init__(self):
        if os.path.exists(datafile):
            self.root = pickle.load(open(datafile))
        else:
            self.root = Root()
        gnome.init('bankershours', VERSION)
        self.wtree = gtk.glade.XML('bankershours.glade')
        window = self.wtree.get_widget('main')
        gnome.ui.window_icon_set_from_default(window)
        self.start_time = None
        self.signal_init()
        self.projectbox_init()
        self.projectbox.set_active(0)
        self.entrytree_init()

    def signal_init(self):
        dict = {}
        for k in self.__class__.__dict__:
            if k.startswith('on_'):
                dict[k] = getattr(self, k)
        self.wtree.signal_autoconnect(dict)

    def projectbox_init(self):
        self.projectbox = self.wtree.get_widget('projectbox')
        self.refresh_projectbox(self.projectbox)
        self.projectbox.get_child().connect('changed',
                                            self.on_projectbox_entry_changed)

    def entrytree_init(self):
        self.entrytree = self.wtree.get_widget('entrytree')
        entrytree = self.entrytree
        entrytree.set_rules_hint(True)
        self.store = gtk.ListStore(gobject.TYPE_INT,    # time.time() date
                                   gobject.TYPE_STRING, # date repr
                                   gobject.TYPE_INT,    # int seconds
                                   gobject.TYPE_STRING, # repr in minutes
                                   gobject.TYPE_STRING  # notes
                                   )
        self.store.set_sort_column_id(0, gtk.SORT_DESCENDING)
        entrytree.set_model(self.store)

        col = gtk.TreeViewColumn('Date', gtk.CellRendererText(), text=1)
        col.set_sort_column_id(0)
        col.set_resizable(True)
        entrytree.append_column(col)

        col = gtk.TreeViewColumn('Time', gtk.CellRendererText(), text=3)
        col.set_sort_column_id(2)
        col.set_resizable(True)
        entrytree.append_column(col)

        col = gtk.TreeViewColumn('Notes', gtk.CellRendererText(), text=4)
        col.set_sort_column_id(4)
        col.set_resizable(True)
        entrytree.append_column(col)

        entrytree.set_property('headers-visible', True)
        projectbox = self.wtree.get_widget('projectbox')
        self.refresh_entrytree(self.store, projectbox.get_child())

    # signal handlers

    def on_main_destroy(self, *args):
        self.root.save()
        gtk.main_quit()

    def on_gobutton_toggled(self, widget):
        if widget.get_active():
            self.start_time = int(time.time())
            self.source_id = gobject.timeout_add(
                1000, self.refresh_gobutton, widget
                )
            notesbox = self.wtree.get_widget('notesbox')
        else:
            assert self.start_time is not None
            gobject.source_remove(self.source_id)
            self.source_id = None
            alignment = widget.get_children()[0]
            hbox = alignment.get_children()[0]
            image, label = hbox.get_children()
            label.set_text('Start')
            end_time = time.time()
            seconds = int((end_time - self.start_time))
            projectbox = self.wtree.get_widget('projectbox')
            projectname = projectbox.get_child().get_text()
            notesbox = self.wtree.get_widget('notesbox')
            buffer = notesbox.get_buffer()
            start, end = buffer.get_bounds()
            text = buffer.get_text(start, end)
            project = self.root.get_or_create(projectname)
            project.add_entry(self.start_time, self.start_time + seconds,
                              text)
            notesbox.set_buffer(gtk.TextBuffer())
            self.start_time = None
            self.refresh_projectbox(projectbox)
        self.refresh_entrytree(self.store, self.projectbox.get_child())

    def on_entrytree_row_activated(self):
        print "row activated"

    def on_entrytree_button_press_event(self, view, event):
        if event.button != 3:
            # right button
            return
        popup = self.wtree.get_widget('entry_rightclick_popup')
        popup.popup(None, None, None, event.button, event.time)

    def on_edit_entry_activate(self, *args):
        print "on_edit_entry_activate called with args %s" % str(args)

    def on_entry_delete_activate(self, menuitem):
        store, iter = self.entrytree.get_selection().get_selected()
        time = store.get_value(iter, 0)
        projectname = self.projectbox.get_child().get_text()
        project = self.root.get(projectname)
        if not project:
            return
        n = 0
        for entry in project.get_entries():
            if time == entry.begin:
                project.remove_entry(n)
            n+=1
        store.remove(iter)

    def on_projectbox_entry_changed(self, entrybox):
        text = entrybox.get_text()
        if self.root.get(text) and self.store is not None:
            self.refresh_entrytree(self.store, entrybox)

    def on_projectbox_changed(self, projectbox):
        if self.store is not None:
            entrybox = projectbox.get_child()
            if self.root.get(entrybox.get_text()):
                self.refresh_entrytree(self.store, entrybox)

    def on_projectbox_editing_done(self, *args):
        print args

    def on_deleteprojectbutton_clicked(self, button):
        projectbox = self.wtree.get_widget('projectbox')
        projectname = projectbox.get_child().get_text()
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
            try:
                self.root.remove(projectname)
            except KeyError:
                pass
            self.refresh_projectbox(projectbox)
        self.root.save()
        dia.destroy()

    def on_delete_project_dialog_response(self, *args):
        print args

    def on_notesbox_key_press_event(self, *args):
        gobutton = self.wtree.get_widget('gobutton')
        active = gobutton.get_active()
        if not gobutton.get_active():
            gobutton.set_active(True)
            self.on_gobutton_toggled(gobutton)

    def on_quit1_activate(self, *args):
        self.root.save()
        gtk.main_quit()

    def on_about1_activate(self, *args):
        dialog = gtk.AboutDialog()
        dialog.set_version(VERSION)
        dialog.set_authors(AUTHORS)
        dialog.set_copyright(COPYRIGHT)
        dialog.run()
        dialog.destroy()

    # utility methods

    def refresh_gobutton(self, widget):
        alignment = widget.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        #image.set_from_icon_name('', gtk.ICON_SIZE_BUTTON)
        if self.start_time:
            label.set_text(minutes_repr(time.time() - self.start_time))
        return True
        
    def refresh_projectbox(self, projectbox):
        active = projectbox.get_active()
        listlen = len(projectbox.get_model())
            
        for n in range(listlen):
            projectbox.remove_text(0)

        for projectname in self.root.get_projectnames():
            projectbox.append_text(projectname)

        projectbox.set_active(active)

    def refresh_entrytree(self, store, projectentry):
        store.clear()
        projectname = projectentry.get_text()
        if not projectname:
            return
        project = self.root.get_or_create(projectname)
        for entry in project.get_entries():
            begin = int(entry.begin)
            duration = int(entry.end - entry.begin)
            iter = self.store.append()
            store.set_value(iter, 0, entry.begin)
            store.set_value(iter, 1, time.strftime(ISO, time.gmtime(begin)))
            store.set_value(iter, 2, duration)
            store.set_value(iter, 3, minutes_repr(duration))
            store.set_value(iter, 4, entry.notes)

def minutes_repr(seconds):
    minutes = seconds / 60
    hours = minutes / 60
    return '%02d:%02d' % (hours, minutes)

class Root(object):
    def __init__(self):
        self.projects = {}
        self.categories = {}
        self.projectname = None
        
    def get(self, projectname):
        return self.projects.get(projectname)

    def get_or_create(self, projectname):
        if self.get(projectname) is None:
            project = Project(projectname)
            self.projects[projectname] = project
            return project
        return self.projects[projectname]

    def get_projectnames(self):
        return self.projects.keys()

    def add(self, projectname):
        self.projects[projectname] = Project(projectname)

    def remove(self, projectname):
        if self.projects.get(projectname) is not None:
            del self.projects[projectname]
            if self.projectname == projectname:
                self.projectname = None

    def save(self):
        pickle.dump(self, open(datafile, 'w'))

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
    app = GUI()
    try:
        gtk.main()
    except KeyboardInterrupt:
        pass
    

                                         
