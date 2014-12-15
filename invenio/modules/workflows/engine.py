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

import sys

import base64
import traceback
from six import iteritems, reraise
from six.moves import cPickle
from uuid import uuid1 as new_uuid
from workflow.engine import GenericWorkflowEngine, TransitionActions, ProcessingFactory, Break, Continue

from .errors import (
    AbortProcessing,
    SkipToken,
    WorkflowDefinitionError,
    WorkflowError as WorkflowErrorClient,
    WorkflowHalt,
    HaltProcessing,
)
from .logger import BibWorkflowLogHandler, get_logger
from .models import (
    BibWorkflowEngineLog,
    BibWorkflowObject,
    ObjectVersion,
    Workflow,
)
from .signals import (workflow_finished,
                      workflow_halted,
                      workflow_started)
from .utils import dictproperty
from invenio.ext.sqlalchemy import db


class WorkflowStatus(object):

    """The different possible value for Workflow Status."""

    NEW, RUNNING, HALTED, ERROR, COMPLETED = range(5)


class BibWorkflowEngine(GenericWorkflowEngine):

    """GenericWorkflowEngine with DB persistence for py:mod:`invenio.workflows`.

    Adds a SQLAlchemy database model to save workflow states and
    workflow data.

    Overrides key functions in GenericWorkflowEngine to implement
    logging and certain workarounds for storing data before/after
    task calls (This part will be revisited in the future).
    """

    def __init__(self, name=None, uuid=None, curr_obj=0,
                 workflow_object=None, id_user=0,
                 module_name="Unknown", **kwargs):
        """Instantiate a new BibWorkflowEngine object.

        This object is needed to run a workflow and control the workflow,
        like at which step of the workflow execution is currently at, as well
        as control object manipulation inside the workflow.

        You can pass several parameters to personalize your engine,
        but most of the time you will not need to create this object yourself
        as the :py:mod:`.api` is there to do it for you.

        :param name: name of workflow to run.
        :type name: str

        :param uuid: pass a uuid to an existing workflow.
        :type uuid: str

        :param curr_obj: internal id of current object being processed.
        :type curr_obj: int

        :param workflow_object: existing instance of a Workflow object.
        :type workflow_object: Workflow

        :param id_user: id of user to associate with workflow
        :type id_user: int

        :param module_name: label used to query groups of workflows.
        :type module_name: str
        """
        super(BibWorkflowEngine, self).__init__()

        self.db_obj = None
        if isinstance(workflow_object, Workflow):
            self.db_obj = workflow_object
        else:
            # If uuid is defined we try to get the db object from DB.
            if uuid is not None:
                self.db_obj = \
                    Workflow.get(Workflow.uuid == uuid).first()
            else:
                uuid = new_uuid()
            if self.db_obj is None:
                self.db_obj = Workflow(name=name, id_user=id_user,
                                       current_object=curr_obj,
                                       module_name=module_name, uuid=uuid)
                self.save(status=WorkflowStatus.NEW)

        if self.db_obj.uuid not in self.log.name:
            db_handler_obj = BibWorkflowLogHandler(BibWorkflowEngineLog,
                                                   "uuid")
            self.log = get_logger(logger_name="workflow.%s" % self.db_obj.uuid,
                                  db_handler_obj=db_handler_obj,
                                  obj=self)

        self.set_workflow_by_name(self.db_obj.name)
        self.set_extra_data_params(**kwargs)

    @property
    def processing_factory(self):
        """Provide a proccessing factory."""
        return InvProcessingFactory

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

    @property
    def counter_object(self):
        """Return the number of object."""
        return self.db_obj.counter_object

    @property
    def uuid(self):
        """Return the uuid."""
        return self.db_obj.uuid

    @property
    def id_user(self):
        """Return the user id."""
        return self.db_obj.id_user

    @property
    def module_name(self):
        """Return the module name."""
        return self.db_obj.module_name

    @property
    def name(self):
        """Return the name."""
        return self.db_obj.name

    @property
    def status(self):
        """Return the status."""
        return self.db_obj.status

    @property
    def objects(self):
        """Return the objects associated with this workflow."""
        return self.db_obj.objects

    def objects_of_statuses(self, statuses):
        """Get objects having given statuses."""
        results = []
        for obj in self.db_obj.objects:
            if obj.version in statuses:
                results.append(obj)
        return results

    @property
    def completed_objects(self):
        """Return completed objects."""
        return self.objects_of_statuses([ObjectVersion.COMPLETED])

    @property
    def halted_objects(self):
        """Return halted objects."""
        return self.objects_of_statuses([ObjectVersion.HALTED])

    @property
    def running_objects(self):
        """Return running objects."""
        return self.objects_of_statuses([ObjectVersion.RUNNING])

    @property
    def initial_objects(self):
        """Return initial objects."""
        return self.objects_of_statuses([ObjectVersion.INITIAL])

    @property
    def waiting_objects(self):
        """Return waiting objects."""
        return self.objects_of_statuses([ObjectVersion.WAITING])

    @property
    def error_objects(self):
        """Return error objects."""
        return self.objects_of_statuses([ObjectVersion.ERROR])

    def __getstate__(self):
        """Pickling needed functions."""
        if not self._picklable_safe:
            raise cPickle.PickleError("The instance of the workflow engine "
                                      "cannot be serialized, "
                                      "because it was constructed with "
                                      "custom, user-supplied callbacks. "
                                      "Either use PickableWorkflowEngine or "
                                      "provide your own __getstate__ method.")
        state = self.__dict__.copy()
        del state['log']
        return state

    def __setstate__(self, state):
        """Unpickling needed functions."""
        if len(self._objects) < self._i[0]:
            raise cPickle.PickleError("The workflow instance "
                                      "inconsistent state, "
                                      "too few objects")

        db_handler_obj = BibWorkflowLogHandler(BibWorkflowEngineLog, "uuid")
        state['log'] = get_logger(logger_name="workflow.%s" % state['uuid'],
                                  db_handler_obj=db_handler_obj,
                                  obj=self)

        self.__dict__ = state

    def __repr__(self):
        """Allow to represent the BibWorkflowEngine."""
        return "<BibWorkflow_engine(%s)>" % (self.db_obj.name,)

    def __str__(self, log=False):
        """Allow to print the BibWorkflowEngine."""
        return """-------------------------------
BibWorkflowEngine
-------------------------------
    %s
-------------------------------
""" % (self.db_obj.__str__(),)

    def has_completed(self):
        """Return True if workflow is fully completed."""
        res = db.session.query(db.func.count(BibWorkflowObject.id)).\
            filter(BibWorkflowObject.id_workflow == self.uuid).\
            filter(BibWorkflowObject.version.in_(
                [ObjectVersion.INITIAL,
                 ObjectVersion.COMPLETED]
            )).group_by(BibWorkflowObject.version).all()
        return len(res) == 2 and res[0] == res[1]

    def save(self, status=None):
        """Save the workflow instance to database."""
        # This workflow continues a previous execution.
        if status == WorkflowStatus.HALTED:
            self.db_obj.current_object = 0
        self.db_obj.save(status)

    def set_task_position(self, new_position):
        """Set current task position."""
        self._i[1] = new_position

    def restart(self, obj, task):
        """Restart the workflow engine at given object and task.

        Will restart the workflow engine instance at given object and task
        relative to current state.

        `obj` must be either:

        * "prev": previous object
        * "current": current object
        * "next": next object
        * "first": first object

        `task` must be either:

        * "prev": previous object
        * "current": current object
        * "next": next object
        * "first": first object

        To continue with next object from the first task:

        .. code-block:: python

                wfe.restart("next", "first")

        :param obj: the object which should be restarted
        :type obj: str

        :param task: the task which should be restarted
        :type task: str
        """
        self.log.debug("Restarting workflow from %s object and %s task" %
                       (str(obj), str(task),))

        # set the point from which to start processing
        if obj == 'prev':
            # start with the previous object
            self._i[0] -= 2
        elif obj == 'current':
            # continue with the current object
            self._i[0] -= 1
        elif obj == 'next':
            pass
        elif obj == 'first':
            self._i[0] = 0
        else:
            raise Exception('Unknown start point for object: %s' % obj)

        # set the task that will be executed first
        if task == 'prev':
            # the previous
            self._i[1][-1] -= 1
        elif task == 'current':
            # restart the task again
            pass
        elif task == 'next':
            # continue with the next task
            self._i[1][-1] += 1
        elif task == 'first':
            self._i[1] = [0]
        else:
            raise Exception('Unknown start pointfor task: %s' % obj)

        self.process(self._objects)
        self._unpickled = False

    def execute_callback(self, callback, obj):
        """Execute the callback (workflow tasks)."""
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

    def get_current_taskname(self):
        """Get name of current task/step in the workflow (if applicable)."""
        callback_list = self.getCallbacks()
        if callback_list:
            import collections
            for i in self.getCurrTaskId():
                if not isinstance(callback_list, collections.Callable):
                    callback_list = callback_list[i]
            if isinstance(callback_list, list):
                # With operator functions such as IF_ELSE
                # The final value is not a function, but a list.value
                # We currently then just take the __str__ of that list.
                return str(callback_list)
            return callback_list.func_name

    def get_current_object(self):
        """Return the currently active BibWorkflowObject."""
        obj_id = self.getCurrObjId()
        if obj_id < 0:
            return None
        return self._objects[obj_id]

    def halt(self, msg, action=None):
        """Halt the workflow by raising WorkflowHalt.

        Halts the currently running workflow by raising WorkflowHalt.

        You can provide a message and the name of an action to be taken
        (from an action in actions registry).

        :param msg: message explaining the reason for halting.
        :type msg: str

        :param action: name of valid action in actions registry.
        :type action: str

        :raises: WorkflowHalt
        """
        raise WorkflowHalt(message=msg,
                           action=action,
                           id_workflow=self.uuid)

    def get_default_data_type(self):
        """Return default data type from workflow definition."""
        return getattr(self.workflow_definition,
                       "object_type",
                       "")

    def set_counter_initial(self, obj_count):
        """Initiate the counters of object states.

        :param obj_count: Number of objects to process.
        :type obj_count: int
        """
        self.db_obj.counter_initial = obj_count
        self.db_obj.counter_halted = 0
        self.db_obj.counter_error = 0
        self.db_obj.counter_finished = 0

    def increase_counter_halted(self):
        """Indicate we halted the processing of one object."""
        self.db_obj.counter_halted += 1

    def increase_counter_error(self):
        """Indicate we crashed the processing of one object."""
        self.db_obj.counter_error += 1

    def increase_counter_finished(self):
        """Indicate we finished the processing of one object."""
        self.db_obj.counter_finished += 1

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

    def abortProcessing(self):
        """Abort current workflow execution without saving object."""
        raise AbortProcessing

    def skipToken(self):
        """Skip current workflow object without saving it."""
        raise SkipToken


class InvTransitionActions(TransitionActions):

    """Transition actions on engine exceptions for invenio."""

    @staticmethod
    def SkipToken(obj, eng, e):
        """Action to take when SkipToken is raised."""
        msg = "Skipped running this object: '%s' (object: %s)" % \
            (str(eng.callbacks), repr(obj))
        eng.log.debug(msg)
        obj.log.debug(msg)
        raise Continue

    @staticmethod
    def AbortProcessing(obj, eng, e):
        """Action to take when AbortProcessing is raised."""
        msg = "Processing was aborted: '%s' (object: %s)" % \
            (str(eng.callbacks), repr(obj))
        eng.log.debug(msg)
        obj.log.debug(msg)
        raise Break

    @staticmethod
    def StopProcessing(obj, eng, e):
        """Action to take when StopProcessing is raised."""
        try:
            super(InvTransitionActions, InvTransitionActions).StopProcessing(obj, eng, e)
        except Break:
            # Processing for the object is stopped!
            obj.save(version=ObjectVersion.FINAL)
            eng.increase_counter_finished()
            raise

    @staticmethod
    def save_and_inc(obj, eng):
        # This object is skipped for some reason. So we're done
        obj.save(version=ObjectVersion.FINAL)
        eng.increase_counter_finished()

    @staticmethod
    def JumpTokenBack(obj, eng, e):
        """Action to take when JumpTokenBack is raised."""
        super(InvTransitionActions, InvTransitionActions).JumpTokenBack(obj, eng, e)
        InvTransitionActions.save_and_inc(obj, eng)

    @staticmethod
    def JumpTokenForward(obj, eng, e):
        """Action to take when JumpTokenForward is raised."""
        super(InvTransitionActions, InvTransitionActions).JumpTokenForward(obj, eng, e)
        InvTransitionActions.save_and_inc(obj, eng)

    @staticmethod
    def ContinueNextToken(obj, eng, e):
        """Action to take when ContinueNextToken is raised."""
        try:
            super(InvTransitionActions, InvTransitionActions).ContinueNextToken(obj, eng, e)
        except Continue:
            InvTransitionActions.save_and_inc(obj, eng)
            raise

    @staticmethod
    def pre_halt_cleanup(obj, eng):
        eng.increase_counter_halted()
        extra_data = obj.get_extra_data()
        obj.set_extra_data(extra_data)
        workflow_halted.send(obj)

        msg = 'Processing was halted at step: %s' % (eng._i,)
        eng.log.info(msg)
        obj.log.info(msg)

    @staticmethod
    def HaltProcessing(obj, eng, e):
        """Action to take when HaltProcessing is raised."""
        try:
            super(InvTransitionActions, InvTransitionActions).HaltProcessing(obj, eng, e)
        except HaltProcessing:
            InvTransitionActions.pre_halt_cleanup(obj, eng)
            raise WorkflowHalt(e)

    @staticmethod
    def WorkflowHalt(obj, eng, e):
        """Action to take when WorkflowHalt is raised."""
        InvTransitionActions.pre_halt_cleanup(obj, eng)
        reraise(*sys.exc_info())

    @staticmethod
    def catchall(obj, eng, e):
        """Action to take when an otherwise unhandled exception is raised."""
        msg = "Error: %r\n%s" % (e, traceback.format_exc())
        extra_data = obj.get_extra_data()
        obj.set_extra_data(extra_data)
        eng.increase_counter_error()
        if isinstance(e, WorkflowErrorClient):
            reraise(*sys.exc_info())
        else:
            raise WorkflowErrorClient(
                message=msg,
                id_workflow=eng.uuid,
                id_object=eng.getCurrObjId(),
            )


class InvProcessingFactory(ProcessingFactory):

    """Processing factory for invenio's requirements."""

    @property
    def transition_exception_mapper(self):
        """Define our for handling transition exceptions."""
        return InvTransitionActions

    def before_processing(self, objects):
        """Executed before processing the workflow."""
        self.eng.save(status=WorkflowStatus.RUNNING)
        self.eng.set_counter_initial(len(objects))
        workflow_started.send(self)
        super(InvProcessingFactory, self).before_processing(objects)

    def before_object(self, objects, obj):
        """Action to take before the proccessing of an object begins."""
        obj.save(version=ObjectVersion.RUNNING,
                 id_workflow=self.eng.db_obj.uuid)

    def after_object(self, objects, obj):
        """Action to take once the proccessing of an object completes."""
        # We save each object once it is fully run through
        obj.save(version=ObjectVersion.FINAL)
        self.eng.increase_counter_finished()
        self.eng.reset_callbacks_pointer()

    def after_processing(self, objects):
        """Action after process to update status."""
        super(InvProcessingFactory, self).after_processing(self, objects)
        if self.eng.has_completed():
            self.eng.save(WorkflowStatus.COMPLETED)
            workflow_finished.send(self.eng)
        else:
            self.eng.save(WorkflowStatus.HALTED)
