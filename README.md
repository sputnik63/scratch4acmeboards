# scratch4acmeboards
python program to use Scratch software by MIT with Acmesystems s.r.l. boards


**scratch4acmeboards** allows Scratch 1.4 by MIT to manage the GPIO pins of Arietta, a Linux embedded module by Acmesystems s.r.l based on an Atmel mcrocontroller.
The pins are managed both in OUTPUT and in INPUT mode. For now, only the board Arietta G25 is tested but I'm confident it could work also on other boards.

# Getting started

Connect Arietta to your PC through USB port or wifi module
If needed update [ablib](https://github.com/tanzilli/ablib) from github
Install the [scratchpy client](https://github.com/pilliq/scratchpy)
Download scratch4acmeboards files and put them on Arietta. Then, as root, run the command

```
# python ./scratch4acmeboards_handler.py
```
On your PC, start Scratch 1.4: it must have Mesh enabled. To enable Mesh on Scratch 1.4 please follow the [instructions here] (http://wiki.scratch.mit.edu/wiki/Mesh#Mesh_by_Modification_of_Scratch)
If you are using the wifi module then you must use the -m option to pass the IP address of your PC
```
# python ./scratch4acmeboards_handler.py -m ipaddress_of_pc_running_scratch
```

# Usage
```
# python ./scratch4acmeboards_handler.py -h

Options:
  -h, --help            show this help message and exit
  -o, --offline         option to use for local tests without Arietta board
  -m IPADDRESS, --mesh=IPADDRESS
                        ip address where mesh (Scratch) is running. Default
                        192.168.10.20
  -d, --debug           Set logging level to DEBUG. Default is WARNING
  -p, --printtostdout   Print all log messages to stdout. Default logs to
                        /tmp/scratch4acmeboards.log
  -b BOARDNAME, --boardname=BOARDNAME
                        ACMESystems board name among Arietta_G25 (default),
                        Daisy, Acqua_A5, FOX_Board_G20, Aria_G25
```
Complete tutorials in italian and english languages are [available here] (http://www.coderdojomolfetta.it/scratch-per-arietta-g25/).
