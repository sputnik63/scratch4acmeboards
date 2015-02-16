#!/usr/bin/env python
#scratch4acmeboards_handler - control AcmeSystems boards GPIO ports using Scratch. http://www.acmesystems.it/
#Copyright (C) 2015 by Francesco Rotondella based on original code for Raspberry Pi by Simon Walters
#Copyright (C) 2013 by Simon Walters based on original code for PiFace by Thomas Preston

#This program is free software; you can redistribute it and/or
#modify it under the terms of the GNU General Public License
#as published by the Free Software Foundation; either version 2
#of the License, or (at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__version__ = 'v0.2' # Feb 2015
import threading
import socket
import time
import sys
import datetime as dt
import os
import s4ah_GPIOController as S4AH
import logging.handlers
import subprocess
from optparse import OptionParser
import scratch


class ScratchSender(threading.Thread):

    def __init__(self, session):
        threading.Thread.__init__(self)
        self.session = session
        self.scratch_socket = session.socket
        self._stop = threading.Event()
        #self.sleepTime = 0.1
        logger.debug("Sender Init")

    def stop(self):
        self._stop.set()
        logger.debug("Sender Stop Set")

    def stopped(self):
        return self._stop.isSet()

    def setsleepTime(self, sleepTime):
        self.sleepTime = sleepTime
        #print("sleeptime:%s", self.sleepTime )

    def run(self):
        logger.debug("Sender running in thread %s ...", self.name)
        #lastPinUpdateTime = time.time()
        lastTimeSinceLastSleep = time.time()
        self.sleepTime = 0.1

        while not self.stopped():
            try:
                loopTime = time.time() - lastTimeSinceLastSleep
                if loopTime < self.sleepTime:
                    sleepdelay = self.sleepTime -loopTime
                    time.sleep(sleepdelay) # be kind to cpu  :)
                    time.sleep(10) # be kind to cpu  :)
                lastTimeSinceLastSleep = time.time()

                bcast_dict = {}
                # check if there is a change in the input pins
                for key in s4ahGC.ValidPins:
                    if s4ahGC.ValidPins[key].mode == s4ahGC.PINPUT:
                        currVal = s4ahGC.pinRead(s4ahGC.ValidPins[key].name)
                        if currVal != s4ahGC.ValidPins[key].value:
                            s4ahGC.ValidPins[key].value = currVal
                            bcast_dict['pin'+s4ahGC.ValidPins[key].name] = currVal
                            logger.debug("Change detected in pin:%s changed to:%s", s4ahGC.ValidPins[key].name, currVal)
                            time.sleep(0.05) # just to give Scratch a better chance to react to event

                if bcast_dict:
                    logger.debug('sending: %s', bcast_dict)
                    self.session.sensorupdate(bcast_dict)

            except scratch.ScratchError, e:
                logger.debug("sender raise ScratchError %s", e)
                cycle_trace = 'disconnected'
            except (KeyboardInterrupt, SystemExit):
                logger.debug("raise error")
                raise
            except socket.timeout:
                #logger.debug("No data received: socket timeout")
                continue
            except Exception:
                continue


class ScratchListener(threading.Thread):
    """
    Class used by the thread listening fro Scratch
    """
    def __init__(self, session):
        threading.Thread.__init__(self)
        self.session = session
        self.scratch_socket = session.socket
        self._stop = threading.Event()
        self.value = None
        self.valueNumeric = None
        logger.debug("Listener Init")

    def send_scratch_command(self, cmd):
        """
        Send a message to Scratch
        """
        n = len(cmd)
        b = (chr((n >> 24) & 0xFF)) + (chr((n >> 16) & 0xFF)) + (chr((n >> 8) & 0xFF)) + (chr(n & 0xFF))
        self.scratch_socket.send(b + cmd)

    def parseItemValue(self, inValue):
        """
        Parse the value received in a sensor-update or in a broadcast command
        Admitted values: on, off, 1, 0 (as strings) or a numeric value
        """
        if inValue == '':
            self.value = None
            return True
        else:
            self.value = inValue

        if inValue == 'on' or inValue == '1':
            self.valueNumeric = 1
            return True
        elif inValue == 'off' or inValue == '0':
            self.valueNumeric = 0
            return True
        elif s4ahGC.isNumeric(inValue):
            self.valueNumeric = inValue
            return True
        else:
            return False

    def stop(self):
        """
        Set the thread as stopped
        """
        self._stop.set()

    def stopped(self):
        """
        Check if this thread is stopped
        """
        return self._stop.isSet()

    def listen(self):
        """
        Function to listen to messages from Scratch
        """
        global cycle_trace
        while not self.stopped():
            try:
                yield self.session.receive()
            except scratch.ScratchError, e:
                logger.debug("listener raises ScratchError %s", e)
                cycle_trace = 'disconnected'
                raise
            except (KeyboardInterrupt, SystemExit):
                logger.debug("raise error")
                raise
            except socket.timeout:
                #logger.debug("No data received: socket timeout")
                continue
            except Exception, e:
                logger.error("Unknown exception %s", e)
                continue

    def parseBroadcast(self, msgToParse):
        """
        Parse a broadcast message. Allowed messages:
        pinpattern followed by a sequence of 0 and 1 (e.g. pinpattern 01011110)
        pinXXNNon, pinXXNNoff (e.g pinPA25on, pinPA8off): to set the single pin XXNN on or off
        allon, alloff: to set all the pins on the board on or foo
        sghdebugon, sghdebugoff (or also sghdebug on, sghdebug off): to turn the debug on or off
        gettime: to get the board date and time
        getip: to get board ip address
        getversion: to get the scratch4acmeboards version
        shutdown: to shutdown the board
        stophandler: to stop the handler
        """
        (cmdItem, cmdItemNum, cmdItemValue) = ('', '', '')
        cmdItemValueLen = 0

        # maybe pinpattern command will be soon removed since not all the Acmesystems
        # boards have a pin ordered numeration that can be used in this way
        if msgToParse.startswith('pinpattern'):
            cmdItem = 'pinpattern'
            cmdItemValue = msgToParse[len(cmdItem):].strip()
        elif msgToParse.startswith('pin'):
            cmdItem = 'pin'
            if msgToParse.endswith('on'):
                cmdItemValue = 'on'
                cmdItemValueLen = -2
            elif msgToParse.endswith('off'):
                cmdItemValue = 'off'
                cmdItemValueLen = -3
            else:
                raise Exception("Unknown command: " + msgToParse)
            cmdItemNum = msgToParse[3:cmdItemValueLen]
            return (cmdItem, cmdItemNum, cmdItemValue)
        elif msgToParse.startswith('all'):
            cmdItem = 'all'
            if msgToParse.endswith('on'):
                cmdItemValue = 'on'
            elif msgToParse.endswith('off'):
                cmdItemValue = 'off'
            else:
                raise Exception("Unknown command: " + msgToParse)
            return (cmdItem, cmdItemNum, cmdItemValue)
        elif msgToParse.startswith('sghdebug'):
            cmdItem = 'sghdebug'
            if msgToParse.endswith('on'):
                cmdItemValue = 'on'
            elif msgToParse.endswith('off'):
                cmdItemValue = 'off'
            else:
                raise Exception("Unknown command: " + msgToParse)
            return (cmdItem, cmdItemNum, cmdItemValue)
        elif msgToParse.startswith('gettime'):
            cmdItem = 'gettime'
            return (cmdItem, cmdItemNum, cmdItemValue)
        elif msgToParse.startswith('getip'):
            cmdItem = 'getip'
            return (cmdItem, cmdItemNum, cmdItemValue)
        elif msgToParse.startswith('getversion'):
            cmdItem = 'getversion'
            return (cmdItem, cmdItemNum, cmdItemValue)
        else:
            raise Exception("Unknown command: " + msgToParse)


    def parseSensorUpdate(self, msgToParse):
        """
        Parse a broadcast message. Allowed sensor:
        pinXXyyon, pinXXyyoff (e.g pinPA25on, pinPA8off)
        """
        (cmdItem, cmdItemNum) = ('', '')
        if msgToParse.startswith('pin'):
            cmdItem = 'pin'
            cmdItemNum = msgToParse[3:]
            return (cmdItem, cmdItemNum)


    def run(self):
        """
        This is the main listening thread routine
        """
        global cycle_trace

        logger.debug("Listener running as thread %s ...", self.name)

        debugLogging = True
        try:
            for msg in self.listen():
                msgType = msg[0]

                cmdList = []    # used to hold lists of all broadcasts or sensor updates
                singleCmd = []  # singleCmd holds list of single broadcast or sensor update

                if msgType == 'broadcast':
                    for item in msg[1:]:
                        try:
                            (cmdItem, cmdItemNum, cmdItemValue) = self.parseBroadcast(msg[1])
                            cmdList.append((cmdItem, cmdItemNum, cmdItemValue))
                        except Exception as ex:
                            #template = "{0} exception occured parsing " + msg[1] + ": {1!r}"
                            #message = template.format(type(ex).__name__, ex.args)
                            message = "Error parsing sensor-update " + msg[1]
                            logger.error(message)
                            continue
                elif msgType == 'sensor-update':
                    for item in msg[1:]:
                        for key in item.keys():
                            try:
                                (cmdItem, cmdItemNum) = self.parseSensorUpdate(key)
                                cmdList.append((cmdItem, cmdItemNum, item[key]))
                            except Exception as ex:
                                #template = "{0} exception occured parsing " + key + ": {1!r}"
                                #message = template.format(type(ex).__name__, ex.args)
                                message = "Error parsing sensor-update " + key
                                logger.error(message)
                                continue
                else:
                    logger.error("Unknown message type: %s", msgType)

                logger.debug("cmdList: %s", cmdList)

                for singleCmd in cmdList:
                    (cmdItem, cmdItemNum, cmdItemValue) = singleCmd

                    if not self.parseItemValue(cmdItemValue):
                        logger.error("Unable to parse value %s ", cmdItemValue)
                        continue

                    if cmdItem == 'sghdebug':
                        if (self.value == "1") and (debugLogging):
                            logging.getLogger().setLevel(logging.DEBUG)
                            debugLogging = True
                        if (self.value == "0") and (debugLogging):
                            logging.getLogger().setLevel(logging.INFO)
                            debugLogging = False

                    elif cmdItem == 'pin':
                        s4ahGC.pinUpdate(cmdItemNum, self.valueNumeric)

                    elif cmdItem == 'all':
                        s4ahGC.pinUpdateAll(self.valueNumeric)

                    #Use bit pattern to control ports
                    elif cmdItem == 'pinpattern':
                        if self.value == None:
                            # assume that an empty value received means a reset all pin
                            self.value = '0'*len(s4ahGC.ValidPins)

                        svalue = self.value

                        # build bitpattern adding 0s at the beginning of the pitpattern received
                        bit_pattern = ('0'*(len(s4ahGC.ValidPins)-len(svalue)))+svalue
                        logger.debug('bit_pattern %s', bit_pattern)
                        logger.debug("commands received: %s", singleCmd)
                        logger.debug("pattern value %s", cmdItemValue)
                        j = 0
                        onSense = '0'
                        for i in range(s4ahGC.numOfValidPins):
                            logger.debug("analyzing pin %s use %s", s4ahGC.ValidPins[i].name, s4ahGC.ValidPins[i].mode)
                            if (s4ahGC.ValidPins[i].mode == s4ahGC.PUNUSED) or (s4ahGC.ValidPins[i].mode == s4ahGC.POUTPUT):
                                logger.debug("trying to update pin to %s", bit_pattern[-(j+1)])
                                if bit_pattern[-(j+1)] == onSense:
                                    s4ahGC.pinUpdate(s4ahGC.ValidPins[i].name, 0)
                                else:
                                    s4ahGC.pinUpdate(s4ahGC.ValidPins[i].name, 1)
                                j = j + 1
                    ### Check for other broadcast type messages being received

                    if cmdItem == 'gettime':
                        now = dt.datetime.now()
                        logger.debug("gettime %s", now)
                        fulldatetime = now.strftime('%Y%m%d%H%M%S')
                        hrs = fulldatetime[-6:-4]
                        minutes = fulldatetime[-4:-2]
                        secs = fulldatetime[-2:]
                        bcast_dict = {'fulldatetime':fulldatetime, 'hours':hrs, 'minutes':minutes, 'seconds':secs}
                        logger.debug('sending: %s', bcast_dict)
                        self.session.sensorupdate(bcast_dict)

                    elif cmdItem == 'getip': #find ip address
                        logger.debug("Finding IP")
                        arg = 'ip route list'
                        p = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
                        ipdata = p.communicate()
                        split_data = ipdata[0].split()
                        ipaddr = split_data[split_data.index('src')+1]
                        logger.debug("IP:%s", ipaddr)
                        bcast_dict = {'ipaddress':ipaddr}
                        self.session.sensorupdate(bcast_dict)

                    elif cmdItem == 'getversion':
                        bcast_dict = {'version':__version__}
                        logger.debug('sending: %s', bcast_dict)
                        self.session.sensorupdate(bcast_dict)

                    elif cmdItem == 'shutdown':
                        os.system('sudo shutdown -h "now"')

                    elif cmdItem == 'stophandler':
                        logger.debug("stop handler msg sent from Scratch")
                        cleanup_threads((listener, sender))
                        sys.exit(0)
        except scratch.ScratchError, e:
            logger.error("Error: %s", e)
            #raise
    ###  End of  ScratchListner Class


def cleanup_threads(threads):
    """
    Exiting or when some important error occurs (like a connection broken)
    try to clean threads, stopping them
    """
    logger.debug("cleanup threads started")

    for thread in threads:
        thread.stop()
    logger.debug("Threads told to stop")

    logger.debug("Waiting for join on main threads to complete")
    #for thread in threads:
    #    thread.join(1)
    main_thread = threading.currentThread()
    for thread in threading.enumerate():
        if thread is main_thread or thread.getName().startswith("Dummy"):
            # debugging with Eclipse when stopped in break in one thread a lot of
            # Dummy threads are created and an exception is raised when trying to stop them
            continue
        logger.debug('joining %s', thread.getName())
        thread.join()

    for thread in threads:
        logger.debug("thread %s is %s", thread.getName(), "alive" if thread.isAlive() else "dead")

    #s4ahGC.resetPinMode()
    logger.debug("cleanup threads finished")


######### Main Program Starts Here

if __name__ == '__main__':
    #Set some constants and initialise lists

    # max number of connection attemps. If you like to try forever, set 0
    MAXATTEMPTS = 30
    PORT = 42001
    DEFAULT_HOST = '192.168.10.20'  # default Arietta board ip address
    DEFAULT_BOARD = 'Arietta_G25'   # default board used
    BUFFER_SIZE = 512               # this value should be enough

    # options parsing
    parser = OptionParser("usage: %prog [options]")
    parser.add_option('-o','--offline',dest="offline",action="store_true",default=False,help='option to use for local tests without Arietta board')
    parser.add_option('-m','--mesh',type='string',dest="ipaddress",default=DEFAULT_HOST,help='ip address where mesh (Scratch) is running. Default 192.168.10.20')
    parser.add_option('-d','--debug',dest="debug",action="store_true",default=False,help='Set logging level to DEBUG. Default is WARNING')
    parser.add_option('-p','--printtostdout',dest="printtostdout",action="store_true",default=False,help='Print all log messages to stdout. Default logs to /tmp/scratch4acmeboards.log')
    parser.add_option('-b','--boardname',dest="boardname",default=DEFAULT_BOARD,help='ACMESystems board name among Arietta_G25 (default), Daisy, Acqua_A5, FOX_Board_G20, Aria_G25')
    options,args = parser.parse_args()

    offline = options.offline
    host = options.ipaddress
    debugflag = options.debug
    printFlag = options.printtostdout
    boardName = options.boardname

    if debugflag:
        logLevel = logging.DEBUG
    else:
        logLevel = logging.INFO

    # log on a rolling file in /tmp and error messages also in console
    LOG_FILENAME = "/tmp/scratch4acmeboards.log"
    logger = logging.getLogger('s4ah_root_logger')
    if printFlag:
        logging.basicConfig(stream=sys.stdout,
                            filemode='w', level=logLevel,
                            format="%(asctime)s - %(module)s.%(funcName)s %(lineno)d: %(message)s",
                            datefmt='%d/%m/%Y %H:%M:%S')
        handler = logging.StreamHandler()
    else:
        logging.basicConfig(filename=LOG_FILENAME,
                            filemode='w', level=logLevel,
                            format="%(asctime)s - %(module)s.%(funcName)s %(lineno)d: %(message)s",
                            datefmt='%d/%m/%Y %H:%M:%S')
        handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=20000000, backupCount=2)

    logger.addHandler(handler)
    consoleHandler = logging.StreamHandler()
    logger.addHandler(consoleHandler)

    # create a controller instance
    try:
        s4ahGC = S4AH.GPIOController(boardName, offline)
    except S4AH.S4AHException, e:
        logger.error("Error: %s", e)
        logger.error("Exiting ... bye")
        sys.exit(1)

    #SCRIPTPATH = os.path.split(os.path.realpath(__file__))[0]
    #logger.debug("PATH:%s", SCRIPTPATH)
    numAttempts = MAXATTEMPTS
    cycle_trace = 'start'

    while True:
        try:
            if cycle_trace == 'start':
                # open the socket trying each 3 seconds
                logger.info('Trying to connect...')
                time.sleep(3)
                s = scratch.Scratch(host)
                the_socket = s.socket
                logger.info('Connected!')
                listener = ScratchListener(s)
                sender = ScratchSender(s)
                cycle_trace = 'running'
                logger.info("Running....")
                listener.start()
                sender.start()

            if cycle_trace == 'disconnected':
                logger.info("Scratch disconnected")
                cleanup_threads((listener, sender))
                logger.debug("Thread cleanup done after disconnect")
                s4ahGC.resetPinMode()
                logger.debug("Pin Reset Done")
                time.sleep(1)
                cycle_trace = 'start'

            time.sleep(0.01) # needed to catch keyboard interrupts

        except scratch.ScratchError:
            logger.info("There was an error connecting to Scratch!")
            logger.info("I couldn't find a Mesh session at host: %s, port: %s", host, PORT)
            numAttempts -= 1
            if MAXATTEMPTS != 0 and numAttempts == 0:
                sys.exit(0)
        except KeyboardInterrupt:
            logger.debug("Keyboard Interrupt")
            try:
                cleanup_threads((listener, sender))
                logger.debug("Thread cleanup done after disconnect")
            except NameError:
                # needed if the KeyboardInterrupt occurs during the connectins attempt
                # before that a listener or sender instance is created
                pass
            s4ahGC.resetPinMode()
            logger.debug("Pin Reset Done")
            sys.exit(0)
            logger.debug("CleanUp complete")
        except scratch.ScratchConnectionError, e:
            logger.error("ScratchConnectionError %s", e)
        except Exception, e:
            logger.error("Unknown error %s", e)

#### End of main program
