#!/usr/bin/env python                                                                                 
#installer for scratch4acmeboards
#scratch4acmeboards- control AcmeSystems boards GPIO ports using Scratch. http://www.acmesystems.it/
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

from optparse import OptionParser
import os
import shutil

class msgcolor:
    OKGREEN = '[ ' + '\033[92m OK \033[0m' + ' ] '
    WARNING = '[ ' + '\033[93m WARNING \033[0m' + ' ] '
    ERROR = '[ ' + '\033[91m KO \033[0m' + ' ] '
    ENDC = '\033[0m'
    BOLD = '\033[1m'

INSTALL_PREFIX = "/opt"
INSTALL_DIR = "scratch4acmeboards"
files = ["scratch4acmeboards_handler.py", "s4ah_GPIOController.py"]

parser = OptionParser("usage: %prog [options]")
parser.add_option('-p','--prefix',dest="installprefix",default=INSTALL_PREFIX,help='installation path. Default: /opt')
options,args = parser.parse_args()
installprefix = options.installprefix

errors = []
warnings = []

print ""
#verify ablib is installed
package = 'ablib'
try:
    ablib = __import__(package)
    print msgcolor.OKGREEN + "ablib present" 

    # check the correct version of ablib
    test_version = ablib.getVersion()
    if test_version:
        print "found ablib version " + test_version
except AttributeError:
    message = "not supported ablib version.\n              Please download it from github"
    warnings.append (message)
except ImportError:
    message = "\033[1mablib\033[0m module not installed\n              Please download it from github"
    warnings.append (message)

#verify scratchpy is installed
package = 'scratch'
try:
    scratchpy = __import__(package)
    print msgcolor.OKGREEN + "scratchpy present" 
except ImportError:
    message = "\033[1mscratchpy\033[0m module not installed\n              Please download it from github"
    warnings.append (message)


installpath = installprefix + "/" + INSTALL_DIR
try:
    if not os.path.exists(installpath):
        os.makedirs(installpath)
    for elem in files:
        shutil.copyfile(elem, installpath + "/" + elem)
except Exception, e:
    errors.append (str(e))

#printing reports
for elem in warnings:
    print msgcolor.WARNING + elem

for elem in errors:
    print msgcolor.ERROR + elem

if errors:
    print "\nUnable to install scratch4acmeboards. Please check errors\n"
elif warnings:
    print "\n\033[1mscratch4acmeboards\033[0m installed, but please check warnings.\n"
else:
    print "\n\033[1mscratch4acmeboards\033[0m installed done without errors.\n\033[1mBe Cool !!!\033[0m\n"
