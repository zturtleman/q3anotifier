import threading
import socket
import notifier

MY_IDENTIFIER="q3anotifier"
MAX_INFO_STRING=1024 # from q3a sources
PING_ATTEMPTS=3 #ping attempts before removing server from the list

class Pooler(threading.Thread):
    def __init__(self, timeout):
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.timeout = timeout
        self.broadcast_socket.settimeout(self.timeout)
        self.loop = True
        self.current_games = dict()
        self.game_list_lock = None
        threading.Thread.__init__(self)
    
    def handle_response(self, response, address):
        changed = False
        new_server = ()
        info = dict()
        r = response[response.find("\n")+2:].split("\\")
                
        if (response[4:response.find("\n")] != "infoResponse"):
            #print "Got strange packet... - not infoResponse"
            pass
        elif len(r) % 2 or len(r) == 0:
            #print "Got strange packet - wrong number of elements"
            pass
        else:
            for i in xrange(0,len(r),2):
                info[r[i]]=r[i+1]
            info['updated'] = PING_ATTEMPTS # just for comparison
            if self.current_games.has_key(address):
                self.current_games[address]['updated'] = PING_ATTEMPTS
                if self.current_games[address] != info:
                    changed = True
                    self.current_games[address].update(info)
            else:
                changed = True
                new_server = address
                self.current_games[address]=info
        return (changed, new_server)
 
    def filter_obsolete(self):
        changed = False
        keys_to_remove = []
        if (self.current_games):
            for k in self.current_games.iterkeys():
                if (self.current_games[k]['updated']==0):
                    keys_to_remove.append(k)
                    changed = True
                else:
                    self.current_games[k]['updated']=self.current_games[k]['updated']-1
            for k in keys_to_remove:
                del self.current_games[k]
        return changed
     
    def pool(self):
        #phase 1, query:
        self.broadcast_socket.sendto("\xff\xff\xff\xffgetinfo %s" % (MY_IDENTIFIER), ("<broadcast>", 27960));
        waiting_for_response = True
        games_added = False
        new_server = ()
        games_ended = False
        
        #phase 2, try to fetch some responses:
        while waiting_for_response:
            tmp_games_added = False
            tmp_newserver = ()
            try:
                (response, address) = self.broadcast_socket.recvfrom(MAX_INFO_STRING)
                #print response
                (tmp_games_added, tmp_newserver) = self.handle_response(response, address)
                if (not games_added):
                    games_added = tmp_games_added
                if (not new_server):
                    new_server = tmp_newserver
            except socket.timeout:
                waiting_for_response = False
        games_ended = self.filter_obsolete()
        if games_ended or games_added:
            self.notifier.update_gamelist(self.current_games)
        
        if new_server:
            if self.notifier.isAlive():
                self.notifier.display_baloon(new_server)
    
    def register_Notifier(self, notifier):
        self.notifier = notifier
    
    def finish(self):
        self.loop = False

    def run(self):
        while self.loop:
            self.pool()
