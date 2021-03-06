#!/usr/bin/env python
#s4ah_GPIOController - control Acme Systems boards GPIO ports using ablib by Sergio Tanzilli
#Copyright (C) 2015 by Francesco Rotondella based on the work of Simon Walters for Rasberry Pi
#Copyright (C) 2013 by Simon Walters

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


import ablib as AB
import os
import logging


class S4AHException(Exception):
    pass

logger = logging.getLogger('s4ah_root_logger')

# Supported AcmeSystems boards
supportedBoards = ['Arietta_G25']
connector_name = {'Arietta_G25'   : ['J4.'],
                  'Aria_G25'      : ['N', 'E', 'S', 'W'],
                  'FOX_Board_G20' : ['J7.', 'J6.'],
                  'Daisy'         : [ 'D1.',  'D2.',  'D3.',  'D4.',  'D5.',  'D6.',  'D7.',  'D8.',
                                      'D10.', 'D11.', 'D12.', 'D13.', 'D14.', 'D15.', 'D16.', 'D17.' ],
                  'Acqua_A5'      : ['J1.', 'J2.', 'J3.'],
                  }

                  
PNONE = 255
# to mantain aligned with ablib modes in pinmode
POUTPUT = 'OUTPUT'
PINPUT  = 'INPUT'
PUNUSED = 'NOTUSED'  # unused pins are set to INPUT mode


class PinData():
    """
    Here are all the useful info about a single pin
    """
    def __init__(self, instance, name):
        self.instance = instance
        self.thread = None   # used to stop the threads started in INPUT mode
        self.name = name       # pin label according the board layout (usually the MCU name e.g PA23)
        self.mode = PUNUSED    # it can be PUNUSED, POUTPUT, PINPUT
        self.value = PNONE
        self.kernelId = AB.pinname2kernelid(name)
        self.invert = False

    def __repr__(self):
        return "Pin %s, mode %s, value %f" % (self.name, self.mode, self.value)


class GPIOController:

    def getRevision(self):
        """
        Gets the version number of the Arietta board
        """
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Revision'):
                        return 1 if line.rstrip()[-1] in ['2', '3'] else 2
                else:
                    return 0
        except:
            return 0

    def __init__(self, boardName, offline):
        self.boardName = boardName
        self.ValidPins = {}
        self.PNONE = PNONE
        self.POUTPUT = POUTPUT
        self.PINPUT = PINPUT
        self.PUNUSED = PUNUSED
        
        #if self.boardName not in supportedBoards:
            #message = "board " + self.boardName + " not yet supported"
            #raise S4AHException (message)

        if offline:
            # for developers only: this is only for testing offline with
            # an ablib modified to write on /tmp instead of real /sys area
            testdir = "/tmp/ablib/sys/class/gpio/"
            val = '0'
            if self.boardName != 'Aria_G25':
                for key in AB.mcuName2pinname[self.boardName]:
                    dirname = testdir + "pio" + key[1:]
                    if not os.path.exists(dirname):
                        os.makedirs(dirname)
                        fh = open(dirname + "/value", 'w')
                        fh.write(val)
                        fh.close()
            else:
                for key in AB.pin2kid.keys():
                    for elem in connector_name[self.boardName]:
                        if key.startswith(elem):
                            dirname = testdir + "pio" + key[1:]
                            if not os.path.exists(dirname):
                                os.makedirs(dirname)
                                fh = open(dirname + "/value", 'w')
                                fh.write(val)
                                fh.close()                
            fh = open(testdir + "export", 'w')
            fh.close()
            fh = open(testdir + "unexport", 'w')
            fh.close()
            # end for developers only

        try:
            # check the correct version of ablib
            test_version = AB.getVersion()
            if test_version:
                pass
        except AttributeError, e:
            message = "Not supported ablib version " + str(e)
            raise S4AHException (message)

        self.piRevision = self.getRevision()
        logger.debug("Board Revision %s", self.piRevision)

        # map the pinname to mcuName creating the reverse map of the ablib
        # mcuName2pinname dict: this is needed to store in PinData the mcuName
        # inv_map = {v:k for k, v in AB.mcuName2pinname[self.boardName].items()}

        # read from ablib the available pins
        if self.boardName != 'Aria_G25':
            for key in AB.mcuName2pinname[self.boardName].keys():
                self.ValidPins[key] = PinData(None, key)
                logging.debug ("Configured pin %s", self.ValidPins[key])
        else:
            #Aria G25 has the pin name already ok in pin2kid dictionary of ablib
            for key in AB.pin2kid.keys():
                for elem in connector_name[self.boardName]:
                    if key.startswith(elem):
                        self.ValidPins[key] = PinData(None, key)
                        logging.debug ("Configured pin %s", self.ValidPins[key])

        self.numOfValidPins = len(self.ValidPins)
        # End init


    def resetAllPins(self):
        """
        reset all pins
        """
        logger.debug("resetting all pins")
        for key in self.ValidPins:
            if self.ValidPins[key].mode != PUNUSED:
                self.resetPin(self.ValidPins[key].name)


    def resetPin(self, pinName):
        """
        reset all pins
        """
        pinName = pinName.upper()
        if pinName not in self.ValidPins.keys():
            logger.error("unknown pin %s", pinName)
            return

        if  self.ValidPins[pinName].mode != PUNUSED:
            # set the default mode to OUTPUT: INPUT mode with trigger
            # should start one thread for each pin
            self.ValidPins[pinName].instance = None
            AB.Pin(pinName, POUTPUT)
            self.ValidPins[pinName].mode = PUNUSED
            self.ValidPins[pinName].value = PNONE
            self.ValidPins[pinName].invert = False
            logger.debug("reset pin %s", pinName)


    def setAllPins(self, mode):
        """
        set all pins with the passed mode
        """
        logger.debug("setting all pins to %s", mode)
        for key in self.ValidPins:
            self.setPinMode(self.ValidPins[key].name, mode)


    def setPinMode(self, pinName, mode):
        """
        set pin mode for a single pin
        """
        pinName = pinName.upper()
        if pinName not in self.ValidPins.keys():
            logger.error("setPinMode: unknown pin %s", pinName)
            return
            
        if self.ValidPins[pinName].mode == mode:
            logger.debug("pin mode not changed: do nothing")
            return

        self.ValidPins[pinName].mode = mode
        AB.Pin(pinName, mode)
        logger.debug("pin %s set to %s mode", pinName, mode)


    def isNumeric(self, s):
        """
        check if the passed value is numeric
        """
        try:
            float(s)
            return True
        except ValueError:
            return False


    def pinUpdate(self, pinName, value):
        """
        main function to update a pin: the passed name has to be a valid name. It has to be among the keys read
        from ablib and stored in ValidPins or it has to be into the available MCU names (also read from ablib)
        """

        pinName = pinName.upper()
        if pinName not in self.ValidPins.keys():
            logger.error("unknown pin %s", pinName)
            return

        if self.ValidPins[pinName].value == value:
            logger.debug("pin %s value %s not changed: do nothing", pinName, value)
            return
        else:
            logger.debug("update pin:%s value:%s use:%s to value:%s", pinName, self.ValidPins[pinName].value, self.ValidPins[pinName].mode, value)

         #if not self.isNumeric(value):
             #logger.error("Value %s not admitted: pin %s unchanged", value, pinName)
             #return

        try:
            logger.debug("pin %s commanded to be %s", pinName, value)
            if self.ValidPins[pinName].invert: # is True: Invert data value (useful for 7 segment common anode displays)
                value = 1 - abs(value)
            if self.ValidPins[pinName].mode == POUTPUT: # if already in output
                self.ValidPins[pinName].value = value
                self.ValidPins[pinName].instance.set_value(value) # set output to 1 or 0
                logger.debug("pin %s set to %s", pinName, value)

            elif self.ValidPins[pinName].mode in [PUNUSED, PINPUT]: # if pin is in input or not used
                old_mode = self.ValidPins[pinName].mode;
                self.ValidPins[pinName].mode = POUTPUT # switch it to output
                self.ValidPins[pinName].instance = AB.Pin(pinName, POUTPUT)
                self.ValidPins[pinName].value = value
                self.ValidPins[pinName].instance.set_value(value) # set output to 1 to 0
                logger.debug("pin %s was %s - now output to value %s", pinName, old_mode, value)

        except ValueError:
            logger.error("Error trying to update pin %s to value %s", pinName, value)
            pass
        except IOError, e:
            logger.error("Unable to access pin %s: %s", pinName, e)
            pass


    def pinRead(self, pinName):
        """
        read the single pin value: the passed name has to be a valid name. It has to be among the keys read
        from ablib and stored in ValidPins or it has to be into the available MCU names (also read from ablib)
        """

        pinName = pinName.upper()
        if pinName not in self.ValidPins.keys():
            logger.error("pinRead: unknown pin %s", pinName)
            return

        try:
            return AB.get_value(self.ValidPins[pinName].kernelId)
        except Exception, e:
            logger.error("Error reading pin %s: %s", pinName, str(e))
            return 0

    def setPinInvert(self, pinName, state=False):
        """
        invert the logic
        """
        pinName = pinName.upper()
        try:
            self.ValidPins[pinName].invert = state
        except ValueError, e:
            pass

    def setAllInvert(self, state=False):
        """
        invert all
        """
        for key in self.ValidPins:
            self.ValidPins[key].invert = state

    def pinUpdateAll(self, value):
        """
        update all the pins to the same value
        """
        logger.debug("pinUpdateAll to value %s", value)
        if value != 0 and value != 1:
            logger.error("Invalid value %s: pins unchanged", value)
            return

        for key in self.ValidPins:
            self.pinUpdate(self.ValidPins[key].name, value)

#### End of main program

