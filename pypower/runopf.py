# Copyright (C) 1996-2011 Power System Engineering Research Center (PSERC)
# Copyright (C) 2011 Richard Lincoln
#
# PYPOWER is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# PYPOWER is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PYPOWER. If not, see <http://www.gnu.org/licenses/>.

"""Runs an optimal power flow.
"""

from sys import stdout, stderr

from os.path import dirname, join

from pypower.ppoption import ppoption
from pypower.opf import opf
from pypower.printpf import printpf
from pypower.savecase import savecase


def runopf(casedata=None, ppopt=None, fname='', solvedcase=''):
    """Runs an optimal power flow.

    @see: L{rundcopf}, L{runuopf}

    @author: Ray Zimmerman (PSERC Cornell)
    @author: Richard Lincoln
    """
    ## default arguments
    if casedata is None:
        casedata = join(dirname(__file__), 'case9')
    ppopt = ppoption(ppopt)

    ##-----  run the optimal power flow  -----
    r = opf(casedata, ppopt)

    ##-----  output results  -----
    if fname:
        fd = None
        try:
            fd = open(fname, "a")
        except IOError as detail:
            stderr.write("Error opening %s: %s.\n" % (fname, detail))
        finally:
            if fd is not None:
                printpf(r, fd, ppopt)
                fd.close()

    else:
        printpf(r, stdout, ppopt)

    ## save solved case
    if solvedcase:
        savecase(solvedcase, r)

    return r


if __name__ == '__main__':
    ppopt = ppoption(OPF_ALG=580)
    runopf(None, ppopt)
