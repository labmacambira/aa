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

import sys, os, time, atexit, urllib, urllib2, json, io, ConfigParser, csv
from signal import SIGTERM
from datetime import datetime, timedelta

try:
    import pynotify
    if not pynotify.init("AA"):
        print("there was a problem initializing the pynotify module")
except:
    print("you don't seem to have pynotify installed")


guide = """
_.__o_oOoOo[ AA ]oOoOo_o__._

Usage:

   aa config <config> <value>     ... sets the config value
   aa start                       ... starts the work session of the day
   aa stop                        ... stops the work session
   aa shout <message>             ... alerts what he is doing now (online)
   aa post <message>              ... alerts what he is doing now (offline)
   aa push                        ... pushes the log to the server
   aa status                      ... checks daemon status
   aa logview                     ... shows your current log
   aa time                        ... shows time and timeslot info
   aa revive                      ... revives the session after a crash
   aa tickets                     ... shows your active tickets (if you are a Macambira)
   aa showticket <ticket number>  ... shows a ticket on trac


Remember, you have to configure your nickname before start:

   aa config user.nickname <YOUR NICKNAME HERE>

Workflow:
             .-.
             v |
   start -> shout -> stop -> push
             or
            post
"""

configuration = ConfigParser.RawConfigParser()
__init = """
[user]
nickname=
email=
tick=900

[server]
url=http://nightsc.com.br/aa/parser.php
"""

def init_config():
    """Checks if configuration file exists, case not creates one with initial layout"""
    try:
        open(__get_config_file())
    except IOError:
        configuration.readfp(io.BytesIO(__init))
        #FIXME implement with dictionaries maybe
        __save()

def __save():
    """Saves configuration options to file"""
    with open(__get_config_file(), "wb") as f:
        configuration.write(f)

def __get_config_file():
    """Gets configuration file name"""
    return os.getenv('HOME')+'/.aaconfig'

def config(params):
    """Receives a list with attribute and value.
    Parses attribute for section information and saves value associated."""
    configuration.read(__get_config_file())
    #if section user not present, then create config file with initial layout
    if not configuration.has_section('user'):
        init_config()
    #checks if params is the right size
    if len(params) == 2:
        attribute, value = params
        #if attribute is like section.attribute parses it
        if attribute.count('.') == 1:
            section, attribute = attribute.split('.')
            #if section does not exist creates it
            if not configuration.has_section(section):
                configuration.add_section(section)
            #else set correspondent value
            configuration.set(section, attribute, value)
        else:
            #if no section is specified, add attribute to user section
            configuration.set('user', attribute, value)
        __save()

def get(params):
    """Receives a list with section and attribute name and returns the correspondent value"""
    configuration.read(__get_config_file())
    if (len(params)) == 2:
        section, attribute = params
        try:
            return configuration.get(section, attribute)
        except ConfigParser.NoOptionError:
            pass
    return None

#
# Calcula timeslots dos logs
#

class Slotador():
    """Classe para calcular timeslots dos logs
    Para usar, instancie:
        s = Slotador()
    E pegue a lista dos numeros de slots ja respondidos
        s.respondidos
    Ex. dessa lista:
        [1, 2, 4, 5]
    Isso quer dizer que vc respondeu corretamente nos timeslots 1,2,4 e 5
    Mas perdeu o 3
    """

    def __init__(self):
        self.atualizar()

    def atualizar(self):
        """Recarrega logs e recalcula os timeslots"""
        home = os.getenv('HOME')
        f = open(home + '/.aa.log', 'r')
        linhas = f.read().splitlines()
        f.close()
        mensagens = []
        self.fim = None
        for linha in linhas:
            data, texto = linha.split(',', 1)
            if texto != 'notify':
                data = self.interpretar_data(data)
                if texto == 'start':
                    self.inicio = data
                elif texto == 'stop':
                    self.fim = data
                else:
                    mensagens.append((data, texto))

        self.respondidos = []
        for m in mensagens:
            slot = self.timeslotar(m[0])
            if slot != -1:
                if slot not in self.respondidos:
                    self.respondidos.append(slot)

        if self.fim == None:
            agora = datetime.now()
        else:
            agora = self.fim
        agora = agora - self.inicio
        minu = agora.total_seconds()/60.0
        atual = int((minu-5)/15)
        self.perdidos = []
        for i in range(1,atual+1):
            if i not in self.respondidos:
                self.perdidos.append(i)

        self.fim_teorico = self.inicio + timedelta(minutes=120)
        self.faltam = self.fim_teorico - datetime.now()
        self.faltam_m = int(self.faltam.total_seconds()/60+1)
        self.prox_time = (self.faltam_m-5) % 15
        self.decorridos_m = int(minu)

    def atual_respondido(self):
        """Retorna se o timeslot atual ja foi respondido"""
        atual = self.timeslotar(datetime.now())
        if atual != -1:
            if atual not in self.respondidos:
                return False
        return True

    def interpretar_data(self, texto):
        """Converte de string para date"""
        return datetime.strptime(texto, '%Y-%m-%d %H-%M-%S')

    def timeslotar(self, tempo):
        """Dado um tempo qualquer, calcula em que timeslot eles caem"""
        tempo = tempo - self.inicio
        minu = tempo.total_seconds()/60.0
        resto = minu%15
        # A mensagem nao caiu em nenhum timeslot valido
        if resto > 5.0 and resto < 10.0:
            return -1
        else:
            return int(round((minu+0.1)/15,0))

#
# Generic Double-fork based Daemon
#

class Daemon:
    """
    A generic daemon class. From Sander Marechal 
      <http://www.jejik.com/authors/sander_marechal/>

    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        Do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        or http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/
        """
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("[AA] Fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("[AA] Fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid())
        file(self.pidfile,'w+').write("%s\n" % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        """
        Start the daemon
        """
        # Check for a pidfile to see if the daemon already runs
        try:
            pf = file(self.pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

            if pid:
                message = "[AA] pidfile %s already exists. Daemon already running?\n"
                sys.stderr.write(message % self.pidfile)
                sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """
        Stop the daemon
        """

        pid = self.getpid()
        if not pid:
            message = "[AA] pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
                else:
                    print(str(err))
                    sys.exit(1)
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    def run(self):
        """
        You should override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """
        pass

    def getpid(self):
        # Get the pid from the pidfile
        try:
            pf = file(self.pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        return pid

#
# AA Daemon
#

class AADaemon(Daemon):
    """
    The AA daemon. The function run() runs forever notifying the user about the remaining time of
    his session.
    """
    def run(self):
        """
        This method runs forever (note the while true loop), notifying the user every N seconds.
        """
        self.logger = AALogger()

        avisos_padroes = 0
        avisos_tick = 0
        inicio = time.time()
        atual = time.time()
#        self.notify('Your session has started, %s. Programming, modafoca! :-)' %
        self.notify('Your session has started, %s.' %
                   get(['user','nickname']))
        s = Slotador()
        while True:
            tick = int(get(['user','tick']))
            prox_aviso_padrao = 10*60 + avisos_padroes * 15*60
            prox_aviso_tick = avisos_tick * tick
            if prox_aviso_padrao < prox_aviso_tick:
                prox_aviso = prox_aviso_padrao
                avisos_padroes += 1
            else:
                prox_aviso = prox_aviso_tick
                avisos_tick += 1
            dormir = prox_aviso + inicio - atual
            if dormir > 0:
                time.sleep(float(dormir))
                atual = time.time()
                minutos = int((atual-inicio)/60)
                #segundos = int((atual-inicio)%60)
                s.atualizar()
                if not s.atual_respondido():
                    self.notify('Tic-tac... '+str(minutos)+\
                                ' minutos' )
                    self.logger.log('notify') # precisamos notificar isso no log?
                    # FIXME: notificar a cada X minutos e informar quanto tempo falta
                    # FIXME: como verificar que o usuario logou? fica a cargo do servidor?
    def notify(self, msg):
        """
        A simple wrapper to Ubuntu's notify-send.
        """
        #os.system('notify-send "AA [%s]: " "%s"' % (time.strftime("%Y-%m-%d %H-%M-%S"), msg))
        pynotify.Notification("AA [%s]" % time.strftime("%Y-%m-%d %H-%M-%S"),
                              msg, 'face-monkey').show()
        os.system('espeak -v pt "%s"' % msg)

    def notify_english(self, msg):
        """
        variant of notify above, for english
        """
        #os.system('notify-send "AA [%s]: " "%s"' % (time.strftime("%Y-%m-%d %H-%M-%S"), msg))
        pynotify.Notification("AA [%s]" % time.strftime("%Y-%m-%d %H-%M-%S"),
                              msg, 'face-monkey').show()
        os.system('espeak "%s"' % msg)

#
# AA HTTP Sender
#

class AAHTTPSender:
    """
    The AA HTTP Sender module. It sends the HTTP messages to the server.
    """
    def send(self, msg):
        """
        Sends the msg to the server, encoding it apropriatelly.
        """

        dic = {'json': msg}
        data = urllib.urlencode(dic)
        req = urllib2.Request(get(['server', 'url']), data.encode('ascii'))
        res = urllib2.urlopen(req)
        res.close()

    def send_log(self):
        """
        Uses the send() method to send every line of the ~/.aa.log to the server.
        """
        home = os.getenv('HOME')
        f = open(home + '/.aa.log', 'r')
        alerts = f.read().splitlines()
        f.close()

        d = [{'user': get(['user','nickname']), 'date': a.split(',')[:2][0], 'log': a.split(',')[:2][1]} for a in alerts]
        for linha in d:
            ret =  linha['log'].split(' ', 1)
            if len(ret) == 2:
                for tipo in ['scream', 'say', 'oalert', 'shout']:
                    ret[0] = ret[0].replace(tipo, 'alert')
                linha['log'] = ret[0] + ' ' + ret[1]
        j = json.dumps(d)
        self.send(j)

#
# AA Logger
#

class AALogger:
    """
    The AA Logger module. It writes every msg to the ~/.aa.log file.
    """
    def __init__(self):
        """
        Creates the logger and set the log file path to ~/.aa.log.
        """
        self.log_filename = os.getenv('HOME') + '/.aa.log'

    def write(self, msg):
        """
        A wrapper to append msg to ~/.aa.log.
        """
        self.log_file = open(self.log_filename, 'a')
        self.log_file.write(msg)
        self.log_file.close()

    def log(self, msg):
        """
        A wrapper to log msg to ~/.aa.log.
        """
        self.write(time.strftime("%Y-%m-%d %H-%M-%S") + ',' + msg + '\n')

    def start(self):
        """
        Starts the logger by creating/overwriting the ~/.aa.log temp file.
        """
        self.log_file = open(self.log_filename, 'w')



class Console():

    def __init__(self):
        # Creating the AA modules

        # Here we create a logger obj to log every msg to the ~/.aa.log
        self.logger = AALogger()

        # And this module deals with the HTTP server
        self.http_sender = AAHTTPSender()

        # Here the daemon that notifies the user every N seconds
        # /tmp/aad.pid has the PID of the forked daemon
        self.daemon = AADaemon('/tmp/aad.pid')

    def send_scream(self, msg):
        # log a scream action
        self.logger.log('shout ' + msg)
        # send the msg to the HTTP server, so it'll be online imediatelly!
        j = json.dumps([{'user': get(['user','nickname']), 'date': time.strftime("%Y-%m-%d %H-%M-%S"), 'log': 'shout ' + msg}])
        self.http_sender.send(j)

    def stop(self):
        if not self.daemon_running():
          print('[AA] Daemon not running, so no point in trying to stop it.')
          sys.exit(0)
        # log a stop session action
        self.logger.log('stop')
        # the daemon notifies that the session is finished
        self.daemon.notify_english('Your session has finished. Dont forget to record your screencast.')
        # kill the daemon
        self.daemon.stop()

    def daemon_running(self):
        if self.daemon.getpid() is not None:
            return True
        else:
            return False

    def start(self):
        init_config()
        # checks if the user nickname is defined
        if get(['user','nickname']) is '':
            print('[AA] Please, set your nickname before start hacking. Use: aa config user.nickname <YOUR NICKNAME>.')
            sys.exit(0)

        # start the logger (overwrite or create the ~/.aa.log file)
        self.logger.start()
        # log a start session action
        self.logger.log('start')
        # fork the daemon and exit
        self.daemon.start()

    def push(self):
        # log a push action
        self.logger.log('push')
        # send all the lines at ~/.aa.log file
        self.http_sender.send_log()
        # notify to the user the push action
#        self.daemon.notify_english('Session pushed to the server. Now get away of this fucking laptop and go fuck.')
        self.daemon.notify_english('Session pushed to the server.')

    # FIXME: I'm tired now, but this would be more interesting in a proper class
    def get_trac_tickets(self, sf_user=None):
        if sf_user is not None:
            nick = sf_user
        else:
            nick = get(['user','nickname'])
        req = urllib2.Request('http://sourceforge.net/apps/trac/labmacambira/report/1?format=tab')
        res = urllib2.urlopen(req)
        tab = csv.DictReader(res, delimiter='\t')
        c = 0
        print('\n')
        for line in tab:
            if (nick in line['owner']) or ('everyone' in line['owner']):
                print("   #%-10s %-20s %s" % (line['ticket'], line['component'], line['summary']))
                c += 1
        if c is not 0:
            print('\n[AA] You have %s active tickets. Lets hack modafoca!' % c)
        else:
            print('\n[AA] You dont have active tickets actually.')

    def process_args(self):
        # Parsing console arguments
        # FIXME: talvez usar o argparse?
        args = sys.argv[1:]
        if len(sys.argv) > 1:
            # START
            if args[0] in ['start', 'inicio', 'inicia', 'início', 'begin']:
                if not self.daemon_running():
                    self.start()
                    # inform to the user at console
                    print('[AA] Your session has started. Happy hacking!')
                else:
                    print('[AA] Error: Daemon seems to be already running. Try to stop and start again')

            # REVIVE
            elif args[0] in ['revive','ressuscitar', 'resurrect', 'reviver']:
                if not self.daemon_running():
                    print('[AA] What have you done? Run to the hills! The daemon has been'+\
                    ' ressurected and will unleash hell upon us ALL!')
                    self.daemon.start()
                    # inform to the user at console
                else:
                    print('[AA] These dark magics are not needed now. The daemon '+\
                    'is already alive and spreading chaos upon the world.')

            # STOP
            elif args[0] in ['stop','fim', 'finaliza', 'termina', 'end']:
                self.stop()
                # inform to the user at console
                print('[AA] Your session has finished. Dont forget to record your screencast.')

            # ALERT
            elif args[0] in ['alert', 'informa', 'marca', 'anota', 'msg', 'post']:
                if len(args) < 2:
                  print('[AA] Please specify a message to post. Use: aa %s <message>'  % args[0])
                  sys.exit(0)

                # no matter if we use quotes or not after the "aa alert"
                msg = ''.join([pal+" " for pal in sys.argv[2:]])
                msg = msg.strip()
                # log a alert action
                self.logger.log('alert ' + msg)
                # inform the user
                print('[AA] New alert: "%s" logged.' % msg)

            # SCREAM
            # Esses nomes estao sendo usados no PUSH! Se alterar aqui, altere
            # lá!
            elif args[0] in ['scream', 'say', 'oalert', 'shout']:
                if len(args) < 2:
                  print('[AA] Please specify a message to say. Use: aa %s <message>'  % args[0])
                  sys.exit(0)
                  
                msg = ''.join([pal+" " for pal in sys.argv[2:]])
                msg = msg.strip()
                self.send_scream(msg)
                # inform the user
                print('[AA] New shout: "%s" logged.' % msg)

            # CONFIG
            elif args[0] in ['config', 'configura', 'seta']:
                if len(args) < 3:
                  print('[AA] Missing arguments. Use: aa %s <config> <value>'  % args[0])
                  sys.exit(0)
                config(sys.argv[2:])

            # STATUS
            elif args[0] in ['status', 'st']:
                if self.daemon_running():
                    print('[AA] daemon is up and running... (pid: %s)' % self.daemon.getpid())
                else:
                    print('[AA] Oh nooo! daemon is not running... Get back to work!!!')

            # LOGVIEW
            elif args[0] in ['logview', 'viewlog']:
                os.system('less ' + os.getenv('HOME') + '/.aa.log')

            # TIMESLOTS
            elif args[0] in ['timeslots', 'ts', 'slots', 'time']:
                s = Slotador()
                print("Trabalhando ha: "+str(s.decorridos_m)+" minutos")
                print("Faltam: "+str(s.faltam_m)+" minutos")
                print("Tempo até proximo timeslot: "+str(s.prox_time)+" minutos")
                print("")
                print("Timeslots:")
                print("respondidos: "+str(s.respondidos))
                print("perdidos: "+str(s.perdidos))
                if len(s.perdidos) == 0:
                    print("Muito bem! Agora continue trabalhando!")
                else:
                    print("NOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO!")

            # PUSH
            elif args[0] in ['push']:
                self.push()
                print '[AA] Session pushed to the server.'

            # TICKETS
            elif args[0] in ['tickets']:
                if len(args) >= 2:
                    self.get_trac_tickets(args[1])
                else:
                    self.get_trac_tickets()

            # VIEWTICKET
            elif args[0] in ['viewticket', 'showticket']:
                if len(args) < 2:
                    print '[AA] Missing arguments. Use: aa %s <ticket number>'  % args[0]
                    sys.exit(0)
                print '[AA] Openning ticket #%s in your browser...' % args[1]
                os.system('firefox http://sourceforge.net/apps/trac/labmacambira/ticket/%s' % args[1])
            
            # UNKNOWN OPTION
            else:
                print'[AA] Unknown option: "%s". Please, try again!' % args[0]
                sys.exit(2)
                sys.exit(0)
        else:
            print guide
            sys.exit(2)

#
# Main Function (start here!)
#

if __name__ == "__main__":
    c = Console()
    c.process_args()
