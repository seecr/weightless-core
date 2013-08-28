# -*- coding: utf-8 -*-
## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Seecr Test"
#
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from __future__ import with_statement

from errno import ECHILD
from os.path import isdir, join, abspath, dirname, basename, isfile, realpath
from os import system, listdir, makedirs, waitpid, kill, WNOHANG, getenv
from sys import stdout, path as systemPath
from random import randint, choice
from time import sleep
from StringIO import StringIO
from subprocess import Popen
from signal import SIGTERM
from urllib import urlopen, urlencode
from lxml.etree import XMLSyntaxError, parse
from string import ascii_letters
from time import time

from seecrtestcase import SeecrTestCase

randomString = lambda n=4: ''.join(choice(ascii_letters) for i in xrange(n))

class IntegrationTestCase(SeecrTestCase):
    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self.state, name)

    def run(self, result=None, state=None):
        self.state = state
        SeecrTestCase.run(self, result=result)

INTEGRATION_TEMPDIR_BASE = getenv('INTEGRATION_TEMPDIR_BASE', '/tmp/integrationtest')
REMOTE_USERNAME = getenv('REMOTE_USERNAME', '')

class IntegrationState(object):
    def __init__(self, stateName, tests=None, fastMode=False):
        self.stateName = stateName
        self.__tests = tests
        self.fastMode = fastMode
        self.pids = {}
        self.integrationTempdir = '%s-%s' % (INTEGRATION_TEMPDIR_BASE, stateName)
        if REMOTE_USERNAME:
            self.integrationTempdir += '-%s' % REMOTE_USERNAME
        if not self.fastMode:
            system('rm -rf ' + self.integrationTempdir)
            system('mkdir --parents '+ self.integrationTempdir)

    def addToTestRunner(self, testRunner):
        testRunner.addGroup(
            self.stateName,
            self.__tests,
            state=self)

    def binDir(self):
        raise NotImplementedError()

    def binPath(self, executable, binDirs=None):
        return SeecrTestCase.binPath(executable, binDirs=[self.binDir()] + (binDirs or []))

    def _startServer(self, serviceName, executable, serviceReadyUrl, cwd=None, redirect=True, flagOptions=None, env=None, **kwargs):
        stdoutfile = join(self.integrationTempdir, "stdouterr-%s.log" % serviceName)
        stdouterrlog = open(stdoutfile, 'w')
        args = executable if isinstance(executable, list) else [executable]
        executable = args[0]
        fileno = stdouterrlog.fileno() if redirect else None
        flagOptions = flagOptions if flagOptions else []
        for flag in flagOptions:
            args.append("--%s" % flag)
        for k,v in kwargs.items():
            args.append("--%s=%s" % (k, str(v)))
        serverProcess = Popen(
            executable=executable,
            args=args,
            cwd=cwd if cwd else getenv('SEECRTEST_USR_BIN', self.binDir()),
            stdout=fileno,
            stderr=fileno,
            env=env,
        )
        self.pids[serviceName] = serverProcess.pid

        self._stdoutWrite("Starting service '%s', for state '%s' : v" % (serviceName, self.stateName))
        done = False
        while not done:
            try:
                self._stdoutWrite('r')
                sleep(0.1)
                serviceReadyResponse = urlopen(serviceReadyUrl).read()
                done = True
            except IOError:
                if serverProcess.poll() != None:
                    del self.pids[serviceName]
                    exit('Service "%s" died, check "%s"' % (serviceName, stdoutfile))
        self._stdoutWrite('oom!\n')

    def _stopServer(self, serviceName, waitInSeconds=20.0):
        kill(self.pids[serviceName], SIGTERM)

        for i in xrange(int(waitInSeconds * 200)):
            try:
                result = waitpid(self.pids[serviceName], WNOHANG)
                if result != (0, 0):
                    break
                sleep(0.005)
            except OSError, e:
                if e.errno == ECHILD:  # ECHILD / 10 --> No child processes, means we're done.
                    break
                raise
        else:
            self._stdoutWrite("Server with servicename '%s' and pid '%s' did not stop within %s seconds - giving up.\n" % (serviceName, self.pids[serviceName], waitInSeconds))

        del self.pids[serviceName]

    def _runExecutable(self, executable, processName=None, cwd=None, redirect=True, flagOptions=None, timeoutInSeconds=15, expectedReturnCode=0, env=None, **kwargs):
        processName = randomString() if processName is None else processName
        args = executable if isinstance(executable, list) else [executable]
        executable = args[0]
        stdoutfile = join(self.integrationTempdir, "stdouterr-%s-%s.log" % (basename(executable), processName))
        stdouterrlog = open(stdoutfile, 'w')
        fileno = stdouterrlog.fileno() if redirect else None
        flagOptions = flagOptions if flagOptions else []
        for flag in flagOptions:
            args.append("--%s" % flag)
        for k,v in kwargs.items():
            args.append("--%s=%s" % (k, str(v)))
        process = Popen(
            executable=executable,
            args=args,
            cwd=cwd if cwd else getenv('SEECRTEST_USR_BIN', self.binDir()),
            stdout=fileno,
            stderr=fileno,
            env=env,
        )

        self._stdoutWrite("Running '%s', for state '%s' : v" % (basename(executable), self.stateName))
        result = 0
        t0 = time()
        keepRunning = True
        while keepRunning:
            self._stdoutWrite('r')
            sleep(0.1)
            result = process.poll()
            keepRunning = result is None
            if time() - t0 > timeoutInSeconds:
                process.terminate()
                exit('Executable "%s" took more than %s seconds, check "%s"' % (basename(executable), timeoutInSeconds, stdoutfile))

        if expectedReturnCode is not None and result != expectedReturnCode:
            exit('Executable "%s" exited with returncode %s, check "%s"' % (basename(executable), result, stdoutfile))
        self._stdoutWrite('oom!\n')
        process.wait()
        stdouterrlog.close()
        if redirect:
            return open(stdoutfile).read()


    def tearDown(self):
        for serviceName in self.pids.keys():
            self._stdoutWrite("Stopping service '%s' for state '%s'\n" % (serviceName, self.stateName))
            self._stopServer(serviceName)

    @staticmethod
    def _stdoutWrite(aString):
        stdout.write(aString)
        stdout.flush()

