from gi.repository import Gtk
from gi.repository import GObject, Nemo
import os
import gettext
import subprocess
import time

class FsCheckPropertyPage(GObject.GObject, Nemo.PropertyPageProvider):
    def __init__(self):
        print "Initializing nemo-fscheck extension"
        pass
    
    def get_property_pages(self, files):
        if len(files) != 1:
            return
        
        file = files[0]
        print file.get_mount()
        if not (
            ( ( file.get_uri_scheme() == 'x-nemo-desktop' ) and 
            ( file.get_mime_type() == 'application/x-nemo-link' ) ) or 
            ( file.get_uri_scheme() == 'computer') ):
            return
            
        self.mountpoint = file.get_mount().get_root().get_path()
        if not os.path.ismount(self.mountpoint):
            return
            
        found = 0
        for line in open('/proc/mounts','r').readlines():
            sp = line.split()
            try:
                if sp[1] == self.mountpoint:
                    self.device = sp[0]
                    found = 1
                    break
            except IndexError:
                continue
        if found == 0:
            return
        self.property_label = Gtk.Label(gettext.dgettext('nemo-fscheck', 'Check').decode('utf-8'))
        self.property_label.show()

        self.vbox = Gtk.VBox(0, False)
        self.hbox = Gtk.HBox(0, False)
        self.text = Gtk.Label()
        self.text.set_markup(gettext.dgettext('nemo-fscheck', "Here you can check the filesystem on this device for errors and repair them").decode('utf-8'))
        self.vbox.pack_start(self.text, False, False, 10)
        self.button = Gtk.Button(gettext.dgettext('nemo-fscheck', 'Check Filesystem').decode('utf-8'))
        self.button.connect('clicked', self.check_filesystem)
        self.hbox.pack_start(self.button, False, False, 10)
        self.vbox.pack_start(self.hbox, False, False, 0)
        self.vbox.show_all()
        
        page = Nemo.PropertyPage(name="NemoPython::fscheck", label=self.property_label, page=self.vbox)
        return [page]
        
    def start_with_pbar(self, args, title, message):
        w = Gtk.Window()
        w.set_position(Gtk.WindowPosition.CENTER)
        w.set_title(title)
        vbox = Gtk.VBox()
        l = Gtk.Label()
        l.set_markup(message)
        pb = Gtk.ProgressBar()
        pb.set_pulse_step(0.02)
        vbox.pack_start(l, False, False, 0)
        vbox.pack_start(pb, False, False, 0)
        w.add(vbox)
        w.show_all()
        p = subprocess.Popen(args)
        while p.poll() is None:
            pb.pulse()
            while Gtk.events_pending():
                Gtk.main_iteration()
            time.sleep(.1)
        w.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        return p.returncode
                       
    def _check_combo_changed(self, combo, warnlabel):
        a = combo.get_active()
        if a == 0:
            warnlabel.hide()
        elif a == 1:
            warnlabel.set_markup("<span foreground=\"red\">" + gettext.dgettext('nemo-fscheck', "WARNING: This enables repair actions which may further corrupt the filesystem if something goes wrong.").decode('utf-8') + "</span>")
            warnlabel.show()
        else:
            warnlabel.set_markup("<span foreground=\"red\">" + gettext.dgettext('nemo-fscheck', "WARNING: This will open a terminal where you can continue the repair process yourself. Be sure you know what you are doing.").decode('utf-8') + "</span>")
            warnlabel.show()
    
    def show_message(self, type, text):
        dlg = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK, type=type, message_format=text, flags=Gtk.DialogFlags.MODAL)
        dlg.run()
        dlg.destroy()
                                     
    def check_filesystem(self, widget):
        openfiles = subprocess.Popen([ "/usr/bin/sudo", "/usr/bin/lsof", "-w", self.mountpoint ], stdout=subprocess.PIPE).communicate()[0]
        if len(openfiles) > 0:
            self.text.set_markup(gettext.dgettext('nemo-fscheck', "There are still open files on this volume.\nPlease close them and try again!").decode('utf-8'))
            while Gtk.events_pending():
                Gtk.main_iteration()
            return
        dlg = Gtk.MessageDialog(buttons=Gtk.ButtonsType.YES_NO, type=Gtk.MessageType.QUESTION, 
        message_format=gettext.dgettext('nemo-fscheck', "You are about to check and repair a filesystem. Even though this works in most cases, it is advisable to have a backup in case something goes wrong. Do you want to continue?").decode('utf-8'))
        dlg.set_default_response(Gtk.ResponseType.YES)
        dlg.set_keep_above(True)
        dlg.set_urgency_hint(True)
        dlg.set_position(Gtk.WindowPosition.CENTER)
        vbox = Gtk.VBox()
        combo = Gtk.ComboBoxText()
        combo.append_text(gettext.dgettext('nemo-fscheck', "Normal").decode('utf-8'))
        combo.append_text(gettext.dgettext('nemo-fscheck', "Force dangerous repairs").decode('utf-8'))
        combo.append_text(gettext.dgettext('nemo-fscheck', "Interactive repair").decode('utf-8'))
        combo.set_active(0)
        label = Gtk.Label(gettext.dgettext('nemo-fscheck', "Mode of operation:").decode('utf-8'))
        label.set_alignment(0.0, 0.5)
        hbox = Gtk.HBox()
        warnlabel = Gtk.Label()
        warnlabel.set_line_wrap(True)
        warnlabel.set_alignment(0.0, 0.5)
        warnlabel.set_no_show_all(True)
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(combo, False, False, 10)
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(warnlabel, False, False, 10)
        combo.connect('changed', self._check_combo_changed, warnlabel)
        dlg.get_content_area().pack_start(vbox, True, True, 0)
        dlg.show_all()
        response = dlg.run()
        mode = combo.get_active()
        dlg.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if response == Gtk.ResponseType.NO:
            return False
        try:
            subprocess.check_call(["udisksctl", "unmount", "-b", self.device])
        except:
            self.text.set_markup(gettext.dgettext('nemo-fscheck', "Could not unmount volume").decode('utf-8'))
            while Gtk.events_pending():
                Gtk.main_iteration()
            return
        if mode == 0:
            args = ["/usr/bin/sudo", "/sbin/fsck", "-f", "-a", self.device]
        elif mode == 1:
            args = ["/usr/bin/sudo", "/sbin/fsck", "-f", "-y", self.device]
        else:
            fs=subprocess.Popen([ "/usr/bin/sudo", "/sbin/blkid", "-c", "/dev/null", "-s", "TYPE", "-o", "value", self.device ], stdout=subprocess.PIPE).communicate()[0].splitlines()[0]
            if fs == "vfat":
                args = ["/usr/bin/xterm", "-T", gettext.dgettext('nemo-fscheck', "Filesystem check"), "-e", "/bin/rbash", "-c", "sudo dosfsck -wr " + self.device + "; read -p '" + gettext.dgettext('nemo-fscheck', "Press any key to continue").decode('utf-8') +"' -n 1 -s"]
            else:
                args = ["/usr/bin/xterm", "-T", gettext.dgettext('nemo-fscheck', "Filesystem check"), "-e", "/bin/rbash", "-c", "sudo fsck -f " + self.device + "; read -p 'Press any key to continue' -n 1 -s"]
        if mode < 2:
            ret = self.start_with_pbar(args, gettext.dgettext('nemo-fscheck', "Checking filesystem on %s...").decode('utf-8') % self.device, gettext.dgettext('nemo-fscheck', "The filesystem on %s is being checked and, if neccessary, repaired.\nThis may take a while, please be patient.").decode('utf-8') % self.device)
            print "Check done!"
            if ret == 0:
                self.show_message(Gtk.MessageType.INFO, gettext.dgettext('nemo-fscheck', "No errors were found during this check.").decode('utf-8'))
            elif ret == 1:
                self.show_message(Gtk.MessageType.WARNING, gettext.dgettext('nemo-fscheck', "Errors were found and repaired during this check.").decode('utf-8'))
            else:
                self.show_message(Gtk.MessageType.ERROR, gettext.dgettext('nemo-fscheck', "For some reason, filesystem check was not successful or did not complete.").decode('utf-8'))
        else:
            ret = subprocess.call(args)
        try:
            subprocess.check_call(["udisksctl", "mount", "-b", self.device])
        except:
            self.show_message(Gtk.MessageType.ERROR, gettext.dgettext('nemo-fscheck', "Could not remount volume").decode('utf-8'))

