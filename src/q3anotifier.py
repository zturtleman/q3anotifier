import pooler
import notifier
import threading
import os
import win32gui
import win32gui_struct
import sys
import ConfigParser
from ConfigParser import NoSectionError

class Controller:    
    def start_quake(self, address, port):
        quake_exe = os.path.basename(self.QUAKEPATH)
        os.chdir(os.path.dirname(self.QUAKEPATH))
        
        if not address is None:
            os.system("\"%s\" +connect %s:%d" % (quake_exe, address, port))
        else:
            os.system("\"%s\" +map %s" % (quake_exe, self.defaultmap) )
        
    def configure(self):
        config = ConfigParser.RawConfigParser()
        local_path = "%s/q3anotifier.ini" % os.path.dirname(sys.argv[0])
        tmp_quake_path = None
        
        try:
            config_file = file(local_path, "r")
            config.read(local_path)
            tmp_quake_path = config.get("q3anotifier", "quake3.exe")
            config_file.close()
        
            if (config.has_option("q3anotifier", "timeout")):
                self.timeout = config.getint("q3anotifier", "timeout")

            if (config.has_option("q3anotifier", "defaultmap")):
                self.defaultmap = config.get("q3anotifier", "defaultmap")
                
        except (IOError, NoSectionError):
            pass
    
        if (not tmp_quake_path or not os.path.isfile(tmp_quake_path)):
            try:
                fname, customfilter, flags=win32gui.GetOpenFileNameW(
                                                             File="quake3.exe",
                                                             Filter="Quake 3 binary (quake3.exe)\0quake3.exe",
                                                             Title="Where is your quake3.exe?",
                                                             FilterIndex = 0)
                if not os.path.isfile(fname):
                    raise IOError
                tmp_quake_path = fname
                if not config.has_section("q3anotifier"):
                    config.add_section("q3anotifier")
                config.set("q3anotifier", "quake3.exe", fname)
            except:
                sys.exit(1)
    
        try:
            config.set("q3anotifier", "timeout", self.timeout)
            config.set("q3anotifier", "defaultmap", self.defaultmap)
            config_file = file(local_path, "w")
            config.write(config_file)
            config_file.close()
        except:
            pass
        
        self.QUAKEPATH = tmp_quake_path
        
    
    
    def __init__(self):
        self.QUAKEPATH = ""
        self.defaultmap = "q3dm17"
        self.timeout = 3
        self.configure()
        
        evt_gui_ready = threading.Event()
        myGUI = notifier.Notifier(self.QUAKEPATH, None, 1, evt_gui_ready, self.start_quake)
        myPooler = pooler.Pooler(timeout = self.timeout)
        myPooler.register_Notifier(myGUI)
        
        myGUI.start()
        evt_gui_ready.wait()
        myPooler.start()
        myGUI.join()
        myPooler.finish()
        myPooler.join()
    
if __name__ == "__main__":
    Controller()