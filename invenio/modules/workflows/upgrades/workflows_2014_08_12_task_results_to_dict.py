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


import warnings
import os

depends_on = []


def info():
    return "Will convert all task results to dict instead of object"


def do_upgrade():
    """Implement your upgrades here."""

    class WorkflowsTaskResult(object):
        """The class to contain the current task results."""

        __module__ = os.path.splitext(os.path.basename(__file__))[0]

        def __init__(self, task_name, name, result):
            """Create a task result passing task_name, name and result."""
            self.task_name = task_name
            self.name = name
            self.result = result

        def to_dict(self):
            """Return a dictionary representing a full task result."""
            return {
                'name': self.name,
                'task_name': self.task_name,
                'result': self.result
            }
    # Try to fetch the right model, if not search for it (in case of renaming).
    try:
        from ..models import BibWorkflowObject
        object_model = BibWorkflowObject
    except ImportError:
        warnings.warn("Cannot find BibWorkflowObject. Trying __all__.")
        from invenio.modules.workflows import models

        all_ = getattr(models, "__all__")
        object_model = None
        for model in all_:
            candidate_model = getattr(models, model)
            if hasattr(candidate_model, "get_tasks_results"):
                object_model = candidate_model
                break
    if not object_model:
        warnings.warn("Cannot find any model. Skipping.")
        return

    from invenio.modules.workflows import utils
    utils.WorkflowsTaskResult = WorkflowsTaskResult
    for bwo in object_model.query.all():
        extra_data = bwo.get_extra_data()
        if "_tasks_results" in extra_data:
            extra_data["_tasks_results"] = convert_to_dict(
                extra_data["_tasks_results"]
            )
            bwo.set_extra_data(extra_data)
            bwo.save()


def estimate():
    """Estimate running time of upgrade in seconds (optional)."""
    return 1


def convert_to_dict(results):
    """Convert WorkflowTask object to dict"""
    results_new = {}
    for task, res in results.iteritems():
        result_list = []
        for result in res:
            if isinstance(result, dict):
                result_list.append(result)
            elif hasattr(result, "to_dict"):
                new_result = result.to_dict()
                # Set default template
                new_result["template"] = map_existing_templates(task)
                result_list.append(new_result)
        results_new[task] = result_list
    return results_new


def map_existing_templates(name):
    """Return a template given a task name, else return default."""
    mapping = {
        "fulltext_download": "workflows/results/fulltext_download.html",
        "refextract": "workflows/results/refextract.html",
    }
    return mapping.get(name, "workflows/results/default.html")
