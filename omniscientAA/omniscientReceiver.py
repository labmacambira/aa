#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
import dbus, gobject
from dbus.mainloop.glib import DBusGMainLoop

def recebe_pidgin(account, sender, message, conversation, flags):
    print 'sender8: %s' % (sender.encode('utf-8')+'\n',) 
    print 'message: %s' % (message.encode('utf-8')+'\n',) 
                             
                  
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
                               
bus.add_signal_receiver(recebe_pidgin,dbus_interface="im.pidgin.purple.PurpleInterface", signal_name="ReceivedImMsg")
                                
loop = gobject.MainLoop()
loop.run()
