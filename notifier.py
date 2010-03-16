# Module     : SysTrayIcon.py
# Synopsis   : Windows System tray icon.

# Notes      : Based on (i.e. ripped off from) SysTrayIcon.py by Simon Brunning, which was
#              Based on (i.e. ripped off from) Mark Hammond's
#              win32gui_taskbar.py and win32gui_menu.py demos from PyWin32
#            
      
import os
import win32api
import winxpgui
import win32con
import win32gui_struct
import threading
import copy

try:
    import winxpgui as win32gui
except ImportError:
    import win32gui

class Notifier(threading.Thread):
    FIRST_ID = 1023
    ID_QUIT = 2048
    ID_ABOUT = 2049
    ID_AUTOSTART = 2050
    
    GAME_TYPES = {
                  0: "Free For All",
                  1: "Tournament One-on-One",
                  2: "Single Player",
                  3: "Team Deathmatch",
                  4: "Capture The Flag"
                  }
    
    def __init__(self,
                 icon,
                 on_quit,
                 default_menu_index,
                 evt_gui_ready,
                 controller
                 ):
        
        self.evt_gui_ready = evt_gui_ready
        self.hover_text = "q3anotifier - right click to see the list of open games"
        self.on_quit = on_quit
        self.on_baloonclick = None
        hicon, small = win32gui.ExtractIconEx(icon, 0)
        win32gui.DestroyIcon(small[0])
        self.icon = hicon[0]
        self.game_list = dict()
        self.game_list_lock = threading.Lock()
        self.window_class_name = "q3anotifier"
        self.ids_to_addresses = dict()
        self.baloon_address = None
        self.quake_starter = controller.start_quake
        self.controller = controller
        self.menu_counters = dict()
        threading.Thread.__init__(self)
        
        
    def run(self):
        message_map = {win32gui.RegisterWindowMessage("TaskbarCreated"): self.restart,
           win32con.WM_DESTROY: self.destroy,
           win32con.WM_COMMAND: self.command,
           win32con.WM_USER+20: self.notify,}
        # Register the Window class.
        window_class = win32gui.WNDCLASS()
        hinst = window_class.hInstance = win32gui.GetModuleHandle(None)
        window_class.lpszClassName = self.window_class_name
        window_class.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground = win32con.COLOR_WINDOW
        window_class.lpfnWndProc = message_map # could also specify a wndproc.
        classAtom = win32gui.RegisterClass(window_class)
        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(classAtom,
                                          self.window_class_name,
                                          style,
                                          0,
                                          0,
                                          win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT,
                                          0,
                                          0,
                                          hinst,
                                          None)
        win32gui.UpdateWindow(self.hwnd)
        self.notify_id = None
        self.refresh_icon()
        self.evt_gui_ready.set()
        win32gui.PumpMessages()
        
    def refresh_icon(self):
        if self.notify_id: message = win32gui.NIM_MODIFY
        else: message = win32gui.NIM_ADD
        self.notify_id = (self.hwnd,
                          0,
                          win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                          win32con.WM_USER+20,
                          self.icon,
                          self.hover_text)
        win32gui.Shell_NotifyIcon(message, self.notify_id)
        
    def restart(self, hwnd, msg, wparam, lparam):
        self.refresh_icon()

    def destroy(self, hwnd, msg, wparam, lparam):
        if self.on_quit: self.on_quit(self)
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0) # Terminate the app.

    def notify(self, hwnd, msg, wparam, lparam):
        if lparam==win32con.WM_LBUTTONDBLCLK:
            self.find_or_create_game()
        elif lparam==win32con.WM_RBUTTONUP:
            self.show_menu()
        elif lparam==win32con.WM_LBUTTONUP:
            pass
        elif lparam==0x405: # user clicked baloon
            if callable(self.quake_starter):
                self.quake_starter(*self.baloon_address)
        return True
        
    def show_menu(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu)
        #win32gui.SetMenuDefaultItem(menu, 1000, 0)
        
        pos = win32gui.GetCursorPos()
        # See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
        try:
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.TrackPopupMenu(menu,
                                    win32con.TPM_LEFTALIGN,
                                    pos[0],
                                    pos[1],
                                    0,
                                    self.hwnd,
                                    None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        except:
            pass
    
    def add_item_to_menu(self, *args, **kwargs):
        menu = args[0]
        item, extras = win32gui_struct.PackMENUITEMINFO(**kwargs)
        win32gui.InsertMenuItem(menu, self.menu_counters[menu], 1, item)
        self.menu_counters[menu] += 1
    
    def create_menu(self, menu):
        menu_items = list()
        self.menu_counters[menu]=0
        
        with self.game_list_lock:
            if self.ids_to_addresses:
                del self.ids_to_addresses
            self.ids_to_addresses = dict()
            id_counter = self.FIRST_ID
            addresses = self.game_list.keys()
            addresses.sort()
 
            for address in addresses:
                self.ids_to_addresses[id_counter] = address
                id_counter+=1
        
            for id in self.ids_to_addresses.keys():                
                game_text, game_type = self.format_game_text(self.ids_to_addresses[id])
                self.add_item_to_menu(text=game_text, wID=id)

        
        if not self.ids_to_addresses:
            self.add_item_to_menu(menu, text = "No games found.", fState = win32con.MFS_DISABLED)
        
        self.add_item_to_menu(menu, fType = win32con.MFT_SEPARATOR)

        submenu = self.prepare_options_submenu()
        self.add_item_to_menu(menu, hSubMenu = submenu, text = "Options")
        self.add_item_to_menu(menu, text="Exit", wID=self.ID_QUIT)

    def prepare_options_submenu(self):
        submenu = win32gui.CreatePopupMenu()
        autostart_status = win32con.MFS_UNCHECKED
        
        if (self.controller.autostart_enabled()):
            autostart_status = win32con.MFS_CHECKED
      
        self.menu_counters[submenu]=0
        self.add_item_to_menu(submenu, wID = self.ID_ABOUT, text="About...")
        self.add_item_to_menu(submenu, fState = autostart_status, wID=self.ID_AUTOSTART, text = "Autostart")
        return submenu

    def command(self, hwnd, msg, wparam, lparam):
        id = win32gui.LOWORD(wparam)
        if id in self.ids_to_addresses.keys():
            self.quake_starter(*self.ids_to_addresses[id])
        elif id == self.ID_QUIT:
            win32gui.DestroyWindow(self.hwnd)
        elif id == self.ID_AUTOSTART:
            self.controller.toggle_autostart()
        elif id == self.ID_ABOUT:
            self.controller.about_page()

    def display_baloon(self, address):
        self.baloon_address = address
        game_description = ""
        game_type = ""
        with self.game_list_lock:
            (game_description, game_type) = self.format_game_text(address)
            
        my_notify = (self.hwnd,
            0,
            win32gui.NIF_INFO,
            0,
            self.icon,
            "",
            "New game detected, click to join.\n%s\nIP: %s%s" % (game_description, address[0],game_type),
            5000,
            "Quake announcement",
            0x00000004)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, my_notify)
    
    def format_game_text(self, address):
        in_text = self.game_list[address]
        game_type = ""
        
        game_description = "%s, map: %s, free slots: %d / %d" % (
            in_text['hostname'],
            in_text['mapname'],
            int(in_text['sv_maxclients']) - int(in_text['clients']),
            int(in_text['sv_maxclients']))
        if self.GAME_TYPES.has_key(int(in_text['gametype'])):
            game_type = "\n" + self.GAME_TYPES[int(in_text['gametype'])]
        
        return (game_description, game_type)
    
    def update_gamelist(self, new_game_list):
        with self.game_list_lock:
            del self.game_list
            self.game_list = copy.deepcopy(new_game_list)

    def find_or_create_game(self):
        with self.game_list_lock:
            available_games = list()
            for (addr, gameinfo) in self.game_list.items():
                if gameinfo['sv_maxclients'] > gameinfo['clients']:
                    if gameinfo['gametype'] > 0:
                        available_games.append(addr)
                    else:
                        available_games.insert(0, addr)
        if available_games:
            self.quake_starter(*available_games[0])
        else:
            self.quake_starter(None, None) # start server