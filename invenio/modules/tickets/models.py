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

"""
The tickets module allows to connect to external ticketing/issue tracking.
"""

from invenio.ext.sqlalchemy import db


class Ticket(db.Model):

    """Represent a Ticket record."""

    __tablename__ = 'tickets'

    id = db.Column(
        db.Integer(15, unsigned=True),
        nullable=False,
        primary_key=True,
        autoincrement=True)

    id_external = db.Column(
        db.String(36),
        nullable=False)

    id_model = db.Column(
        db.String(36),
        nullable=True)

    json = db.Column(db.JSON, nullable=True)

    type = db.Column(db.Char(100), nullable=True)
