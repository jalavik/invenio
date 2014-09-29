# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2014 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Define system class and registry."""

import six

from werkzeug.local import LocalProxy


class SystemsRegistry(type):

    """Systems registry."""

    __systems_registry__ = []

    def __init__(cls, name, bases, dct):
        """Register cls to actions registry."""
        if not dct.get('__prototype__', False):
            cls.__systems_registry__.append(cls)
        super(SystemsRegistry, cls).__init__(name, bases, dct)

    @property
    def name(cls):
        """Return lowercased system class name."""
        return cls.__name__.lower()

    @property
    def description(cls):
        """Return stripped class documentation string."""
        return cls.__doc__.strip()

systems = LocalProxy(lambda: SystemsRegistry.__systems_registry__)
"""List of registered actions."""


@six.add_metaclass(SystemsRegistry)
class System(object):

    """Default system description."""

    __prototype__ = True  # do not register this class

    attributes = []
