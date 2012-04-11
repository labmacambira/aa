#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
import dbus, gobject
from dbus.mainloop.glib import DBusGMainLoop

import os
def recebe_pidgin(account, sender, message, conversation, flags):
    print os.system("aa config user.nickname %s" % (sender.encode('utf-8'),) )
    message = message.encode('utf-8')
    if len(message) < 500:
        print os.system('aa shout %s' % (message,))
    else: 
        while len(message)>500:
            print os.system("aa shout '%s'" % (message[:500],))
            message=message[500:]
        print os.system("aa shout '%s'" % (message,))
                  
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
                               
bus.add_signal_receiver(recebe_pidgin,dbus_interface="im.pidgin.purple.PurpleInterface", signal_name="ReceivedImMsg")
                                
loop = gobject.MainLoop()
loop.run()
