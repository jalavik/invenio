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

from six import iteritems
from uuid import uuid1 as new_uuid

from workflow.engine_db import DbWorkflowEngine, ObjectVersion
from workflow.errors import WorkflowDefinitionError
from workflow.logger import DbWorkflowLogHandler, get_logger

from invenio.ext.sqlalchemy import db

from .models import (
    Workflow,
    DbWorkflowObject,
    DbWorkflowEngineLog
)

from six.moves import cPickle
from .utils import dictproperty
import base64

class BibWorkflowEngine(DbWorkflowEngine):

    """Special engine for Invenio.

    The reason why base64 is used throughout this class is due to a bug in
    CPython pickle streams which sometimes contain non-ASCII characters. Because
    of this it is impossible to correctly use json on such data without base64
    encoding it first.
    """

    def __init__(self, db_obj, **kwargs):
        """Special handling of instantiation of engine."""
        super(BibWorkflowEngine, self).__init__(db_obj)
        self.set_extra_data_params(**kwargs)
        self.set_workflow_by_name(self.db_obj.name)

    @classmethod
    def with_name(cls, name, id_user=0, module_name="Unknown", **kwargs):
        """ Instantiate a DbWorkflowEngine given a name or UUID.

        :param name: name of workflow to run.
        :type name: str

        :param id_user: id of user to associate with workflow
        :type id_user: int

        :param module_name: label used to query groups of workflows.
        :type module_name: str
        """
        db_obj = Workflow(
            name=name,
            id_user=id_user,
            module_name=module_name,
            uuid=new_uuid()
        )
        return cls(db_obj, **kwargs)

    @classmethod
    def from_uuid(cls, uuid, **kwargs):
        """ Load a workflow from the database given a UUID.

        :param uuid: pass a uuid to an existing workflow.
        :type uuid: str
        """
        db_obj = Workflow.get(Workflow.uuid == uuid).first()
        if db_obj is None:
            raise LookupError("No workflow with UUID {} was found".format(uuid))
        return cls(db_obj, **kwargs)

    @property
    def db(self):
        """Return db object."""
        return db

    def get_extra_data(self):
        """Main method to retrieve data saved to the object."""
        return cPickle.loads(base64.b64decode(self.db_obj._extra_data))

    def set_extra_data(self, value):
        """Main method to update data saved to the object."""
        self.db_obj._extra_data = base64.b64encode(cPickle.dumps(value))

    def reset_extra_data(self):
        """Reset extra data to defaults."""
        from .models import get_default_extra_data
        self.db_obj._extra_data = get_default_extra_data()

    def extra_data_get(self, key):
        """Get a key value in extra data."""
        if key not in self.db_obj.get_extra_data():
            raise KeyError("%s not in extra_data" % (key,))
        return self.db_obj.get_extra_data()[key]

    def extra_data_set(self, key, value):
        """Add a key value pair in extra_data."""
        tmp = self.db_obj.get_extra_data()
        tmp[key] = value
        self.db_obj.set_extra_data(tmp)

    extra_data = dictproperty(fget=extra_data_get, fset=extra_data_set,
                              doc="Sets up property")

    del extra_data_get, extra_data_set

    def set_extra_data_params(self, **kwargs):
        """Add keys/value in extra_data.

        Allows the addition of value in the extra_data dictionary,
        all the data must be passed as "key=value".
        """
        tmp = self.get_extra_data()
        if not tmp:
            tmp = {}
        for key, value in iteritems(kwargs):
            tmp[key] = value
        self.set_extra_data(tmp)

# def _save_extra_data(obj):
#     extra_data = obj.get_extra_data()
#     obj.set_extra_data(extra_data)

    def execute_callback(self, callback, obj):
        """Execute the callback (workflow tasks)."""
        # What is this I don't even.
        obj.data = obj.get_data()
        obj.extra_data = obj.get_extra_data()
        self.extra_data = self.get_extra_data()
        self.log.debug("Executing callback %s" % (repr(callback),))
        try:
            callback(obj, self)
        finally:
            self.set_extra_data(self.extra_data)
            obj.set_data(obj.data)
            obj.extra_data["_task_counter"] = self._i[1]
            obj.extra_data["_last_task_name"] = callback.func_name
            obj.update_task_history(callback)
            obj.set_extra_data(obj.extra_data)

    def init_logger(self):
        """Return the appropriate logger instance."""
        db_handler_obj = DbWorkflowLogHandler(DbWorkflowEngineLog, "uuid")
        return get_logger(logger_name="workflow.%s" % self.db_obj.uuid,
                              db_handler_obj=db_handler_obj,
                              obj=self)

    def has_completed(self):
        """Return True if workflow is fully completed."""
        res = self.db.session.query(self.db.func.count(DbWorkflowObject.id)).\
            filter(DbWorkflowObject.id_workflow == self.uuid).\
            filter(DbWorkflowObject.version.in_(
                [ObjectVersion.INITIAL,
                 ObjectVersion.COMPLETED]
            )).group_by(DbWorkflowObject.version).all()
        return len(res) == 2 and res[0] == res[1]

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
