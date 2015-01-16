# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2012, 2013, 2014, 2015 CERN.
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

"""The workflow engine extension of GenericWorkflowEngine."""

from __future__ import absolute_import

from invenio.ext.sqlalchemy import db
from workflow.engine_db import DbWorkflowEngine
from workflow.errors import WorkflowDefinitionError


class BibWorkflowEngine(DbWorkflowEngine):

    def __init__(self, *args, **kwargs):
        super(BibWorkflowEngine, self).__init__(*args, **kwargs)
        self.set_workflow_by_name(self.db_obj.name)

    @property
    def db(self):
        return db

    def set_workflow_by_name(self, workflow_name):
        """Configure the workflow to run by the name of this one.

        Allows the modification of the workflow that the engine will run
        by looking in the registry the name passed in parameter.

        :param workflow_name: name of the workflow.
        :type workflow_name: str
        """
        from .registry import workflows
        if workflow_name not in workflows:
            # No workflow with that name exists
            raise WorkflowDefinitionError("Workflow '%s' does not exist"
                                          % (workflow_name,),
                                          workflow_name=workflow_name)
        self.workflow_definition = workflows[workflow_name]
        self.setWorkflow(self.workflow_definition.workflow)

    # FIXME: Unused. If removed, `self.workflow_definition` is also unused.
    def get_default_data_type(self):
        """Return default data type from workflow definition."""
        return getattr(self.workflow_definition,
                       "object_type",
                       "")
