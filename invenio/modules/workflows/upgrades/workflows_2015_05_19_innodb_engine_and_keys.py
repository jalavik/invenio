# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from invenio.modules.upgrader.api import op


depends_on = [u'workflows_2014_08_12_initial']


def info():
    return "Upgrades workflows tables to InnoDB and adds some indexes"


def do_upgrade():
    """Implement your upgrades here."""
    with op.batch_alter_table("bwlOBJECT", recreate="always", table_kwargs={"mysql_engine": 'InnoDB'}) as batch_op:
        batch_op.create_index('ix_bwlOBJECT_version', ['version'])
        batch_op.create_index('ix_bwlOBJECT_data_type', ['data_type'])
        pass

    with op.batch_alter_table("bwlWORKFLOW", recreate="always", table_kwargs={"mysql_engine": 'InnoDB'}) as batch_op:
        pass

    with op.batch_alter_table("bwlWORKFLOWLOGGING", recreate="always", table_kwargs={"mysql_engine": 'InnoDB'}) as batch_op:
        pass

    with op.batch_alter_table("bwlOBJECTLOGGING", recreate="always", table_kwargs={"mysql_engine": 'InnoDB'}) as batch_op:
        pass

def estimate():
    """Estimate running time of upgrade in seconds (optional)."""
    return 1


def pre_upgrade():
    """Run pre-upgrade checks (optional)."""
    # Example of raising errors:
    # raise RuntimeError("Description of error 1", "Description of error 2")


def post_upgrade():
    """Run post-upgrade checks (optional)."""
    # Example of issuing warnings:
    # warnings.warn("A continuable error occurred")
