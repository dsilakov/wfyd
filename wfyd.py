#!/usr/bin/python
COPYRIGHT = """Copyright (c) 2005-2009 Chris McDonough, Denis Silakov and Contributors.
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
import datetime
import os
import sys
import calendar
import socket
try:
    from pysqlite2 import dbapi2 as sqlite
except:
    from sqlite3 import dbapi2 as sqlite
#~
try:
    from pkg_resources import resource_filename
except ImportError:
    here = os.path.abspath(os.path.split(__file__)[0])
    GLADE_TREE = os.path.join(here, 'wfyd.glade')
    WINDOW_ICON = os.path.join(here, 'resources', 'wfyd-32x32.png')
    RECORD_ICON = os.path.join(here, 'resources', 'record.png')
    SMALLGEARS_ANIM = os.path.join(here, 'resources', 'smallgears.gif')
    STOP_ICON = os.path.join(here, 'resources', 'stop.png')
    HELPFILE = os.path.join(here, 'doc', 'wfyd.xml')
else:
    GLADE_TREE = resource_filename(__name__, 'wfyd.glade')
    WINDOW_ICON = resource_filename(__name__, 'resources/wfyd-32x32.png')
    RECORD_ICON = resource_filename(__name__, 'resources/record.png')
    SMALLGEARS_ANIM = resource_filename(__name__, 'resources/smallgears.gif')
    STOP_ICON = resource_filename(__name__, 'resources/stop.png')
    HELPFILE = resource_filename(__name__, 'doc/wfyd.xml')

VERSION = '0.8'
AUTHORS = ['Chris McDonough (chrism@plope.com)',
           'Denis Silakov (d_uragan@rambler.ru)',
           'Tres Seaver (tseaver@palladion.com)',
          ]
WEBSITE = 'http:///wfyd.sourceforge.net'

ISO = "%Y-%m-%d %H:%M:%S"

dbfile = None

class MainWindow(object):

    def __init__(self):
        # Even if dbfile is not exists, it will be created
        con = sqlite.connect(dbfile)
        cur = con.cursor()
        self.root = Root()

        self.current_task_id = 0;
        self.task_running = 0;

        # If we are creating dbfile from scratch - create necesary tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects
            (
                project_id        integer           PRIMARY KEY AUTOINCREMENT,
                project_name      varchar(255)      UNIQUE,
                last_used         integer
            )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks
            (
                task_id          integer               PRIMARY KEY AUTOINCREMENT,
                project_id       integer,
                task_name        varchar(255),
                time_start       timestamp,
                time_finish      timestamp,
                UNIQUE           (project_id, task_name, time_start)
            )
            """)

        # correct possible inconsistencies that can occur in the db after unexpected crashes
        cur.execute("UPDATE tasks SET time_finish = current_timestamp WHERE time_finish < time_start")
        con.commit()

        gnome.init('WFYD', VERSION)
        self.wtree = gtk.glade.XML(GLADE_TREE)
        self.window = self.wtree.get_widget('main')
        #gnome.ui.window_icon_set_from_default(self.window)
        self.window.set_icon_from_file(os.path.join(WINDOW_ICON))
        self.start_time = None
        init_signals(self, self.wtree.signal_autoconnect)
        self.entrytree_widget = EntryTree(self.wtree, self.root)
        self.preferences = PreferencesWindow(self.wtree, self.root)
        self.projectbox = self.wtree.get_widget('projectbox')
        self.journals = JournalsWindow(self.wtree, self.root)
        self.journaltree_widget = JournalTree(self.wtree, self.root)
        self.gobutton = self.wtree.get_widget('gobutton')
        self.statusbar = self.wtree.get_widget('appbar1')
        self.gobutton_set_add()
        self.refresh_projectbox()

        # can't see projectbox child in glade, so need to connect signal here
        self.projectbox.get_child().connect('changed',
                                            self.on_projectbox_entry_changed)

        #self.projectbox.set_active(0)
        self.nagging = False
        self.last_nag_time = time.time()
        self.nag_id = gobject.timeout_add(1000, self.nag_cb)

        projectbox = self.wtree.get_widget('projectbox')
        cur.execute("SELECT project_name, project_id FROM projects ORDER BY project_id")
        for row in cur:
            projectbox.append_text(row[0])
            self.root.projects[row[0]] = Project(row[0])
            # project entries are filed with tasks for the last day only
            cur_tasks = con.cursor()
            cur_tasks.execute("""
                    SELECT task_name, strftime('%s', time_start), strftime('%s', time_finish) FROM tasks
                    WHERE time_start >= (SELECT MAX(date(time_start)) FROM tasks) AND project_id=""" + str(row[1]))
            for row_tasks in cur_tasks:
                self.root.projects[row[0]].add_entry(row_tasks[1], row_tasks[2], row_tasks[0])


    def on_main_destroy(self, *args):
        self.root.save()
        gtk.main_quit()

    def gobutton_set_add(self):
        widget = self.gobutton
        alignment = widget.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        #image.set_from_file(RECORD_ICON)

        image.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        label.set_text('Add   ')
        # could do something like this instead but above is easier
        #icon_theme = gtk.icon_theme_get_default()
        #pixbuf = icon_theme.load_icon('Add', 24, 0)
        #image.set_from_pixbuf(pixbuf)

    def gobutton_set_stop(self):
        widget = self.gobutton
        alignment = widget.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        #image.set_from_file(RECORD_ICON)

        image.set_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON)
        label.set_text('Stop  ')
        # could do something like this instead but above is easier
        #icon_theme = gtk.icon_theme_get_default()
        #pixbuf = icon_theme.load_icon('Add', 24, 0)
        #image.set_from_pixbuf(pixbuf)

        # or an animation
        #pixbufanim = gtk.gdk.PixbufAnimation(SMALLGEARS_ANIM)
        #image.set_from_animation(pixbufanim)
        #image.set_from_file(STOP_ICON)

    def on_gobutton_toggled(self, widget):
        projectbox = self.wtree.get_widget('projectbox')
        projectname = projectbox.get_child().get_text().strip()

        con = sqlite.connect(dbfile)
        cur = con.cursor()

        if widget.get_active():
            # New task is being started
            if not projectname:
                widget.set_active(False)
                self.change_status('You must choose or create a project in '
                                   'the dropdown to start an entry.')
                return
            self.change_status('')
            self.start_time = int(time.time())
            self.gobutton_set_stop()
            self.source_id = gobject.timeout_add(100, self.gobutton_refresh_cb)

            if self.task_running == 0:
                cur.execute("SELECT COUNT(*) FROM projects WHERE project_name='" + projectname + "' ")
                project_cnt = cur.fetchone()[0]
                if project_cnt == 0:
                    cur.execute("SELECT MAX(project_id) FROM projects")
                    project_id = str(cur.fetchone()[0])
                    if project_id == "None":
                        project_id = 0
                    else:
                        project_id = int(project_id)+1
                    cur.execute("INSERT INTO projects VALUES( " + str(project_id) + ", '" + projectname + "', 1) ")
                else:
                    cur.execute("SELECT project_id FROM projects WHERE project_name='" + projectname + "' ")
                    project_id = cur.fetchone()[0]

                cur.execute("SELECT MAX(task_id) FROM tasks")
                self.current_task_id = str(cur.fetchone()[0])
                if self.current_task_id == "None":
                    self.current_task_id = 0
                else:
                    self.current_task_id = int(self.current_task_id)
                self.current_task_id+=1
                cur.execute("INSERT INTO tasks VALUES(" + str(self.current_task_id) + ", " + str(project_id) + ", '',  current_timestamp, 0)" )
                con.commit()
                cur.execute("SELECT MAX(task_id) FROM tasks")
                self.task_running = 1
        else:
            # Running task is being finished
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
            notesbox.set_buffer(gtk.TextBuffer())
            self.start_time = None
            self.refresh_projectbox()
            self.gobutton_set_add()

            sql_stmt = "UPDATE tasks SET task_name= '" + text.replace("'","''") + "', "
            sql_stmt+= "  time_finish = current_timestamp "
            sql_stmt+= "WHERE task_id = " + str(self.current_task_id)

            cur.execute(sql_stmt)
            con.commit()
            self.task_running = 0

        self.change_status('')
        self.entrytree_widget.refresh(projectname)
        self.journaltree_widget.refresh(projectname)

    def on_projectbox_entry_changed(self, entrybox):
        projectname = entrybox.get_text().strip()
        if self.root.get(projectname):
            self.entrytree_widget.refresh(projectname)
            self.journaltree_widget.refresh(projectname)
#          self.root.cur_project = projectname

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
            self.refresh_projectbox()
            self.projectbox.get_child().set_text('')
            con = sqlite.connect(dbfile)
            cur = con.cursor()
            cur.execute("DELETE FROM tasks WHERE project_id IN (SELECT project_id FROM projects WHERE project_name='" + projectname + "')")
            cur.execute("DELETE FROM projects WHERE project_name = '" + projectname +"'" )
            con.commit()
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

    def on_export_to_text1_activate(self, *args):
        dialog = gtk.FileSelection("Export text file..")
        dialog.set_filename('wfyd.txt')
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.export_text(filename)
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

    def on_journals_clicked(self, *args):
        projectbox = self.wtree.get_widget('projectbox')
        projectname = projectbox.get_child().get_text().strip()
        self.journaltree_widget.finish_time = int(time.time())
        self.journaltree_widget.refresh(projectname)
        self.journals.display()

    def on_contents1_activate(self, *args):
        # frameworkitis has consumed the help system api, so let's avoid that
        # by calling yelp directly
        os.spawnvpe(os.P_NOWAIT, 'yelp', ['yelp', HELPFILE], os.environ)

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
        appbar.set_status(status)
#        statusframe = appbar.get_children()[0]
#        label = statusframe.get_children()[0]
#        label.set_text(status)

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

    def export_text(self, filename):
        file = open(filename, 'w')

        # To sort items (in case of adding a new item they aren't sorted) we need
        # to remake all operations with database ordering by time_start
        db = sqlite.connect(dbfile)
        project = db.cursor()
        # Take all projects from db
        project.execute("SELECT project_name, project_id FROM projects ORDER BY project_id")

        for row in project:
            project_name = row[0]
            project_id = row[1]

            file.write("        %s\n\n" % project_name)

            task = db.cursor()
            # Take all tasks for a given project from db
            sql_stmt = "SELECT task_name, strftime('%s', time_start), strftime('%s', time_finish) FROM tasks "
            sql_stmt+= "WHERE project_id = " + str(project_id)
            sql_stmt+= " ORDER BY time_start DESC"
            task.execute(sql_stmt)

            # A key for printing a date one time foreach value of date
            date = -1;

            for row in task:
                task_note = row[0]
                task_begin = row[1]
                task_end = row[2]

                task_note = task_note.replace('\n', '\n        ')

                end = time.localtime((float)(task_end));
                begin = time.localtime((float)(task_begin));

                end_time = datetime.datetime(end[0], end[1], end[2], end[3], end[4], end[5])
                begin_time = datetime.datetime(begin[0], begin[1], begin[2], begin[3], begin[4], begin[5])

                duration = end_time - begin_time

                if date != begin[2]:
                    if date != -1:
                        file.write("\n")

                    file.write("    %s\n\n" % begin_time.strftime("%d (%A) %B"))
                    date = begin[2]

                file.write("%s %s\n" % (duration, task_note))

            file.write("\n\n");

        file.close()

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

        self.statusbar = self.wtree.get_widget('appbar1')

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

    # Calculate total time spent on selected tasks
    def on_entrytree_button_release_event(self, view, event):
        if event.button == 1:
            # left button
            model, paths = self.entrytree.get_selection().get_selected_rows()
            iters = [ model.get_iter(path) for path in paths ]
            total_duration = 0
            for iter in iters:
                duration = model.get_value(iter, 2)
                total_duration += duration
            date_str = minutes_repr(total_duration)
            self.statusbar.set_status("Total time spent on selected tasks: " + date_str)

    # This function handles right button click only.
    # Left button clicked is handled by the next function.
    def on_entrytree_button_press_event(self, view, event):
        if event.button != 3:
        # not right button
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

        con = sqlite.connect(dbfile)
        cur = con.cursor()
        sql_stmt = "DELETE FROM tasks WHERE time_start= datetime(" + str(time) + ", 'unixepoch')"
        cur.execute(sql_stmt)
        con.commit()

    def on_entrytree_row_activated(self, *args):
        self.editwindow.display()

    def notes_search(self, model, column_num, searchstring, rowiter, d=None):
        # this is less than ideal because it's not an incremental search
        text = model.get_value(rowiter, column_num)
        if text.find(searchstring) != -1:
            return False # this means it was found
        return True

class JournalTree(object):
    def __init__(self, wtree, root):
        self.wtree = wtree
        self.root = root
        self.projectbox = self.wtree.get_widget('projectbox')

        self.journaltree = self.wtree.get_widget('journaltree')
        self.journaltree.set_rules_hint(True) # alternating colors

        self.journal_date_start = self.wtree.get_widget('journal_date_start')
        self.journal_date_finish = self.wtree.get_widget('journal_date_finish')
        self.journal_date_start.set_flags(0);
        self.journal_date_finish.set_flags(0);

        # By default, set finish time to the current one
        # and the start time to the last calendar month, not counting current day.
        # In order to d this, we should now number of days in the previous month.
        current_date = datetime.datetime.now();
        if current_date.month == 0:
            days=31
        else:
            days=calendar.monthrange(current_date.year, current_date.month)[1]

        self.start_time = int(time.time()-60*60*24*(days+1) )
        self.finish_time = int(time.time())
        self.journal_date_start.set_time(self.start_time)
        self.journal_date_finish.set_time(0);

        treeselection = self.journaltree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        self.store = gtk.ListStore(gobject.TYPE_INT,    # time.time() date
                                   gobject.TYPE_STRING, # date repr
                                   gobject.TYPE_INT,    # int seconds
                                   gobject.TYPE_STRING, # repr in minutes
                                   gobject.TYPE_STRING  # notes
                                   )
        self.store.set_sort_column_id(0, gtk.SORT_DESCENDING)
        self.journaltree.set_model(self.store)

        col = gtk.TreeViewColumn('Date', gtk.CellRendererText(), text=1)
        col.set_sort_column_id(0)
        col.set_resizable(True)
        self.journaltree.append_column(col)

        col = gtk.TreeViewColumn('Time', gtk.CellRendererText(), text=3)
        col.set_sort_column_id(2)
        col.set_resizable(True)
        self.journaltree.append_column(col)

        col = gtk.TreeViewColumn('Notes', gtk.CellRendererText(), text=4)
        col.set_sort_column_id(4)
        col.set_resizable(True)
        self.journaltree.append_column(col)

        self.journal_statusbar = self.wtree.get_widget('journal_statusbar')

        self.journaltree.set_property('headers-visible', True)
        self.journaltree.set_search_column(4)
        self.journaltree.set_search_equal_func(self.notes_search)
        projectbox = self.wtree.get_widget('projectbox')
        self.editwindow = JournalEntryEditWindow(self)
        init_signals(self, self.wtree.signal_autoconnect)

    # The next three functions filter the Journals window data to represent
    # last active day, last week and last month activities respectively.
    #
    # We'll manipulate seconds; however, time.time() returns UTC seconds,
    # we should take into account difference with the local time;
    # 'diff' variable will store this difference in seconds
    #
    # When displaying last week/month. let's set time to midnight.
    # Note that last week/month are calendar last week/month,
    # while the last active day is actually the last day when some activities was started.
    #
    # Since time() function is too precise (returns float with milliseconds), we'll truncate it to int
    def on_LastDayBtn_pressed(self, event):
        self.journal_date_finish.set_time(0)
        current_date = datetime.datetime.now()
        self.projectname = self.projectbox.get_child().get_text().strip()

        # Calculate actual active day, not the simply previous one
        con = sqlite.connect(dbfile)
        cur = con.cursor()
        sql_stmt = "SELECT strftime('%s', MAX(time_start)) FROM tasks "
        sql_stmt+= "JOIN projects USING(project_id) "
        sql_stmt+= "WHERE project_name = '" + self.projectname + "'"

        cur.execute(sql_stmt)
        self.start_time = cur.fetchone()[0];

        if not self.start_time:
            self.start_time = 0
        else :
            current_time = int(time.time())
            self.start_time = int(self.start_time) - int(self.start_time)%(60*60*24)

        diff = int( time.mktime(time.localtime()) - time.mktime(time.gmtime()) )
        self.journal_date_start.set_time(self.start_time - diff)
        self.finish_time = int(time.time())
        self.refresh(self.projectname)

    def on_LastWeekBtn_pressed(self, event):
        self.journal_date_finish.set_time(0)
        current_date = datetime.datetime.now()
        self.projectname = self.projectbox.get_child().get_text().strip()

        current_time = int(time.time())
        diff = int( time.mktime(time.localtime()) - time.mktime(time.gmtime()) )

        self.start_time = current_time-60*60*24*7-current_time%(60*60*24)
        self.journal_date_start.set_time(self.start_time-diff)
        self.finish_time = current_time
        self.refresh(self.projectname)

    def on_LastMonthBtn_pressed(self, event):
        self.journal_date_finish.set_time(0)
        current_date = datetime.datetime.now()
        self.projectname = self.projectbox.get_child().get_text().strip()

        current_time = int(time.time())
        diff = int( time.mktime(time.localtime()) - time.mktime(time.gmtime()) )

        # Number of days in the current month
        current_date = datetime.datetime.now();
        if current_date.month == 0:
            days=31
        else:
            days=calendar.monthrange(current_date.year, current_date.month-1)[1]

        self.start_time = current_time-60*60*24*days-(current_time%(60*60*24))
        self.journal_date_start.set_time(self.start_time-diff)
        self.finish_time = current_time
        self.refresh(self.projectname)

    # Calculate total time spent on selected tasks
    def on_journaltree_button_release_event(self, view, event):
        if event.button == 1:
            # left button
            model, paths = self.journaltree.get_selection().get_selected_rows()
            iters = [ model.get_iter(path) for path in paths ]
            total_duration = 0
            for iter in iters:
                duration = model.get_value(iter, 2)
                total_duration += duration
            date_str = minutes_repr(total_duration)
            self.journal_statusbar.pop(0)
            self.old_id = self.journal_statusbar.push(0,"Total time spent on selected tasks: " + date_str)

    def clear(self):
        self.store.clear()

    def refresh(self, projectname):
        self.store.clear()
        if not projectname:
            # when journal tree is initiated with the program start,
            # projectbox is empty; refresh it now
            self.projectname = self.projectbox.get_child().get_text().strip()
            projectname = self.projectname

        if not projectname:
            # This means that no project is selected in the main window
            return

        con = sqlite.connect(dbfile)
        cur = con.cursor()

        # get necessary entries for the project given and fill journal entries with them
        cur.execute("SELECT project_id FROM projects WHERE project_name='" + projectname +"'")
        project_id = cur.fetchone()[0]

        date_start = self.start_time
        date_finish = self.finish_time

        cur_tasks = con.cursor()
        if( not date_start ):
            date_start=0
        if( not date_finish ):
            self.finish_time = time.mktime(time.gmtime())

        # select tasks whose periods intersect with the selected one
        sql_stmt = "SELECT task_name, strftime('%s', time_start), strftime('%s', time_finish) FROM tasks "
        sql_stmt+= "WHERE ( (time_start <= datetime(" + str(date_finish) + ", 'unixepoch') "
        sql_stmt+= "          AND time_start >= datetime(" + str(date_start) + ", 'unixepoch') ) "
        sql_stmt+= "        OR (time_finish <= datetime(" + str(date_finish) + ", 'unixepoch') "
        sql_stmt+= "            AND time_finish >= datetime(" + str(date_start) + ", 'unixepoch') ) "
        sql_stmt+= ") AND project_id=" + str(project_id)
        cur_tasks.execute(sql_stmt)
        for row_tasks in cur_tasks:
            begin = int(row_tasks[1])
            if row_tasks[2] < row_tasks[1]:
                task_finish = time.mktime(time.localtime())
            else :
                task_finish = row_tasks[2]
            duration = int(task_finish) - int(row_tasks[1])
            iter = self.store.append()
            self.store.set_value(iter, 0, int(row_tasks[1]))
            self.store.set_value(iter, 1, time.strftime(ISO, time.localtime(begin)))
            self.store.set_value(iter, 2, duration)
            self.store.set_value(iter, 3, minutes_repr(duration))
            self.store.set_value(iter, 4, row_tasks[0])

    def on_journaltree_button_press_event(self, view, event):
        if event.button != 3:
            # right button
            return
        count = self.journaltree.get_selection().count_selected_rows()
        if count < 1:
            return True
        elif count == 1:
            popup = self.wtree.get_widget('journal_entry_rightclick_popup')
        elif count > 1:
            popup = self.wtree.get_widget('journal_entry_rightclick_popup_multi')
        popup.popup(None, None, None, event.button, event.time)
        return True

    def on_edit_journal_entry_activate(self, *args):
        self.editwindow.display()

    def on_journal_entry_delete_activate(self, menuitem):
        model, paths = self.journaltree.get_selection().get_selected_rows()
        iters = [ model.get_iter(path) for path in paths ]
        for iter in iters:
            self.delete_journal_entry_row(model, iter)

    def delete_journal_entry_row(self, store, iter):
        time = store.get_value(iter, 0)
        projectname = self.projectbox.get_child().get_text().strip()
        project = self.root.get(projectname)
        if not project:
            return

        n = 0
        con = sqlite.connect(dbfile)
        cur = con.cursor()

        for entry in project.get_entries():
            if time == entry.begin:
                project.remove_entry(n)
        sql_stmt = "DELETE FROM tasks WHERE time_start= datetime(" + str(time) + ", 'unixepoch')"
        n+=1
        store.remove(iter)

        cur.execute(sql_stmt)
        con.commit()

    def on_journaltree_row_activated(self, *args):
        self.editwindow.display()

    def notes_search(self, model, column_num, searchstring, rowiter, d=None):
        # this is less than ideal because it's not an incremental search
        text = model.get_value(rowiter, column_num)
        if text.find(searchstring) != -1:
            return False # this means it was found
        return True

    def on_journal_date_start_date_changed(self, *args):
        self.projectbox = self.wtree.get_widget('projectbox')
        self.projectname = self.projectbox.get_child().get_text().strip()
        self.refresh(self.projectname)


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
        if len(paths) == 0 :
            return

        path = paths[0]
        iter = store.get_iter(path)
        start = store.get_value(iter, 0)
        minutes = store.get_value(iter, 2) / 60
        notes = store.get_value(iter, 4)

        con = sqlite.connect(dbfile)
        cur = con.cursor()
        sql_stmt = "SELECT task_id FROM tasks "
        sql_stmt+= "WHERE time_start = datetime(" + str(start) + ", 'unixepoch') "
        sql_stmt+= "AND task_name = '" + notes.replace("'","''") + "'"
        cur.execute(sql_stmt)
        self.task_id = cur.fetchone()[0]

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
        if len(paths) == 0 :
            return

        path = paths[0]
        iter = store.get_iter(path)
        oldbegin = self.store.get_value(iter, 0)
        projectname = self.projectbox.get_child().get_text().strip()
        project = self.root.get(projectname)

        if not project:
            return

        con = sqlite.connect(dbfile)
        cur = con.cursor()
        sql_stmt = "UPDATE tasks SET task_name='" + text.replace("'","''") + "', "
        sql_stmt+= "  time_start = datetime(" + str(begin) + ", 'unixepoch'), "
        sql_stmt+= "  time_finish = datetime(" + str(begin+seconds) + ", 'unixepoch') "
        sql_stmt+= "WHERE task_id=" + str(self.task_id)
        cur.execute(sql_stmt)
        con.commit()

        n = 0
        for entry in project.get_entries():
            if oldbegin == entry.begin:
                entry.begin = begin
                entry.end = begin + seconds
                entry.set_notes(text)
            n+=1

        self.hide()
        self.parent.refresh(projectname)

    def on_entry_edit_delete_event(self, *args):
        self.hide()
        return True # dont allow this window to be destroyed

class JournalEntryEditWindow(object):
    def __init__(self, parent):
        self.wtree = parent.wtree
        self.root = parent.root
        self.store = parent.store
        self.journaltree = parent.journaltree
        self.projectbox = parent.projectbox
        self.parent = parent
        self.window = self.wtree.get_widget('journal_entry_edit')
        self.datebox = self.wtree.get_widget('journal_date_edit_box')
        self.minutebox = self.wtree.get_widget('journal_minutes_edit_box')
        self.notesbox   = self.wtree.get_widget('journal_notes_edit_box')
        init_signals(self, self.wtree.signal_autoconnect)

    def display(self):
        store, paths = self.journaltree.get_selection().get_selected_rows()

        if len(paths) == 0 :
            return

        path = paths[0]
        iter = store.get_iter(path)
        start = store.get_value(iter, 0)
        minutes = store.get_value(iter, 2) / 60
        notes = store.get_value(iter, 4)

        con = sqlite.connect(dbfile)
        cur = con.cursor()
        sql_stmt = "SELECT task_id FROM tasks WHERE time_start = datetime(" + str(start) + ", 'unixepoch') "
        sql_stmt+= "AND task_name = '" + notes.replace("'","''") + "'"
        cur.execute(sql_stmt)

        self.task_id = cur.fetchone()[0]

        self.datebox.set_time(start)
        self.minutebox.set_value(minutes)
        self.notesbox.get_buffer().set_text(notes)
        self.window.set_transient_for(self.journaltree.get_toplevel())
        self.window.show_all()

    def hide(self):
        self.window.hide()

    def on_journal_entry_edit_cancel_clicked(self, *args):
        self.hide()

    def on_journal_entry_edit_apply_clicked(self, *args):
        begin = int(self.datebox.get_time())
        seconds = int(self.minutebox.get_value() * 60)
        buffer = self.notesbox.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end)
        store, paths = self.journaltree.get_selection().get_selected_rows()
        if len(paths) == 0 :
            return

        path = paths[0]
        iter = store.get_iter(path)
        oldbegin = self.store.get_value(iter, 0)
        projectname = self.projectbox.get_child().get_text().strip()
        project = self.root.get(projectname)

        if not project:
            return

        con = sqlite.connect(dbfile)
        cur = con.cursor()
        sql_stmt = "UPDATE tasks SET task_name='" + text.replace("'","''") + "', "
        sql_stmt+= "  time_start = datetime(" + str(begin) + ", 'unixepoch'), "
        sql_stmt+= "  time_finish = datetime(" + str(begin+seconds) + ", 'unixepoch') "
        sql_stmt+= "WHERE task_id=" + str(self.task_id)
        cur.execute(sql_stmt)
        con.commit()

        n = 0
        for entry in project.get_entries():
            if oldbegin == entry.begin:
                entry.begin = begin
                entry.end = begin + seconds
                entry.set_notes(text)
            n+=1

        self.hide()
        self.parent.refresh(projectname)

#    def on_entry_edit_delete_event(self, *args):
#        self.hide()
#        return True # dont allow this window to be destroyed

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
        #self.root.save()
        self.hide()

    def on_prefs_cancel_clicked(self, *args):
        self.hide()

    def on_prefs_delete_event(self, *args):
        self.hide()
        return True # don't allow this window to be destroyed

class JournalsWindow(object):
    def __init__(self, wtree, root):
        self.wtree = wtree
        self.root = root
        self.window = self.wtree.get_widget('Journals')
        init_signals(self, self.wtree.signal_autoconnect)

    def display(self):
        self.window.set_transient_for(self.wtree.get_widget('main'))
        self.window.show_all()

    def hide(self):
        self.window.hide()

    def on_Journals_delete_event(self, *args):
        self.hide()
        return True # dont allow this window to be destroyed

# Global functions

def minutes_repr(seconds):
    minutes = seconds / 60
    hours = int(minutes / 60)
    minutes = minutes - hours * 60
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
#   self.cur_project = ""

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
        con = sqlite.connect(dbfile)
        cur = con.cursor()
        cur.execute("UPDATE tasks SET time_finish = current_timestamp WHERE time_finish < time_start")

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
        entry.start(int(start))
        entry.set_notes(notes)
        entry.stop(int(stop))
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

def main():
    global dbfile
    try:
        dbfile = sys.argv[1]
    except IndexError:
        dbfile = os.path.expanduser('~/.wfyd.db')

    app = MainWindow()
    try:
        gtk.main()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

