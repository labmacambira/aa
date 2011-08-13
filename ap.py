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

import gobject
import pygtk
pygtk.require("2.0")
import gtk
import appindicator

import aa

class Indicador():

   def __init__(self):
       self.janela = Janela()

       self.ind = appindicator.Indicator("labmacambira-aa-client",
                                       #"face-monkey", # aka Gorila Truta
                                     "indicator-messages",
                                  appindicator.CATEGORY_APPLICATION_STATUS)
       self.ind.set_icon("face-monkey")
       self.ind.set_status(appindicator.STATUS_ACTIVE)
       self.ind.set_attention_icon("face-surprise")
       # /usr/share/icons
       # /usr/share/pixmaps
       # /usr/share/app-install

       self.slotador = aa.Slotador()
       self.cont = 0

       self.menu = gtk.Menu()
       mi = gtk.MenuItem('AA')
       self.menu.append(mi)
       self.ind.set_menu(self.menu)
       mi.show()
       mi.connect("activate", self.clicado, "blah")
       #accel_group = gtk.AccelGroup()
       #self.janela.janela.add_accel_group(accel_group)
       #mi.add_accelerator("activate", accel_group, ord('Q'),
       #                   gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

       gtk.timeout_add(2000, self.atualizar)

       gtk.main()

   def clicado(self, w, r):
       self.janela.mostrar()

   def atualizar(self):
       self.slotador.atualizar()
       self.ind.set_label('[faltam '+str(self.slotador.faltam_m)+'min]')
       raz = float(self.slotador.decorridos_m)/(self.slotador.faltam_m+self.slotador.decorridos_m)
       self.janela.ajustar_barra(raz)
       #menuitem.get_child().set_text('New text')
       if self.slotador.atual_respondido():
           self.ind.set_status(appindicator.STATUS_ACTIVE)
       else:
           self.ind.set_status(appindicator.STATUS_ATTENTION)
       return True


class Janela(object):       

    def __init__(self):
        self.console = aa.Console()

        builder = gtk.Builder()
        builder.add_from_file("janela.glade")
        builder.connect_signals({ "on_ok" : self.enviar,
                                  "on_cancel" : self.cancelar,
                                  "on_ss" : self.startstop,
                                  "on_push" : self.push,
                                })
        self.janela = builder.get_object("janela")
        self.mensagem = builder.get_object("mensagem")
        self.barra = builder.get_object("barra")
        self.bot_ss = builder.get_object("startstop")
        if self.console.daemon_running():
            self.bot_ss.set_active(True)
        else:
            self.bot_ss.set_active(False)
        self.startstop_label()

    def ajustar_barra(self, x):
        self.barra.set_fraction(x)

    def resetar(self):
        """Reseta a janela para para poder ser aberta novamente"""
        self.janela.hide()
        self.mensagem.set_text("")
        self.mensagem.grab_focus()

    def push(self, w):
        pass

    def startstop_label(self):
        """Arruma o label do botao de start e stop"""
        pressionado = self.bot_ss.get_active()
        if pressionado:
            self.bot_ss.set_label("Stop")
        else:
            self.bot_ss.set_label("Start")

    def startstop(self, w):
        self.startstop_label()
        pressionado = w.get_active()
        if pressionado:
            self.console.start()
            w.set_label("Stop")
        else:
            self.console.stop()
            w.set_label("Start")

    def cancelar(self, w):
        """Botao Cancelar clicado"""
        self.resetar()

    def mostrar(self):
        self.janela.show()

    def enviar(self, w):
        msg = self.mensagem.get_text()
        self.resetar()
        while gtk.events_pending():
            gtk.main_iteration() 
        self.console.send_scream(msg)


if __name__ == "__main__":
    i = Indicador()
