## This file is part of Invenio.
## Copyright (C) 2012, 2013 CERN.
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

from __future__ import print_function

from six import iteritems

from invenio.celery import celery

from invenio.ext.sqlalchemy import db
from invenio.base.helpers import with_app_context


@celery.task(name='invenio.modules.workflows.workers.worker_celery.run_worker')
@with_app_context()
def celery_run(workflow_name, data, **kwargs):
    """
    Runs the workflow with Celery
    """
    from ..worker_engine import run_worker
    from ..utils import BibWorkflowObjectIdContainer
    if isinstance(data, list):
        for i in range(0, len(data)):
            if isinstance(data[i], dict):
                if str(BibWorkflowObjectIdContainer().__class__) in data[i]:
                    data[i] = BibWorkflowObjectIdContainer().from_dict(data[i]).get_object()
                    stack = data[i].get_extra_data().items()
                    while stack:
                        k, v = stack.pop()
                        if isinstance(v, dict):
                            stack.extend(iteritems(v))
                        elif isinstance(v, db.Model):
                            # try except pass to maintain compatibility in case SQLAlchemy is fixed
                            try:
                                db.session.merge(data[i].extra_data["repository"])
                                db.session.add(data[i].extra_data["repository"])
                                db.session.commit()
                            except Exception as e:
                                print("Celery : SQLAlchemy decoherence data object")
                                print(e.message)
    else:
        if isinstance(data, dict):
            if str(BibWorkflowObjectIdContainer().__class__) in data:
                data = BibWorkflowObjectIdContainer().from_dict(data).get_object()
                stack = data.get_extra_data().items()
                while stack:
                    k, v = stack.pop()
                    if isinstance(v, dict):
                        stack.extend(iteritems(v))
                    elif isinstance(v, db.Model):
                        # try except pass to maintain compatibility in case SQLAlchemy is fixed
                        try:
                            db.session.merge(data.extra_data["repository"])
                            db.session.add(data.extra_data["repository"])
                            db.session.commit()
                        except Exception as e:
                            print("Celery : SQLAlchemy decoherence data object")
                            print(e.message)
    run_worker(workflow_name, data, **kwargs)


@celery.task(name='invenio.modules.workflows.workers.worker_celery.restart_worker')
@with_app_context()
def celery_restart(wid, **kwargs):
    """
    Restarts the workflow with Celery
    """
    from ..worker_engine import restart_worker

    restart_worker(wid, **kwargs)


@celery.task(name='invenio.modules.workflows.workers.worker_celery.continue_worker')
@with_app_context()
def celery_continue(oid, restart_point, **kwargs):
    """
    Restarts the workflow with Celery
    """
    from ..worker_engine import continue_worker

    continue_worker(oid, restart_point, **kwargs)


class worker_celery(object):
    def run_worker(self, workflow_name, data, **kwargs):
        """
        Helper function to get celery task
        decorators to worker_celery

        @param workflow_name: name of the workflow to be run
        @type workflow_name: string

        @param data: list of objects for the workflow
        @type data: list
        """
        return celery_run.delay(workflow_name, data, **kwargs)

    def restart_worker(self, wid, **kwargs):
        """
        Helper function to get celery task
        decorators to worker_celery

        @param wid: uuid of the workflow to be run
        @type wid: string
        """
        return celery_restart.delay(wid, **kwargs)

    def continue_worker(self, oid, restart_point, **kwargs):
        """
        Helper function to get celery task
        decorators to worker_celery

        @param oid: uuid of the object to be started
        @type oid: string

        @param restart_point: sets the start point
        @type restart_point: string
        """
        return celery_continue.delay(oid, restart_point, **kwargs)
