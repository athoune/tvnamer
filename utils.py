#!/usr/bin/env python
#encoding:utf-8
#author:dbr/Ben
#project:tvnamer
#repository:http://github.com/dbr/tvnamer
#license:Creative Commons GNU GPL v2
# http://creativecommons.org/licenses/GPL/2.0/

"""Utilities for tvnamer, including filename parsing
"""

import os
import re
import sys

import tvdb_api

from config import Config
from tvnamer_exceptions import (InvalidPath, InvalidFilename)


def warn(text):
    """Displays message to sys.stdout
    """
    sys.stderr.write("%s\n" % text)


def verbose(text):
    """Prints message if verbose option is specified
    """
    if Config['verbose']:
        print text


class FileFinder(object):
    """Given a file, it will verify it exists, given a folder it will descend
    one level into it and return a list of files, unless the recursive argument
    is True, in which case it finds all files contained within the path.
    """

    def __init__(self, path, recursive = False):
        self.path = path
        self.recursive = recursive

    def findFiles(self):
        """Returns list of files found at path
        """
        if os.path.isfile(self.path):
            return [os.path.abspath(self.path)]
        elif os.path.isdir(self.path):
            return self._findFilesInPath(self.path)
        else:
            raise InvalidPath("%s is not a valid file/directory" % self.path)

    def _findFilesInPath(self, startpath):
        """Finds files from startpath, could be called recursively
        """
        allfiles = []
        if os.path.isfile(startpath):
            allfiles.append(os.path.abspath(startpath))

        elif os.path.isdir(startpath):
            for subf in os.listdir(startpath):
                newpath = os.path.join(startpath, subf)
                newpath = os.path.abspath(newpath)
                if os.path.isfile(newpath):
                    allfiles.append(newpath)
                else:
                    if self.recursive:
                        allfiles.extend(self._findFilesInPath(newpath))
                    #end if recursive
                #end if isfile
            #end for sf
        #end if isdir
        return allfiles


class FileParser(object):
    """Deals with parsing of filenames
    """

    def __init__(self, path):
        self.path = path
        self.compiled_regexs = []
        self._compileRegexs()

    def _compileRegexs(self):
        """Takes episode_patterns from config, compiles them all
        into self.compiled_regexs
        """
        for cpattern in Config['episode_patterns']:
            try:
                cregex = re.compile(cpattern, re.VERBOSE)
            except re.error, errormsg:
                warn("WARNING: Invalid episode_pattern, %s. %s" % (
                    errormsg, cregex.pattern))
            else:
                self.compiled_regexs.append(cregex)

    def parse(self):
        _, filename = os.path.split(self.path)

        for cmatcher in self.compiled_regexs:
            match = cmatcher.match(filename)
            if match:
                namedgroups = match.groupdict().keys()

                if 'episodenumber1' in namedgroups:
                    # Multiple episodes, have episodenumber1 or 2 etc
                    epnos = []
                    for cur in namedgroups:
                        epnomatch = re.match('episodenumber(\d+)', cur)
                        if epnomatch:
                            epnos.append(int(match.group(cur)))
                    epnos.sort()
                    episodenumber = epnos

                elif 'episodenumberstart' in namedgroups:
                    # Multiple episodes, regex specifies start and end number
                    start = int(match.group('episodenumberstart'))
                    end = int(match.group('episodenumberend'))
                    episodenumber = range(start, end + 1)

                else:
                    episodenumber = int(match.group('episodenumber'))

                if 'seasonnumber' in namedgroups:
                    seasonnumber = int(match.group('seasonnumber'))
                else:
                    # No season number specified, usually for Anime
                    seasonnumber = None

                episode = EpisodeInfo(
                    showname = match.group('showname'),
                    seasonnumber = seasonnumber,
                    episodenumber = episodenumber,
                    filename = self.path)
                return episode
        else:
            raise InvalidFilename(self.path)


class EpisodeInfo(object):
    """Stores information (season, episode number, episode name), and contains
    logic to generate new name
    """

    def __init__(self,
        showname = None,
        seasonnumber = None,
        episodenumber = None,
        episodename = None,
        filename = None):

        self.showname = showname
        self.seasonnumber = seasonnumber
        self.episodenumber = episodenumber
        self.episodename = episodename
        self.filename = filename

    def generateFilename(self):
        """
        Uses the following config options:
        filename_with_episode # Filename when episode name is found
        filename_without_episode # Filename when no episode can be found
        episode_single # formatting for a single episode number
        episode_seperator # used to join multiple episode numbers
        """
        # Format episode number into string, or a list
        if isinstance(self.episodenumber, list):
            epno = Config['episode_seperator'].join(
                Config['episode_single'] % x for x in self.episodenumber)
        else:
            epno = Config['episode_single'] % self.episodenumber

        epdata = {
            'showname': self.showname,
            'seasonno': self.seasonnumber,
            'episode': epno,
            'episodename': self.episodename}

        if self.episodename is None:
            return Config['filename_with_episode'] % epdata
        else:
            return Config['filename_without_episode'] % epdata

    def __repr__(self):
        return "<%s: %s>" % (
            self.__class__.__name__,
            self.generateFilename())


class Renamer(object):
    """Deals with renaming of files
    """

    def __init__(self, filename):
        self.filename = filename

    def newPath(self, newPath):
        """Moves a file
        """
        #FIXME: Need to impliment this
        raise NotImplementedError()

    def newName(self, newName, keepExtension=True):
        """Renames a file, keeping the path the same.

        If keepExtension is True (default), the existing extension (if any) is
        retained. If False, the existing extension is removed, and the one in
        newName is used if it is supplied.

        If keepExtension is False, the extension in newName will be used
        """
        filepath, filename = os.path.split(self.filename)
        filename, fileext = os.path.splitext(filename)

        if keepExtension:
            newName = newName + fileext

        newpath = os.path.join(filepath, newName)
        os.rename(self.filename, newpath)
        self.filename = newpath
