#!/usr/bin/env python
#encoding:utf-8
#author:dbr/Ben
#project:tvnamer
#repository:http://github.com/dbr/tvnamer
#license:Creative Commons GNU GPL v2
# http://creativecommons.org/licenses/GPL/2.0/

"""Holds Config singleton
"""

import os
import xml
import elementtree.ElementTree as ET

from tvnamer_exceptions import InvalidConfigFile, WrongConfigVersion


def _serialiseElement(root, name, elem, etype='option'):
    """Used for config XML saving, currently supports strings, integers
    and lists contains the any of these
    """
    celem = ET.SubElement(root, etype)
    if name is not None:
        celem.set('name', name)

    if isinstance(elem, bool):
        celem.set('type', 'bool')
        celem.text = str(elem)
        return
    elif isinstance(elem, int):
        celem.set('type', 'int')
        celem.text = str(elem)
        return
    elif isinstance(elem, basestring):
        celem.set('type', 'string')
        celem.text = elem
        return
    elif isinstance(elem, list):
        celem.set('type', 'list')
        for subelem in elem:
            _serialiseElement(celem, None, subelem, 'value')
        return


def _deserialiseItem(ctype, citem):
    """Used for config XML loading, currently supports strings, integers
    and lists contains the any of these
    """
    if ctype == 'int':
        return int(citem.text)
    elif ctype == 'string':
        return citem.text
    elif ctype == 'bool':
        if citem.text == 'True':
            return True
        elif citem.text == 'False':
            return False
        else:
            raise InvalidConfigFile(
                "Boolean value for %s was not 'True' or ', was %r" % (
                    citem.text))
    elif ctype == 'list':
        ret = []
        for subitem in citem:
            ret.append(_deserialiseItem(subitem.attrib['type'], subitem))
        return ret


def _indentTree(elem, level=0):
    """Inline-modification of ElementTree to "pretty-print" the XML
    """
    i = "\n" + "    "*level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            _indentTree(child, level+1)
        lastchild = elem[-1]
        if not lastchild.tail or not lastchild.tail.strip():
            lastchild.tail = i
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


class _ConfigManager(dict):
    """Stores configuration options, deals with optional parsing and saving
    of options to disc.
    """

    VERSION = 1
    DEFAULT_CONFIG_FILE = os.path.expanduser("~/.tvnamer.xml")

    def __init__(self):
        super(_ConfigManager, self).__init__(self)
        if os.path.isfile(self.DEFAULT_CONFIG_FILE):
            self._loadConfig(self.DEFAULT_CONFIG_FILE)
        else:
            self.useDefaultConfig()

    def _setDefaults(self):
        """If no config file is found, these are used. If the config file
        skips any options, the missing settings are set to the defaults.
        """
        defaults = {
            'verbose': False,
            'recursive': False,
            'episode_patterns': [
                # [group] Show - 01-02 [Etc]
                '''^\[.+?\][ ]? # group name
                (?P<showname>.*?)[ ]?[-_][ ]? # show name, padding, spaces?
                (?P<episodenumberstart>\d+)   # first episode number
                ([-_]\d+)*                    # optional repeating episodes
                [-_](?P<episodenumberend>\d+) # last episode number
                [^\/]*$''',

                # [group] Show - 01 [Etc]
                '''^\[.+?\][ ]? # group name
                (?P<showname>.*) # show name
                [ ]?[-_][ ]?(?P<episodenumber>\d+)
                [^\/]*$''',

                # foo.s01e23e24*
                '''
                ^(?P<showname>.+?)[ \._\-]               # show name
                [Ss](?P<seasonnumber>[0-9]+)             # s01
                [\.\- ]?                                 # seperator
                [Ee](?P<episodenumberstart>[0-9]+)       # first e23
                ([\.\- ]?[Ee][0-9]+)*                    # e24e25 etc
                [\.\- ]?[Ee](?P<episodenumberend>[0-9]+) # final episode num
                [^\/]*$''',

                # foo.1x09-11*
                '''^(?P<showname>.+?)[ \._\-]       # show name and padding
                \[                                  # [
                    ?(?P<seasonnumber>[0-9]+)       # season
                x                                   # x
                    (?P<episodenumberstart>[0-9]+)  # episode
                -                                   # -
                    (?P<episodenumberend>[0-9]+)    # episode
                \]                                  # \]
                [^\\/]*$''',

                # foo_[s01]_[e01]
                '''^(?P<showname>.+?)[ \._\-]       # show name and padding
                \[                                  # [
                    [Ss](?P<seasonnumber>[0-9]+?)   # season
                \]                                  # ]
                _                                   # _
                \[                                  # [
                    [Ee](?P<episodenumber>[0-9]+?)  # episode
                \]?                                 # ]
                [^\\/]*$''',

                # foo.1x09*
                '''^(?P<showname>.+?)[ \._\-]       # show name and padding
                \[?                                 # [ optional
                (?P<seasonnumber>[0-9]+)            # season
                x                                   # x
                (?P<episodenumber>[0-9]+)           # episode
                \]?                                 # ] optional
                [^\\/]*$''',

                # foo.s01.e01, foo.s01_e01
                '''^(?P<showname>.+?)[ \._\-]
                [Ss](?P<seasonnumber>[0-9]+)[\.\- ]?
                [Ee](?P<episodenumber>[0-9]+)
                [^\\/]*$''',

                # foo.103*
                '''^(?P<showname>.+)[ \._\-]
                (?P<seasonnumber>[0-9]{1})
                (?P<episodenumber>[0-9]{2})
                [\._ -][^\\/]*$''',

                # foo.0103*
                '''^(?P<showname>.+)[ \._\-]
                (?P<seasonnumber>[0-9]{2})
                (?P<episodenumber>[0-9]{2,3})
                [\._ -][^\\/]*$'''],

            'filename_with_episode':
              '%(showname)s - [%(seasonno)02dx%(episode)s] - %(episodename)s',
            'filename_without_episode':
              '%(showname)s - [%(seasonno)02dx%(episode)s]',
            'episode_single': 'e%02d',
            'episode_seperator': ''}

        # Updates defaults dict with current settings
        for dkey, dvalue in defaults.items():
            self.setdefault(dkey, dvalue)

    def _clearConfig(self):
        """Clears all config options, usually before loading a new config file
        """
        self.clear()

    def _loadConfig(self, xmlsrc):
        """Loads a config from a file
        """
        try:
            root = ET.fromstring(xmlsrc)
        except xml.parsers.expat.ExpatError, errormsg:
            raise InvalidConfigFile(errormsg)

        version = int(root.attrib['version'])
        if version != 1:
            raise WrongConfigVersion(
                'Expected version %d, got version %d' % (
                    self.VERSION, version))

        conf = {}
        for citem in root:
            value = _deserialiseItem(citem.attrib['type'], citem)
            conf[citem.attrib['name']] = value

        return conf

    def _saveConfig(self, configdict):
        """Takes a config dictionary, returns XML as string
        """
        root = ET.Element('tvnamer')
        root.set('version', str(self.VERSION))

        for ckey, cvalue in configdict.items():
            _serialiseElement(root, ckey, cvalue)

        _indentTree(root)
        return ET.tostring(root).strip()

    def loadConfig(self, filename):
        """Use Config.loadFile("something") to load a new config files, clears
        all existing options
        """
        self._clearConfig()
        try:
            xmlsrc = open(filename).read()
        except IOError, errormsg:
            raise InvalidConfigFile(errormsg)
        else:
            loaded_conf = self._loadConfig(xmlsrc)
            self._setDefaults() # Makes sure all config options are set
            self.update(loaded_conf)

    def saveConfig(self, filename):
        """Stores config options into a file
        """
        xmlsrc = self._saveConfig(self)
        try:
            fhandle = open(filename, 'w')
        except IOError, errormsg:
            raise InvalidConfigFile(errormsg)
        else:
            fhandle.write(xmlsrc)
            fhandle.close()

    def useDefaultConfig(self):
        """Uses only the default settings, works similarly to Config.loadFile
        """
        self._clearConfig()
        self._setDefaults()


Config = _ConfigManager()
