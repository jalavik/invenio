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
    invenio.modules.workflows.user_settings
    ---------------------------------------

    Represents the widget on the user dashboard with overview
    over any actions assigned to user.

    WORK IN PROGRESS
"""

from flask import url_for
from flask.ext.login import current_user

from invenio.base.i18n import _
from invenio.ext.template import render_template_to_string
from invenio.modules.dashboard.settings import Settings, UserSettingsStorage

from .models import BibWorkflowObject, ObjectVersion


class WorkflowsSettings(Settings):

    storage_builder = UserSettingsStorage

    def __init__(self):
        super(self.__class__, self).__init__()
        self.icon = 'list-alt'
        self.title = _('Assigned actions')
        self.view = url_for('holdingpen.index')

    def widget(self):
        # TODO filter on user id/grpup
        halted_objects = BibWorkflowObject.query.filter(
            BibWorkflowObject.version == ObjectVersion.HALTED
        )

        template = """
{{  _("You have %(x_num_pending)d pending actions.",
      x_num_pending=pending) }}
"""
        return render_template_to_string(template,
                                         _from_string=True,
                                         pending=halted_objects.count())

    widget.size = 4

    @property
    def is_authorized(self):
        return current_user.is_authenticated()

## Compulsory plug-in interface
settings = WorkflowsSettings
