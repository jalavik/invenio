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

from sqlalchemy import *
from invenio.modules.upgrader.api import op


depends_on = []


def info():
    return "Initial creation of tables for pidstore module."


def do_upgrade():
    """Implement your upgrades here."""
    op.create_table(
        'pidSTORE',
        sa.Column('id', mysql.INTEGER(display_width=15), nullable=False),
        sa.Column('pid_type', sa.String(length=6), nullable=False),
        sa.Column('pid_value', sa.String(length=255), nullable=False),
        sa.Column('pid_provider', sa.String(length=255), nullable=False),
        sa.Column('status', sa.CHAR(length=1), nullable=False),
        sa.Column('object_type', sa.String(length=3), nullable=True),
        sa.Column('object_value', sa.String(length=255), nullable=True),
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('last_modified', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_object', 'pidSTORE', ['object_type', 'object_value'], unique=False)
    op.create_index('idx_status', 'pidSTORE', ['status'], unique=False)
    op.create_index('uidx_type_pid', 'pidSTORE', ['pid_type', 'pid_value'], unique=True)

    op.create_table(
        'pidLOG',
        sa.Column('id', mysql.INTEGER(display_width=15), nullable=False),
        sa.Column('id_pid', mysql.INTEGER(display_width=15), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('action', sa.String(length=10), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['id_pid'], ['pidSTORE.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_action', 'pidLOG', ['action'], unique=False)


def estimate():
    """Estimate running time of upgrade in seconds (optional)."""
    return 1


def pre_upgrade():
    """Run pre-upgrade checks (optional)."""
    pass


def post_upgrade():
    """Run post-upgrade checks (optional)."""
    pass
