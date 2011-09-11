#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright 2011 Lab Macambira
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
#-----------------------------------------------------------------------------

from datetime import datetime, timedelta
from subprocess import Popen, PIPE, STDOUT
import os, sys

import gobject
import pygtk
pygtk.require("2.0")
import gtk
import appindicator
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

import aa


def achar_arquivo(nome):
    return os.readlink('/usr/local/bin/aapp')[:-7]+nome

    #try:
    #    cmd = 'readlink -f aapp'
    #    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    #    output = p.stdout.read()
    #    caminho = output.splitlines()[0].rsplit('/', 1)[0]+'/'
    #    return caminho+nome
    #except:
    #    return "./"+nome


class Indicador(dbus.service.Object):
    """Cria um Application Indicator no Unity"""

    def __init__(self):
        """Cria o app e inicializa a janela"""
        self.ind = appindicator.Indicator("labmacambira-aa-client",
                                        #"face-monkey", # aka Gorila Truta
                                      "indicator-messages",
                                   appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind.set_icon("face-tired")
        self.ind.set_status(appindicator.STATUS_ACTIVE)
        self.ind.set_attention_icon("face-surprise")
        # /usr/share/icons
        # /usr/share/pixmaps
        # /usr/share/app-install

        self.console = aa.Console()
        self.janela = Janela(self)

        self.slotador = aa.Slotador()
        self.cont = 0

        self.menu = gtk.Menu()
        self.mi = gtk.MenuItem('AA')
        self.menu.append(self.mi)
        self.ind.set_menu(self.menu)
        self.mi.show()
        self.mi.connect("activate", self.clicado, "blah")

        DBusGMainLoop(set_as_default=True)
        bus_name = dbus.service.BusName('org.macambira.AA', bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, '/org/macambira/AA')

        gtk.main()

    @dbus.service.method('org.macambira.AA')
    def atalho(self):
        self.mi.activate()

    def acordar(self):
        """comeca a contar os minutos"""
        self.ind.set_icon("face-monkey")
        self.timeout_id = gtk.timeout_add(2000, self.atualizar)

    def dormir(self):
        """para de contar minutos"""
        self.ind.set_icon("face-tired")
        gobject.source_remove(self.timeout_id)
        self.ind.set_label('')
        self.ind.set_status(appindicator.STATUS_ACTIVE)

    def clicado(self, w, r):
        """exibe a janela"""
        self.janela.mostrar()

    def atualizar(self):
        """atualiza contagem de minutos"""
        self.slotador.atualizar()
        raz = float(self.slotador.decorridos_m)/(self.slotador.faltam_m+self.slotador.decorridos_m)
        # ajusta barra de completude da janela
        self.janela.ajustar_barra(raz)
        #menuitem.get_child().set_text('New text')
        ateslot = ''
        if self.slotador.atual_respondido():
            # Coloca carinha do gorila
            self.ind.set_status(appindicator.STATUS_ACTIVE)
            ateslot = '('+str(self.slotador.prox_time)+')'
        else:
            # Coloca cara de atencao
            self.ind.set_status(appindicator.STATUS_ATTENTION)

        # ajusta novo label
        self.ind.set_label('[faltam '+str(self.slotador.faltam_m)+'min'+ateslot+']')
        return True


class Janela(object):
    """janela com opcoes de controle do programa"""

    def __init__(self, ind):
        """inicializa itens da janela, mas a mantem escondida"""
        self.ind = ind
        self.console = ind.console

        builder = gtk.Builder()
        builder.add_from_file(achar_arquivo("janela.glade"))
        builder.connect_signals({ "on_ok" : self.enviar,
                                  "on_cancel" : self.cancelar,
                                  "on_ss" : self.startstop,
                                  "on_push" : self.push,
                                  "on_sair" : self.sair,
                                  'on_delete_event' : self.resetar,
                                })
        self.janela = builder.get_object("janela")
        #self.janela.set_focus_on_map(True)
        self.janela.set_position(gtk.WIN_POS_CENTER)
        self.mensagem = builder.get_object("mensagem")
        self.barra = builder.get_object("barra")
        self.bot_ss = builder.get_object("startstop")
        if self.console.daemon_running():
            self.bot_ss.set_active(True)
        else:
            self.bot_ss.set_active(False)
        self.startstop_label()

    def ajustar_barra(self, x):
        """ajusta o preenchimento de barra de minutos"""
        if x < 0.0:
            x2 = 0.0
        elif x > 1.0:
            x2 = 1.0
        else:
            x2 = x
        self.barra.set_fraction(x2)

    def resetar(self, w=None, w2=None):
        """Reseta a janela para para poder ser aberta novamente"""
        self.janela.hide()
        self.mensagem.set_text("")
        #self.mensagem.grab_focus()
        self.janela.set_urgency_hint(False)
        return True

    def push(self, w):
        """faz o push do AA"""
        self.console.push()

    def startstop_label(self):
        """Arruma o label do botao de start e stop"""
        pressionado = self.bot_ss.get_active()
        if pressionado:
            self.bot_ss.set_label("Stop")
        else:
            self.bot_ss.set_label("Start")

    def startstop(self, w):
        """trata o botao quando pressionado, podendo mandar start ou stop"""
        self.startstop_label()
        pressionado = w.get_active()
        if pressionado:
            #self.console.start()
            if not self.console.daemon_running():
                os.system("aa start")
            self.ind.acordar()
            w.set_label("Stop")
        else:
            #self.console.stop()
            if self.console.daemon_running():
                os.system("aa stop")
            self.ind.dormir()
            w.set_label("Start")

    def sair(self, w):
        gtk.main_quit()
        
    def cancelar(self, w):
        """Botao Cancelar clicado"""
        self.resetar()

    def mostrar(self):
        """Revela a janela"""
        #self.mensagem.grab_focus()
        self.janela.set_urgency_hint(True)
        self.janela.set_accept_focus(True)
        self.janela.present()
        self.janela.set_urgency_hint(True)
        self.janela.set_accept_focus(True)
        #FIXME a mardita janela nao ganha foco na segunda vez que abre
        #self.ind.teste.hide()
        #self.ind.teste.show()
        #self.janela.show_all()

    def enviar(self, w):
        """Envia um shout pelo AA"""
        msg = self.mensagem.get_text()
        self.resetar()
        # Evita que a janela fique esperando ate o fim do shout
        while gtk.events_pending():
            gtk.main_iteration() 
        self.console.send_scream(msg)


class Janelinha(object):
    """janela com opcoes de controle do programa"""

    def __init__(self):
        """inicializa itens da janela, mas a mantem escondida"""
        self.console = aa.Console()

        builder = gtk.Builder()
        builder.add_from_file(achar_arquivo("janelinha.glade"))
        builder.connect_signals({ "on_ok" : self.enviar,
                                  "on_cancel" : self.cancelar,
                                })
        self.janela = builder.get_object("janela")
        #self.janela.set_focus_on_map(True)
        self.janela.set_position(gtk.WIN_POS_CENTER)
        self.mensagem = builder.get_object("mensagem")

        self.janela.show_all()

        gtk.main()

    def ajustar_barra(self, x):
        """ajusta o preenchimento de barra de minutos"""
        if x < 0.0:
            x2 = 0.0
        elif x > 1.0:
            x2 = 1.0
        else:
            x2 = x
        self.barra.set_fraction(x2)

    def cancelar(self, w):
        """Botao Cancelar clicado"""
        gtk.main_quit()

    def enviar(self, w):
        """Envia um shout pelo AA"""
        print "oooi"
        msg = self.mensagem.get_text()
        self.janela.hide()
        # Evita que a janela fique esperando ate o fim do shout
        while gtk.events_pending():
            gtk.main_iteration() 
        self.console.send_scream(msg)
        gtk.main_quit()
        print "oooi2"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "msg":
            Janelinha()
    else:
        i = Indicador()
