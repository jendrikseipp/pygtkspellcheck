# -*- coding:utf-8 -*-
#
# Copyright (C) 2012, Carlos Jenkins <carlos@jenkins.co.cr>
# Copyright (C) 2012, Maximilian Köhl <linuxmaxi@googlemail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module extracts the .dic and .aff (Hunspell) dictionaries from any given 
.oxt extension.

Extensions could be found at:

    http://extensions.services.openoffice.org/dictionary
"""

import functools
import logging
import os
import shutil
import xml.dom.minidom
import zipfile

# public objects
__all__ = ['extract_oxt', 'batch_extract', 'BatchError', 'BATCH_SUCCESS',
           'BATCH_ERROR']

# logger
logger = logging.getLogger(__name__)

def find_dictionaries(registry):
    def oor_name(name, element):
        return element.attributes['oor:name'].value.lower() == name
    
    def get_property(name, properties):
        property = list(filter(functools.partial(oor_name, name),
                               properties))
        if property:
            return property[0].getElementsByTagName('value')[0]
    
    result = []
    
    for dictionaries in filter(functools.partial(oor_name, 'dictionaries'),
                               registry.getElementsByTagName('node')):
        for dictionary in dictionaries.getElementsByTagName('node'):
            properties = dictionary.getElementsByTagName('prop')
            format = get_property('format', properties).firstChild.data.strip()
            if format and format == 'DICT_SPELL':
                locations = get_property('locations', properties)
                if locations.firstChild.nodeType == xml.dom.Node.TEXT_NODE:
                    locations = locations.firstChild.data
                    locations = locations.replace('%origin%/', '').strip()
                    result.append(locations.split())
                else:
                    locations = [item.firshChild.data.replace('%origin%/', '') \
                                 .strip() for item in
                                 locations.getElementsByTagName('it')]
                    result.append(locations)
    
    return result

def extract(filename, target, override=False):
    """
    Extract Hunspell dictionaries out of LibreOffice ``.oxt`` extensions.

    :param filename: path to the ``.oxt`` extension
    :param target: path to extract Hunspell dictionaries to
    :param override: override existing files in the target directory
    :rtype: list of the extracted dictionaries

    This function extracts the Hunspell dictionaries (``.dic`` and ``.aff``
    files) from the given ``.oxt`` extension found to ``target``.

    Extensions could be found at:

        http://extensions.services.openoffice.org/dictionary
    """
    with zipfile.ZipFile(filename, 'r') as extension:
        files = extension.namelist()
        
        registry = 'dictionaries.xcu'
        if not registry in files:
            for filename in files:
                if filename.lower().endswith(registry):
                    registry = filename
                
        if registry in files:
            registry = xml.dom.minidom.parse(extension.open(registry))
            dictionaries = find_dictionaries(registry)
            extracted = []
            for dictionary in dictionaries:
                for filename in dictionary:
                    dict_file = os.path.join(target, os.path.basename(filename))
                    if (not os.path.exists(dict_file) 
                            or (override and os.path.isfile(dict_file))):
                        with open(dict_file, 'wb') as _target:
                            with extension.open(filename, 'r') as _source:
                                extracted.append(os.path.basename(filename))
                                _target.write(_source.read())
                    else:
                        logging.warning(('dictionary file "{}" already exists '
                                         'and not overriding it'
                                         ).format(dict_file))
            return extracted

class BatchError(Exception):
    """
    An fatal error happened during Batch Processing.
    """

BATCH_SUCCESS = 'success'
BATCH_ERROR = 'error'

def batch_extract(oxt_path, extract_path, override=False, move_path=None):
    """
    Uncompress, read and install LibreOffice ``.oxt`` dictionaries extensions.
    
    :param oxt_path: path to a directory containing the ``.oxt`` extensions
    :param extract_path: path to extract Hunspell dictionaries files to
    :param override: override already existing files
    :param move_path: optional path to move the ``.oxt`` files after processing
    :rtype: generator over all extensions, yielding result, extension name and
        error - result would be :const:`BATCH_SUCCESS` for success and
        :const:`BATCH_ERROR` if some error happened
    
    This function extracts the Hunspell dictionaries (``.dic`` and ``.aff``
    files) from all the ``.oxt`` extensions found on ``oxt_path`` directory to
    the ``extract_path`` directory.
    
    Extensions could be found at:
    
        http://extensions.services.openoffice.org/dictionary
    
    In detail, this functions does the following:
    
    1. find all the ``.oxt`` extension files within ``oxt_path``
    2. open (unzip) each extension
    3. find the dictionary definition file within (*dictionaries.xcu*)
    4. parse the dictionary definition file and locate the dictionaries files
    5. uncompress those files to ``extract_path``
    
    
    By default file overriding is disabled, set ``override`` parameter to True
    if you want to enable it. As additional option, each processed extension can
    be moved to ``move_path``.
    
    Example::
    
        for result, name, error in oxt_extract.batch_extract(...):
            if result == oxt_extract.BATCH_SUCCESS:
                print('successfully extracted extension "{}"'.format(name))
            else:
                print('could not extract extension "{}"'.format(name))
                print('error {}'.format(error))
        
    """

    # get the real, absolute and normalized path
    oxt_path = os.path.normpath(os.path.abspath(os.path.realpath(oxt_path)))
    
    # check that the input directory exists
    if not os.path.isdir(oxt_path):
        return
        
    # create extract directory if not exists
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)

    # check that the extract path is a directory
    if not os.path.isdir(extract_path):
        raise BatchError('extract path is not a directory')
    
    # get all .oxt extension at given path
    oxt_files = [extension for extension in os.listdir(oxt_path)
                 if extension.lower().endswith('.oxt')]
    
    for extension_name in oxt_files:
        extension_path = os.path.join(oxt_path, extension_name)
        
        try:
            extract(extension_path, extract_path, override)
            yield BATCH_SUCCESS, extension_name, None
        except zipfile.BadZipFile as error:
            yield BATCH_ERROR, extension_name, error        
        
        # move the extension after processing if user requires it
        if move_path is not None:
            # create move path if it doesn't exists
            if not os.path.exists(move_path):
                os.makedirs(move_path)
            # move to the given path only if it is a directory and target
            # doesn't exists
            if os.path.isdir(move_path):
                if (not os.path.exists(os.path.join(move_path, extension_name))
                        or override):
                    shutil.move(extension_path, move_path)
                else:
                    logger.warning(('unable to move extension, file with same '
                                    'name exists within move_path'))
            else:
                logger.warning(('unable to move extension, move_path is not a '
                                'directory'))