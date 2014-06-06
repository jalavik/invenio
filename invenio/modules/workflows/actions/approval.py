# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2012, 2013, 2014 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Generic Approval action."""

from invenio.base.i18n import _
from flask import render_template


class approval(object):
    """Class representing the approval action."""

    name = _("Approve")
    static = ["js/workflows/actions/approval.js"]

    def render_mini(self, obj):
        """Method to render the action."""
        return render_template(
            'workflows/action/approve_mini.html',
            {
                'message': obj.get_message(),
                'object_id': obj.id
            }
        )

    def render(self, obj):
        """Method to render the action."""
        return {
            "main": render_template('workflows/action/approval.html',
                                    {
                                        'message': obj.get_message(),
                                        'object_id': obj.id,
                                    })
        }

    def resolve(self, request):
        """Resolve the action taken in the approval action."""
        from flask import flash
        from ..api import continue_oid_delayed
        from ..models import BibWorkflowObject

        object_id = request.get("object_id", None)

        if object_id:
            bwobject = BibWorkflowObject.query.get(object_id)

            if request.form['decision'] == 'Accept':
                bwobject.remove_action()
                continue_oid_delayed(object_id)
                flash('Record Accepted')

            elif request.form['decision'] == 'Reject':
                BibWorkflowObject.delete(object_id)
                flash('Record Rejected')
