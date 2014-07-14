
invenio.modules.workflows
-------------------------

Run a specified workflow of tasks synchronously (current Python process) or asynchronously (using external task queues like `Celery`).

Workflows can be defined like this:

.. code-block:: python

    class sample(object):
        """A sample workflow adding 20 and checking if higher."""
        workflow = [add_data(20),
                    halt_if_higher_than_20]


as a Python file, located at `yourmodule/workflows/sample.py`.

.. sidebar:: Workflow naming
    :subtitle: A valid workflow must

    (a) Have matching class name and file-name or (b) map the class name using `__all__ = ["myname"]` notation.


The `workflow` attribute should be a list of tasks (or list of lists) as per the conditions of the underlying `workflows-module`_.


.. code-block:: python

    class test_workflow(object):
        """A sample workflow adding 20 and checking if higher."""
        workflow = [add_data(20),
                    halt_if_higher_than_20]



def add_data(data_param):
    """Add data_param to the obj.data."""
    def _add_data(obj, eng):
        data = data_param
        obj.data += data

    return _add_data

def halt_if_higher_than_20(obj, eng):
    """Function checks if variable is higher than 20."""
    if obj.data > 20:
        eng.halt("Value of filed: a in object is higher than 20.")


.. _workflows-module: https://pypi.python.org/pypi/workflow/1.01
